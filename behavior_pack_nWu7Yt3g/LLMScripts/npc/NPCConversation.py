# -*- coding: utf-8 -*-
"""
NPC 对话管理器
管理每个 NPC 实体的独立对话历史和 Bridge 通信
"""
import json
import socket
import threading

from LLMScripts.npc.NPCProfileManager import NPCProfileManager


class NPCConversation(object):
    """对话管理器，每个 NPC 实体对应一个实例"""

    MAX_HISTORY = 30
    BRIDGE_HOST = "127.0.0.1"
    BRIDGE_PORT = 19999

    def __init__(self, entity_id, profile_id, display_name=None):
        self.entity_id = entity_id
        self.profile_id = profile_id
        self.profile = NPCProfileManager().get(profile_id)
        # 实体的实际显示名（可能带后缀如"战士-2"）
        self._display_name = display_name
        # 对话历史: [{"role": "user"/"assistant", "content": "..."}, ...]
        self.history = []
        # 当前在线玩家列表
        self._online_players = []
        # 打断标记：新消息到来时设为 True，旧线程检测到后停止处理
        self._interrupted = False

    def set_online_players(self, names):
        """设置当前在线玩家名单"""
        self._online_players = list(names)

    def interrupt(self):
        """打断当前对话的处理（新消息到来时调用）"""
        self._interrupted = True

    @property
    def display_name(self):
        """NPC 显示名（带颜色）"""
        name = self._display_name or self.profile.get("name", "NPC")
        return "%s%s§r" % (self.profile["color"], name)

    def get_system_prompt(self):
        """获取 system prompt，注入名字+通用行为规范"""
        base = self.profile["system_prompt"]
        name = self._display_name or self.profile.get("name", "NPC")
        tool_tip = (
            "\n\n=== 工具使用规则 ===\n\n"
            "你必须通过工具来执行实际动作，光在文字中说要做什么并不会真的发生。\n"
            "可用的工具列表已单独提供给你。\n"
            "常用工具说明：\n"
            "  - move_to_player: 移动到玩家身边\n"
            "  - get_pos: 获取自己或指定目标的坐标（支持玩家名/实体ID）\n"
            "  - get_health: 获取自己或指定玩家的血量\n"
            "  - get_entity_info: 查询任意实体的详细信息\n"
            "  - look_at: 看向某个目标\n\n"
            "=== 战斗纪律 ===\n\n"
            "如果你正在追击/攻击一个目标（调用了 attack_entity 且目标还活着），\n"
            "在它死掉之前**不要**对另一个目标再次使用 attack_entity。\n"
            "必须先用 get_health 确认当前目标死亡（health <= 0），再转向下一个。\n"
            "多个敌人时，集中火力逐个击破，不要打一下这个又去打那个。\n\n"
            "=== 工具反馈机制 ===\n\n"
            "当你调用工具后，系统会把执行结果送回给你。\n"
            "你可以基于结果继续调工具，或者生成最终回复。\n"
            "你可以连续多轮调工具，逐步获取信息后再回复。\n\n"
            "=== 重要：数据时效性 ===\n\n"
            "对话历史中的工具执行结果是**历史快照**，不代表当前状态。\n"
            "如果需要获取最新信息（如当前位置、血量、附近方块等），必须**重新调用**对应的工具，不要依赖历史记录中的数据。\n"
            "例如：玩家问「附近有箱子吗」时，必须重新调用 scan_blocks 扫描，而不是引用上一次的扫描结果。\n\n"
            "=== 输出格式要求 ===\n\n"
            "你回复的 text 会直接显示在 Minecraft 聊天框中。\n"
            "禁止使用任何颜色代码（如§、$等符号）和 emoji、颜文字或特殊 Unicode 符号。\n"
            "禁止使用：😂😄👍🌟🎉❤️📍☺️❌✅⚠️➡️⭐🔥💀🔍🛡️⚔️🧱💎🏠🚪🗺️ 等任何 emoji 或特殊符号。\n"
            "用纯文本回复即可，系统会自动为你添加颜色。\n\n"
            "你的名字是%s。%s"
        )
        return tool_tip % (name, base)

    def add_user_message(self, content):
        """添加玩家消息到历史"""
        self.history.append({"role": "user", "content": content})
        self._trim()

    def add_assistant_message(self, content):
        """添加 AI 回复到历史"""
        self.history.append({"role": "assistant", "content": content})
        self._trim()

    def clear_history(self):
        """清除对话历史"""
        self.history = []

    def _trim(self):
        """超出上限时裁剪"""
        if len(self.history) > self.MAX_HISTORY:
            self.history = self.history[-self.MAX_HISTORY:]

    def build_messages(self, question):
        """构建完整的 messages 数组，注入在线玩家信息"""
        messages = [{"role": "system", "content": self.get_system_prompt()}]
        messages.extend(self.history)
        # 注入当前在线玩家名单，让 AI 知道有哪些人以及消息前缀含义
        if self._online_players:
            player_list_str = "、".join(self._online_players)
            messages.append({
                "role": "system",
                "content": "当前在线玩家：%s。玩家的消息会以[玩家名]为前缀，你可以通过玩家名使用工具查询他们的信息。" % player_list_str
            })
        messages.append({"role": "user", "content": question})
        return messages

    def call_bridge(self, question, callback):
        """在子线程中调 Bridge（携带 MCP 工具定义）"""
        thread = threading.Thread(
            target=self._do_call,
            args=(question, callback)
        )
        thread.daemon = True
        thread.start()

    def _do_call(self, question, callback):
        """实际的 Bridge 调用"""
        try:
            if self._interrupted:
                print("[NPCConversation] 对话已被打断，跳过本次请求")
                return

            messages = self.build_messages(question)
            payload_dict = {"messages": messages}

            # 附加 MCP 工具定义
            try:
                from action_tools.tool_registry import ToolRegistry
                tools = ToolRegistry.get_tools_mcp_schema()
                if tools:
                    payload_dict["tools"] = tools
                    print("[NPCConversation] 携带工具定义: %d 个" % len(tools))
            except ImportError:
                pass

            payload = json.dumps(payload_dict)
            print("[NPCConversation] 发送到Bridge的消息数=%d, 工具数=%d, 最近消息=[%s]" % (
                len(messages), len(tools or []), messages[-1].get("content", "")[:60] if messages else ""))

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(30)

            try:
                sock.connect((self.BRIDGE_HOST, self.BRIDGE_PORT))
            except socket.error:
                callback("[Error] Bridge 未运行，请启动 DEEPSEEK_BRIDGE")
                sock.close()
                return

            # 先发数据长度（4字节大端整数），再发实际数据
            payload_bytes = payload.encode("utf-8")
            import struct
            sock.sendall(struct.pack(">I", len(payload_bytes)))
            sock.sendall(payload_bytes)

            response_data = ""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response_data += chunk
            sock.close()

            if response_data:
                reply = response_data.decode("utf-8").strip()
                callback(reply)
            else:
                callback("")

        except socket.timeout:
            callback("[Error] 请求超时")
        except Exception as e:
            callback("[Error] %s" % str(e))
