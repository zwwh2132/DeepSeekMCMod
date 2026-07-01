# -*- coding: utf-8 -*-

import json
import mod.server.extraServerApi as serverApi
from LLMScripts.npc.NPCConversation import NPCConversation
from LLMScripts.npc.NPCProfileManager import NPCProfileManager
from LLMScripts.npc.NPCManager import NPCManager
from LLMScripts.npc.action_tools.tool_registry import ToolRegistry, BridgeResponseParser
from LLMScripts.npc.action_tools import ActionTool


class LLMServerSystem(serverApi.GetServerSystemCls()):

    _RED = "§c"
    _GREEN = "§a"
    _BLUE = "§b"
    _R = "§r"

    def __init__(self, namespace, name):
        super(LLMServerSystem, self).__init__(namespace, name)
        print("===== LLMServerSystem 初始化 =====")

        self._result_queue = []

        # 对话管理器: {entityId_or_name: NPCConversation}
        self._conversations = {}
        # 按名字索引：{display_name: NPCConversation}，NPC死亡后对话不丢失
        self._name_conversations = {}
        self._npc_manager = NPCManager()
        self._npc_manager.set_system(self)  # 注入系统实例用于监听事件
        self._npc_profile_manager = NPCProfileManager()

        # 确保 ActionTool 已被注册（import action_tools 时会自动注册）
        print("[LLMServerSystem] 已注册工具: %s" % list(ToolRegistry.get_all().keys()))

        # 指令事件
        self.ListenForEvent(
            serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
            "CustomCommandTriggerServerEvent", self, self._OnCustomCommand
        )
        # 聊天缓存
        self.ListenForEvent(
            serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
            "ServerChatEvent", self, self._OnServerChat
        )
        # Tick 处理队列
        self.ListenForEvent(
            serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
            "OnScriptTickServer", self, self._OnTick
        )
        # 实体创建/加载（用于存档重载时恢复 NPC 注册）
        self.ListenForEvent(
            serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
            "AddEntityServerEvent", self, self._OnAddEntity
        )
        # 客户端回传真实 playerId
        self.ListenForEvent(
            "LLMTestMod", "LLMClientSystem",
            "LLMShowChatEvent", self, self._OnShowChat
        )

        print("===== LLMServerSystem 初始化完成 =====")

    # ==================== 对话管理 ====================

    def _get_conversation(self, entity_id, profile_id=None):
        """获取或创建对话实例
        Args:
            entity_id: NPC 实体 id（或 "default"/profile_id 字符串）
            profile_id: 可选，指定 profile
        """
        # 兼容旧的 profile_id 字符串 key
        if entity_id in self._conversations:
            return self._conversations[entity_id]

        # 确定 profile_id
        if not profile_id:
            if entity_id == "default":
                profile_id = "default"
            else:
                # 从 NPCManager 获取
                npc_info = self._npc_manager.get_npc(entity_id)
                if npc_info:
                    profile_id = npc_info.get("profile_id", "default")
                else:
                    # 尝试从 ExtraData 读取（serverApi 已在顶部导入）
                    extra = serverApi.GetEngineCompFactory().CreateExtraData(entity_id)
                    profile_id = extra.GetExtraData("profile_id")
                    if not profile_id:
                        profile_id = "default"

        # 获取显示名（NPC 实体才有独立名字，"default"对话没有）
        display_name = None
        if entity_id != "default":
            npc_info = self._npc_manager.get_npc(entity_id)
            if npc_info:
                display_name = npc_info.get("display_name")

        conversation = NPCConversation(entity_id, profile_id, display_name)
        self._conversations[entity_id] = conversation
        # NPC对话同时按名字索引，死亡后仍可通过名字找到
        if display_name:
            self._name_conversations[display_name] = conversation
        return conversation

    # ==================== 聊天缓存 ====================

    def _OnServerChat(self, args):
        """缓存聊天消息，@NPC名字 开头的消息定向到指定NPC的上下文"""
        try:
            msg = args.get("message", "").strip()
            pid = args.get("playerId", "")
            if not msg or not pid or msg.startswith("/"):
                return

            # 只处理 @NPC名字 前缀的消息
            if not msg.startswith("@"):
                return

            rest = msg[1:]  # 去掉 @

            # 收集所有可能的 NPC 名字（对话记录 + 已生成实体）
            all_names = set(self._name_conversations.keys())
            for info in self._npc_manager.get_all().values():
                all_names.add(info.get("display_name", ""))

            # 按名字长度降序匹配，避免"战士"匹配到"战士-2"的内容
            matched_name = None
            for name in sorted(all_names, key=lambda x: -len(x)):
                if not name:
                    continue
                if rest.startswith(name):
                    matched_name = name
                    break

            if not matched_name:
                print("===== _OnServerChat 未找到NPC: rest=[%s], 已知NPC列表=%s =====" % (
                    rest, list(all_names)))
                return

            content = rest[len(matched_name):].strip()
            if not content:
                return

            print("===== _OnServerChat @解析: npc_name=[%s], content=[%s] =====" % (matched_name, content))

            # 获取玩家名字
            nameComp = serverApi.GetEngineCompFactory().CreateName(pid)
            player_name = nameComp.GetName() or pid

            # 和 /ainpc 一样触发回复
            self._start_npc_reply(pid, player_name, matched_name, content)
        except Exception as e:
            print("===== _OnServerChat 出错: %s =====" % str(e))

    # ==================== 指令处理 ====================

    def _OnCustomCommand(self, args):
        try:
            cmd = args.get("command", "")
            if cmd == "ai":
                self._HandleAI(args)
            elif cmd == "aiclear":
                self._HandleAIClear(args)
            elif cmd == "aiconfig":
                self._HandleAIConfig(args)
            elif cmd == "ainpcs":
                self._HandleAINPCs(args)
            elif cmd == "ainpc":
                self._HandleAINPC(args)
            elif cmd == "ainpc_spawn":
                self._HandleAINPCSpawn(args)
            elif cmd == "ainpc_list":
                self._HandleAINPCList(args)
            elif cmd == "ainpc_despawn":
                self._HandleAINPCDespawn(args)
            elif cmd == "ainpc_clear":
                self._HandleAINPCClear(args)
            elif cmd == "ainpc_clear_all":
                self._HandleAINPCClearAll(args)
        except Exception as e:
            print("===== _OnCustomCommand 出错: %s =====" % str(e))

    def _HandleAI(self, args):
        """处理 /ai 指令：/ai <问题>"""
        try:
            raw_question = ""
            for arg in args.get("args", []):
                if arg.get("name") == "问题":
                    raw_question = arg.get("value", "")
                    break
            if not raw_question:
                self._NotifyPlayer("", "%s用法: /ai <你的问题>%s" % (self._RED, self._R))
                return

            origin = args.get("origin", {})
            player_id = origin.get("entityId", "")
            player_list = serverApi.GetPlayerList()
            if player_id not in player_list and player_list:
                player_id = player_list[0]
            if not player_id:
                return

            # 获取玩家名字
            nameComp = serverApi.GetEngineCompFactory().CreateName(player_id)
            player_name = nameComp.GetName() or player_id

            # 给 AI 的问题带上前缀，让它知道谁在说话
            ai_question = "[%s] %s" % (player_name, raw_question)

            # 广播提问到公屏（用 SendMsg 模拟玩家发消息，显示为 <玩家名> 内容）
            self._result_queue.append(("__broadcast_chat__", player_name, raw_question))

            self._NotifyPlayer(player_id, "%sAI思考中...%s" % (self._GREEN, self._R))

            conv = self._get_conversation("default", "default")
            # 打断旧的默认对话
            conv.interrupt()
            self._clear_pending_tools("default")
            # 设置当前在线玩家列表
            all_players = serverApi.GetPlayerList()
            online_names = []
            for pid in all_players:
                ncomp = serverApi.GetEngineCompFactory().CreateName(pid)
                pname = ncomp.GetName()
                if pname:
                    online_names.append(pname)
            conv.set_online_players(online_names)
            conv._interrupted = False
            conv.call_bridge(ai_question, lambda reply: self._on_reply(player_id, reply, conv, ai_question))

        except Exception as e:
            print("===== _HandleAI 出错: %s =====" % str(e))

    def _HandleAIClear(self, args):
        """清除默认 AI 对话历史"""
        try:
            origin = args.get("origin", {})
            player_id = origin.get("entityId", "")
            player_list = serverApi.GetPlayerList()
            if player_id not in player_list and player_list:
                player_id = player_list[0]
            if not player_id:
                return

            conv = self._get_conversation("default", "default")
            conv.clear_history()
            self._NotifyPlayer(player_id, "%sAI对话历史已清除%s" % (self._GREEN, self._R))
        except Exception as e:
            print("===== _HandleAIClear 出错: %s =====" % str(e))

    def _HandleAIConfig(self, args):
        """查看配置"""
        try:
            origin = args.get("origin", {})
            player_id = origin.get("entityId", "")
            player_list = serverApi.GetPlayerList()
            if player_id not in player_list and player_list:
                player_id = player_list[0]
            if not player_id:
                return
            self._NotifyPlayer(player_id, "%s[Bridge] 127.0.0.1:19999%s" % (self._GREEN, self._R))
            self._NotifyPlayer(player_id, "%s  /ainpcs 查看可用NPC%s" % (self._GREEN, self._R))
        except Exception as e:
            print("===== _HandleAIConfig 出错: %s =====" % str(e))

    def _HandleAINPCs(self, args):
        """列出所有可用 NPC 配置"""
        try:
            origin = args.get("origin", {})
            player_id = origin.get("entityId", "")
            player_list = serverApi.GetPlayerList()
            if player_id not in player_list and player_list:
                player_id = player_list[0]
            if not player_id:
                return

            profiles = self._npc_profile_manager.get_all()
            self._NotifyPlayer(player_id, "%s可用NPC配置:%s" % (self._GREEN, self._R))
            for pid, p in profiles.items():
                desc = p.get("description", "")
                self._NotifyPlayer(player_id, "  %s%s§r - %s" % (p["color"], p["name"], desc))
            self._NotifyPlayer(player_id, "%s使用 /ainpc <名字> <问题> 对话%s" % (self._GREEN, self._R))
            self._NotifyPlayer(player_id, "%s使用 /ainpc_spawn <模板> [名字] 生成实体%s" % (self._GREEN, self._R))
        except Exception as e:
            print("===== _HandleAINPCs 出错: %s =====" % str(e))

    def _start_npc_reply(self, player_id, player_name, npc_name, content):
        """触发 NPC 对话回复的公共逻辑（供 /ainpc 指令和 @聊天 共用）"""
        # 按显示名查找 NPC 实体（可能已经死亡）
        entity_id = self._npc_manager.find_by_display_name(npc_name)
        is_alive = bool(entity_id)

        # 给 AI 的问题带上前缀
        ai_question = "[%s] %s" % (player_name, content)

        # 获取或创建对话（优先用名字查找，NPC死亡后仍有对话记录）
        conv = self._name_conversations.get(npc_name)
        if not conv:
            profile_id = "default"
            if is_alive:
                npc_info = self._npc_manager.get_npc(entity_id)
                if npc_info:
                    profile_id = npc_info.get("profile_id", "default")
            conv = NPCConversation(npc_name, profile_id, npc_name)
            self._conversations[npc_name] = conv
            self._name_conversations[npc_name] = conv
        elif is_alive:
            if conv.entity_id != entity_id:
                conv.entity_id = entity_id
                self._conversations[entity_id] = conv

        # 广播提问到公屏
        self._result_queue.append(("__broadcast_chat__", player_name, content))

        # 打断旧的对话处理
        conv.interrupt()
        if is_alive:
            self._clear_pending_tools(entity_id)
            # 停止 NPC 移动
            try:
                move_comp = serverApi.GetEngineCompFactory().CreateMoveTo(entity_id)
                extra = serverApi.GetEngineCompFactory().CreateExtraData(entity_id)
                extra.SetExtraData("follow_target_player", "")
                motion_comp = serverApi.GetEngineCompFactory().CreateActorMotion(entity_id)
                motion_comp.SetMotion((0, 0, 0))
            except Exception:
                pass
        else:
            self._NotifyPlayer(player_id, "%s[与%s对话中 - NPC已死亡]%s" % (self._GREEN, npc_name, self._R))

        # 设置当前在线玩家列表
        all_players = serverApi.GetPlayerList()
        online_names = []
        for pid in all_players:
            ncomp = serverApi.GetEngineCompFactory().CreateName(pid)
            pname = ncomp.GetName()
            if pname:
                online_names.append(pname)
        conv.set_online_players(online_names)

        if is_alive:
            npc_display = "%s%s§r" % (self._GREEN, npc_name)
            self._NotifyPlayer(player_id, "%s[与%s对话中]%s" % (self._GREEN, npc_display, self._R))

        # 重置打断标记，让新请求能正常处理
        conv._interrupted = False
        conv.call_bridge(ai_question, lambda reply: self._on_reply(player_id, reply, conv, ai_question))

    def _HandleAINPC(self, args):
        """处理 /ainpc 指令：/ainpc <名字> <问题>"""
        try:
            npc_name = ""
            raw_question = ""
            for arg in args.get("args", []):
                name = arg.get("name", "")
                if name == "名字":
                    npc_name = arg.get("value", "")
                elif name == "问题":
                    raw_question = arg.get("value", "")
            if not npc_name or not raw_question:
                self._NotifyPlayer("", "%s用法: /ainpc <名字> <问题>%s" % (self._RED, self._R))
                return

            origin = args.get("origin", {})
            player_id = origin.get("entityId", "")
            player_list = serverApi.GetPlayerList()
            if player_id not in player_list and player_list:
                player_id = player_list[0]
            if not player_id:
                return

            nameComp = serverApi.GetEngineCompFactory().CreateName(player_id)
            player_name = nameComp.GetName() or player_id

            self._start_npc_reply(player_id, player_name, npc_name, raw_question)

        except Exception as e:
            print("===== _HandleAINPC 出错: %s =====" % str(e))

    def _HandleAINPCSpawn(self, args):
        """处理 /ainpc_spawn <模板> [名字] 指令：生成 NPC 实体"""
        try:
            template_name = ""
            custom_name = ""
            for arg in args.get("args", []):
                arg_name = arg.get("name", "")
                if arg_name == "模板":
                    template_name = arg.get("value", "")
                elif arg_name == "名字":
                    custom_name = arg.get("value", "")
                    break
            if not template_name:
                self._NotifyPlayer("", "%s用法: /ainpc_spawn <模板> [名字]%s" % (self._RED, self._R))
                return

            origin = args.get("origin", {})
            player_id = origin.get("entityId", "")
            if not player_id:
                player_list = serverApi.GetPlayerList()
                if player_list:
                    player_id = player_list[0]
            if not player_id:
                return

            # 匹配 NPC 配置（支持模板名或 ID）
            profiles = self._npc_profile_manager.get_all()
            profile_id = None
            for pid, p in profiles.items():
                if pid == template_name or p.get("name", "") == template_name:
                    profile_id = pid
                    break
            if not profile_id:
                self._NotifyPlayer(player_id, "%s未找到NPC模板「%s」%s" % (self._RED, template_name, self._R))
                return

            # 第一步：获取生成位置
            spawn_info = self._npc_manager.create_npc(profile_id, player_id)
            if not spawn_info:
                self._NotifyPlayer(player_id, "%s无法获取生成位置%s" % (self._RED, self._R))
                return

            # 第二步：在自己的系统上下文中创建实体
            entity_id = self.CreateEngineEntityByTypeStr(
                NPCManager.NPC_IDENTIFIER,
                spawn_info["pos"],
                (0, 0),
                spawn_info["dimension_id"]
            )

            # 第三步：初始化实体（传递自定义名字，不传则自动生成）
            if entity_id:
                display_name = custom_name if custom_name else None
                result = self._npc_manager.after_spawn(entity_id, profile_id, display_name)
                if result is None and display_name:
                    # 名字已存在，销毁已创建的实体
                    self.DestroyEntity(entity_id)
                    self._NotifyPlayer(player_id, "%s名字「%s」已被占用，请换一个名字%s" % (self._RED, display_name, self._R))
                    return
                # 获取实际生成的显示名
                npc_info = self._npc_manager.get_npc(entity_id)
                final_name = npc_info.get("display_name", "?") if npc_info else "?"

                # 同名重生：继承旧的对话记录
                old_conv = self._name_conversations.get(final_name)
                if old_conv:
                    self._conversations[entity_id] = old_conv
                    # 更新 conversation 内部的 entity_id 引用
                    old_conv.entity_id = entity_id
                    print("===== _HandleAINPCSpawn: 继承旧对话 history_len=%d =====" % len(old_conv.history))
                    self._NotifyPlayer(player_id, "%s已继承「%s」的对话记忆%s" % (self._GREEN, final_name, self._R))

                self._NotifyPlayer(player_id, "%s已生成NPC实体「%s」%s" % (self._GREEN, final_name, self._R))
                self._NotifyPlayer(player_id, "%s 使用 /ainpc %s <问题> 对话%s" % (self._GREEN, final_name, self._R))
            else:
                self._NotifyPlayer(player_id, "%s生成失败%s" % (self._RED, self._R))

        except Exception as e:
            print("===== _HandleAINPCSpawn 出错: %s =====" % str(e))

    def _HandleAINPCList(self, args):
        """列出所有已生成的 NPC 实体"""
        try:
            origin = args.get("origin", {})
            player_id = origin.get("entityId", "")
            player_list = serverApi.GetPlayerList()
            if player_id not in player_list and player_list:
                player_id = player_list[0]
            if not player_id:
                return

            npcs = self._npc_manager.get_all()
            count = self._npc_manager.count()
            self._NotifyPlayer(player_id, "%s当前 NPC 实体 (%d 个):%s" % (self._GREEN, count, self._R))
            for eid, info in npcs.items():
                self._NotifyPlayer(player_id, "  %s (profile: %s, 实体: %s)" % (
                    info.get("display_name", "?"), info.get("profile_id", "?"), eid[:12] + "..."
                ))
        except Exception as e:
            print("===== _HandleAINPCList 出错: %s =====" % str(e))

    def _HandleAINPCDespawn(self, args):
        """移除 NPC 实体"""
        try:
            origin = args.get("origin", {})
            player_id = origin.get("entityId", "")
            player_list = serverApi.GetPlayerList()
            if player_id not in player_list and player_list:
                player_id = player_list[0]
            if not player_id:
                return

            # 检查是否有名字参数
            npc_name = ""
            for arg in args.get("args", []):
                if arg.get("name") == "名字":
                    npc_name = arg.get("value", "")
                    break

            if not npc_name:
                # 没有参数 → 移除所有
                count = self._npc_manager.remove_all()
                self._NotifyPlayer(player_id, "%s已移除 %d 个 NPC 实体%s" % (self._GREEN, count, self._R))
            else:
                # 按显示名移除
                entity_id = self._npc_manager.find_by_display_name(npc_name)
                if not entity_id:
                    self._NotifyPlayer(player_id, "%s未找到NPC「%s」%s" % (self._RED, npc_name, self._R))
                    return
                if self._npc_manager.remove_npc(entity_id):
                    self._NotifyPlayer(player_id, "%s已移除NPC「%s」%s" % (self._GREEN, npc_name, self._R))
                else:
                    self._NotifyPlayer(player_id, "%s移除NPC「%s」失败%s" % (self._RED, npc_name, self._R))

        except Exception as e:
            print("===== _HandleAINPCDespawn 出错: %s =====" % str(e))

    def _HandleAINPCClear(self, args):
        """清除某个NPC实体的对话历史"""
        try:
            npc_name = ""
            for arg in args.get("args", []):
                if arg.get("name") == "名字":
                    npc_name = arg.get("value", "")
                    break
            if not npc_name:
                self._NotifyPlayer("", "%s用法: /ainpc_clear <名字>%s" % (self._RED, self._R))
                return

            origin = args.get("origin", {})
            player_id = origin.get("entityId", "")
            player_list = serverApi.GetPlayerList()
            if player_id not in player_list and player_list:
                player_id = player_list[0]
            if not player_id:
                return

            # 按名字查找对话（包括已死亡的NPC）
            conv = self._name_conversations.get(npc_name)
            if conv:
                conv.clear_history()
                self._NotifyPlayer(player_id, "%s已清除「%s」的对话历史%s" % (self._GREEN, npc_name, self._R))
            else:
                self._NotifyPlayer(player_id, "%s「%s」没有对话历史%s" % (self._GREEN, npc_name, self._R))

        except Exception as e:
            print("===== _HandleAINPCClear 出错: %s =====" % str(e))

    def _HandleAINPCClearAll(self, args):
        """清除所有NPC的对话历史"""
        try:
            origin = args.get("origin", {})
            player_id = origin.get("entityId", "")
            player_list = serverApi.GetPlayerList()
            if player_id not in player_list and player_list:
                player_id = player_list[0]
            if not player_id:
                return

            count = 0
            for conv in self._name_conversations.values():
                conv.clear_history()
                count += 1

            self._NotifyPlayer(player_id, "%s已清除全部 %d 个NPC的对话历史%s" % (self._GREEN, count, self._R))

        except Exception as e:
            print("===== _HandleAINPCClearAll 出错: %s =====" % str(e))

    # ==================== Bridge 回调 ====================
    MAX_FEEDBACK_ROUNDS = 80

    @staticmethod
    def _convert_unicode_to_str(obj):
        """递归将 unicode 转为 str（Python 2 的 json.loads 产出 unicode，API 需要 str）"""
        if isinstance(obj, dict):
            return {LLMServerSystem._convert_unicode_to_str(k): LLMServerSystem._convert_unicode_to_str(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [LLMServerSystem._convert_unicode_to_str(item) for item in obj]
        elif isinstance(obj, unicode):
            return str(obj)
        return obj

    @staticmethod
    def _fix_nested_json(text, tool_calls):
        """兜底修复：AI 有时会在 text 字段里嵌套 JSON，递归提取真正的文本和工具"""
        seen = set()
        while text and text.startswith("{") and not tool_calls:
            if text in seen:
                break
            seen.add(text)
            try:
                inner = json.loads(text)
                if isinstance(inner, dict):
                    text = inner.get("text", "")
                    tool_calls = inner.get("tool_calls", [])
                    continue
            except (ValueError, TypeError):
                pass
            break
        return text, tool_calls

    @staticmethod
    def _fix_unicode_escapes(text):
        """兜底修复：处理文本中未解码的 \\uXXXX unicode 转义序列（支持多重反斜杠）"""
        if not text or "\\u" not in text:
            return text
        try:
            import re
            return re.sub(r'\\+u([0-9a-fA-F]{4})', lambda m: unichr(int(m.group(1), 16)), text)
        except Exception:
            pass
        return text

    def _on_reply(self, player_id, reply, conv, question, feedback_rounds=MAX_FEEDBACK_ROUNDS):
        """Bridge 回调：收到回复后解析工具调用 + 显示文本
        feedback_rounds: 剩余工具反馈轮数，每轮递减，0 表示不再反馈。
        注意：此方法在子线程中执行！不能直接调 serverApi。
        将解析结果放入队列，由 _OnTick 在主线程执行。
        """
        try:
            if reply.startswith("[Error]"):
                self._result_queue.append((player_id, reply))
                return

            # print("===== _on_reply: 原始回复=[%s] =====" % reply)

            # 先存对话历史（原始回复，含工具标记）
            conv.add_user_message(question)
            conv.add_assistant_message(reply)

            print("===== _on_reply: 原始回复=[%s] =====" % reply)

            # 解析工具调用（Bridge 返回的 JSON 格式）
            parsed = BridgeResponseParser.parse(reply)
            # 统一将 unicode 转成 str（Python 2 的 json.loads 产出 unicode，API 需要 str）
            parsed = self._convert_unicode_to_str(parsed)
            text = parsed["text"]
            tool_calls = parsed["tool_calls"]

            # 兜底修复：如果 text 本身是 JSON（AI 嵌套了格式），递归提取真正的文本和工具
            text, tool_calls = self._fix_nested_json(text, tool_calls)

            # 兜底修复：处理未解码的 \\uXXXX unicode 转义序列
            text = self._fix_unicode_escapes(text)

            print("===== _on_reply: 解析结果 text=[%s], tool_calls=%s =====" % (text, tool_calls))

            # 工具反馈闭环：AI 可以多轮调用工具，逐步推理后再回复
            if tool_calls and conv.entity_id and conv.entity_id != "default" and feedback_rounds > 0:
                if not text:
                    # AI 只调工具没说文字 → 执行工具后送回 AI，剩余轮次减 1
                    self._result_queue.append((
                        "__tool_feedback__", conv.entity_id, tool_calls, player_id, conv, feedback_rounds - 1
                    ))
                    return
                else:
                    # 既说话又调工具 → 先广播文本，再执行工具（继续反馈）
                    self._result_queue.append((
                        "__tool_feedback__", conv.entity_id, tool_calls, player_id, conv, feedback_rounds - 1
                    ))

            # 把文本回复放入队列（广播到全服）
            display_name = conv.display_name
            if text:
                self._result_queue.append(("__broadcast__", "%s %s" % (display_name, text)))

        except Exception as e:
            print("===== _on_reply 出错: %s =====" % str(e))

    # ==================== 消息显示 ====================

    def _OnTick(self, args=None):
        try:
            while self._result_queue:
                item = self._result_queue.pop(0)

                # 判断是否是工具执行请求
                if len(item) == 4 and item[0] == "__tool__":
                    # ("__tool__", entity_id, tool_calls, player_id)
                    _, entity_id, tool_calls, player_id = item
                    self._execute_tools(entity_id, tool_calls, player_id)
                elif item[0] == "__broadcast_chat__":
                    # ("__broadcast_chat__", player_name, message)
                    _, player_name, message = item
                    self._SendChatMessage(player_name, message)
                elif item[0] == "__broadcast__":
                    # ("__broadcast__", message) — NPC/AI 回复
                    _, message = item
                    self._BroadcastMessage(message)
                elif item[0] == "__tool_feedback__":
                    # ("__tool_feedback__", entity_id, tool_calls, player_id, conv, feedback_rounds)
                    _, entity_id, tool_calls, player_id, conv, feedback_rounds = item
                    self._execute_tools_with_feedback(entity_id, tool_calls, player_id, conv, feedback_rounds)
                else:
                    # 普通消息 (player_id, message)
                    player_id, message = item[0], item[1]
                    self._NotifyPlayer(player_id, message)
        except Exception as e:
            print("===== _OnTick 出错: %s =====" % str(e))

    def _OnAddEntity(self, args):
        """实体创建或从存档加载时，尝试恢复 NPC 注册"""
        try:
            engine_type = args.get("engineTypeStr", "")
            if engine_type != NPCManager.NPC_IDENTIFIER:
                return
            entity_id = args.get("id", "")
            if entity_id:
                self._npc_manager.try_register(entity_id)
        except Exception as e:
            print("===== _OnAddEntity 出错: %s =====" % str(e))

    def _execute_tools(self, entity_id, tool_calls, player_id):
        """在主线程中执行工具调用"""
        try:
            npc_info = self._npc_manager.get_npc(entity_id)
            print("===== _execute_tools: entity_id=%s, tool_calls=%s, npc_info=%s =====" % (
                entity_id, tool_calls, npc_info))
            if not npc_info:
                print("===== _execute_tools: NPC实体不在管理器中，跳过 =====")
                return

            context = {"playerId": player_id, "levelId": serverApi.GetLevelId()}
            print("===== _execute_tools: context=%s =====" % context)

            for call in tool_calls:
                tool_name = call.get("name", "")
                tool_args = call.get("args", {})
                print("===== _execute_tools: 执行 tool=%s, args=%s =====" % (tool_name, tool_args))
                tool_cls = ToolRegistry.get(tool_name)
                if not tool_cls:
                    print("===== _execute_tools: 未知工具 %s =====" % tool_name)
                    continue

                result = tool_cls.execute(entity_id, tool_args, context)
                print("===== _execute_tools: 结果 %s =====" % result)
                if result.get("status") == "ok":
                    msg = result.get("message", "")
                    if msg:
                        self._NotifyPlayer(player_id, msg)
        except Exception as e:
            print("===== _execute_tools 出错: %s =====" % str(e))

    def _execute_tools_with_feedback(self, entity_id, tool_calls, player_id, conv, feedback_rounds):
        """执行工具并将结果送回 AI，让 AI 继续推理或生成自然语言回复"""
        try:
            if conv._interrupted:
                print("[_execute_tools_with_feedback] 对话已被打断，跳过")
                return

            context = {"playerId": player_id, "levelId": serverApi.GetLevelId()}
            results = []
            for call in tool_calls:
                tool_name = call.get("name", "")
                tool_args = call.get("args", {})
                tool_cls = ToolRegistry.get(tool_name)
                if tool_cls:
                    result = tool_cls.execute(entity_id, tool_args, context)
                    results.append(result)
                else:
                    results.append({"message": "未知工具: %s" % tool_name})

            # 构建反馈消息
            feedback_parts = []
            for i, call in enumerate(tool_calls):
                tool_name = call.get("name", "")
                result = results[i] if i < len(results) else {"message": ""}
                msg = result.get("message", "")
                if msg:
                    feedback_parts.append("[%s] %s" % (tool_name, msg))

            if not feedback_parts:
                return

            feedback_msg = "工具执行结果：\n" + "\n".join(feedback_parts)

            # 把反馈加入对话历史作为用户消息
            conv.add_user_message(feedback_msg)

            # 重新调 Bridge，让 AI 基于工具结果继续推理
            # feedback_rounds 递减后传给 _on_reply，为 0 时不再触发反馈
            conv.call_bridge(feedback_msg,
                             lambda reply: self._on_reply(player_id, reply, conv, feedback_msg, feedback_rounds))

        except Exception as e:
            print("===== _execute_tools_with_feedback 出错: %s =====" % str(e))

    def _clear_pending_tools(self, entity_id):
        """清除队列中指定实体的待执行工具"""
        try:
            kept = []
            removed = 0
            for item in self._result_queue:
                # __tool__: (tag, eid, calls, pid)
                # __tool_feedback__: (tag, eid, calls, pid, conv, rounds)
                if len(item) >= 2 and item[0] in ("__tool__", "__tool_feedback__") and item[1] == entity_id:
                    removed += 1
                else:
                    kept.append(item)
            self._result_queue = kept
            if removed:
                print("[_clear_pending_tools] 清除了 %d 个待执行工具" % removed)
        except Exception as e:
            print("===== _clear_pending_tools 出错: %s =====" % str(e))

    MAX_LINES_PER_MSG = 10

    @staticmethod
    def _split_message(message):
        """将长消息按行数分段，每段最多 MAX_LINES_PER_MSG 行"""
        lines = message.split("\n")
        chunks = []
        for i in range(0, len(lines), LLMServerSystem.MAX_LINES_PER_MSG):
            chunks.append("\n".join(lines[i:i + LLMServerSystem.MAX_LINES_PER_MSG]))
        return chunks

    def _SendChatMessage(self, player_name, message):
        """模拟玩家发送全服聊天消息，显示为 <玩家名> 内容"""
        try:
            msg_comp = serverApi.GetEngineCompFactory().CreateMsg(serverApi.GetLevelId())
            for chunk in self._split_message(message):
                msg_comp.SendMsg(player_name, chunk)
        except Exception as e:
            print("===== _SendChatMessage 出错: %s =====" % str(e))

    def _BroadcastMessage(self, message):
        """向所有在线玩家广播消息（复用已验证的客户端事件流程）"""
        try:
            for chunk in self._split_message(message):
                player_list = serverApi.GetPlayerList()
                for pid in player_list:
                    self._NotifyPlayer(pid, chunk)
        except Exception as e:
            print("===== _BroadcastMessage 出错: %s =====" % str(e))

    def _NotifyPlayer(self, player_id, message):
        """通过客户端事件发送消息"""
        try:
            if player_id:
                event_data = self.CreateEventData()
                event_data["message"] = message
                self.NotifyToClient(player_id, "LLMReplyEvent", event_data)
        except Exception as e:
            print("===== _NotifyPlayer 出错: %s =====" % str(e))

    def _OnShowChat(self, args):
        """客户端回传真实 playerId，用 NotifyOneMessage 显示聊天栏（自动分段）"""
        try:
            real_player_id = args.get("playerId", "")
            message = args.get("message", "")
            if real_player_id and message:
                msg_comp = serverApi.GetEngineCompFactory().CreateMsg(real_player_id)
                if msg_comp:
                    for chunk in self._split_message(message):
                        msg_comp.NotifyOneMessage(real_player_id, chunk)
        except Exception as e:
            print("===== _OnShowChat 出错: %s =====" % str(e))
