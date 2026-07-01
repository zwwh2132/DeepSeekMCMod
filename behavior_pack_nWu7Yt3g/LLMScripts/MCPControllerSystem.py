# -*- coding: utf-8 -*-
"""
MCPControllerSystem — MC 控制端系统

完全独立于 NPC 对话系统（LLMServerSystem），不导入任何 NPC 相关模块。
只负责：监听 TCP 端口 → 接收 JSON 命令 → 直接执行 MC 指令。

通信协议：
  [4字节大端长度][JSON数据]

请求类型：
  {"type": "ping"}                          → 心跳
  {"type": "list_tools"}                    → 列出可用工具
  {"type": "execute_command", "command": "time set 6000"}  → 直接执行指令

响应格式：
  {"status": "ok", "message": "..."}
  {"status": "ok", "type": "tool_list", "tools": [...]}
"""
import json
import socket
import struct
import threading
import sys
import os
import mod.server.extraServerApi as serverApi


class _TeeStream(object):
    """同时写入文件和控制台的流分流器"""
    def __init__(self, file, orig):
        self._file = file
        self._orig = orig

    def write(self, data):
        self._file.write(data)
        self._orig.write(data)

    def flush(self):
        self._file.flush()
        if hasattr(self._orig, 'flush'):
            self._orig.flush()


class MCPControllerSystem(serverApi.GetServerSystemCls()):
    """MCP 控制器系统 — 独立系统，不依赖 NPC 模块"""

    # ==================== 系统工具定义 ====================
    # 所有可用的 MCP 工具，硬编码在此，不依赖任何外部模块
    SYSTEM_TOOLS = [
        {
            "name": "mc_execute",
            "description": "执行任意 MC 游戏指令（完全权限），如 give、tp、summon、time、weather、kill、effect、setblock 等。注意：指令含中文时 MCP 层可能编码出错，此时请改用 mc_inject_python 传入 \\uXXXX 转义的 Python 代码来执行 SetCommand",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "要执行的指令，不需要加 / 前缀，例: give @p diamond 10。含中文时需改用 mc_inject_python"}
                },
                "required": ["command"]
            }
        },
        {
            "name": "mc_time_set",
            "description": "设置游戏时间（0=黎明, 1000=早晨, 6000=中午, 12000=夜晚, 18000=午夜）",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "time": {"type": "number", "description": "游戏刻时间 (0~24000)"}
                },
                "required": ["time"]
            }
        },
        {
            "name": "mc_weather_set",
            "description": "设置天气：clear=晴天, rain=雨天, thunder=雷暴",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "weather": {
                        "type": "string",
                        "description": "天气类型",
                        "enum": ["clear", "rain", "thunder"]
                    }
                },
                "required": ["weather"]
            }
        },
        {
            "name": "mc_summon",
            "description": "在指定位置生成一个实体",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "entity_type": {"type": "string", "description": "实体类型 ID，如 zombie、creeper"},
                    "x": {"type": "number", "description": "X 坐标（默认 0）"},
                    "y": {"type": "number", "description": "Y 坐标（默认 0）"},
                    "z": {"type": "number", "description": "Z 坐标（默认 0）"}
                },
                "required": ["entity_type"]
            }
        },
        {
            "name": "mc_kill",
            "description": "清除指定类型的实体",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "清除目标，如 @e[type=zombie]、@p、@a"}
                },
                "required": ["target"]
            }
        },
        {
            "name": "mc_effect",
            "description": "给玩家或实体添加状态效果",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "effect": {"type": "string", "description": "效果名称，如 speed、strength、regeneration"},
                    "duration": {"type": "number", "description": "持续时间（秒），默认 30"},
                    "amplifier": {"type": "number", "description": "效果等级（0= I级），默认 0"},
                    "target": {"type": "string", "description": "目标，默认 @p"}
                },
                "required": ["effect"]
            }
        },
        {
            "name": "mc_give_item",
            "description": "给指定玩家发放物品（需要 OP 权限）",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "player_name": {"type": "string", "description": "玩家名称"},
                    "item_name": {"type": "string", "description": "物品 ID，如 diamond、minecraft:iron_sword"},
                    "count": {"type": "number", "description": "数量，默认 1"}
                },
                "required": ["player_name", "item_name"]
            }
        },
        {
            "name": "mc_teleport",
            "description": "传送玩家或实体到指定坐标",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "x": {"type": "number", "description": "目标 X 坐标"},
                    "y": {"type": "number", "description": "目标 Y 坐标"},
                    "z": {"type": "number", "description": "目标 Z 坐标"},
                    "target": {"type": "string", "description": "传送目标（玩家名或 @p），默认 @p"}
                },
                "required": ["x", "y", "z"]
            }
        },
        {
            "name": "mc_list_players",
            "description": "列出当前在线的所有玩家",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "mc_inject_python",
            "description": "在模组服务端执行任意 Python 2 代码（完全权限）。可直接调用 serverApi。注意：含中文指令时（如斗蛐蛐指令），请用 \\uXXXX 转义绕过编码限制，参考: cmd=u'\\uXXXX'.encode('utf-8'); comp.SetCommand(cmd, executor, False)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "要执行的 Python 2 代码。中文用 \\uXXXX 转义，例: cmd=u'\\u6597\\u86d0\\u86d0\\u53ec\\u5524...'.encode('utf-8')"}
                },
                "required": ["code"]
            }
        },
        {
            "name": "mc_listen_event",
            "description": "注册监听一个游戏事件，在指定时间内记录事件触发数据。之后用 mc_get_event_records 拉取记录。例: 监听 ProjectileDoHitEffectEvent 看 hitTargetType",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "event": {"type": "string", "description": "事件名称，如 ProjectileDoHitEffectEvent、EntityTickServerEvent、AddEntityServerEvent 等"},
                    "duration": {"type": "number", "description": "监听持续时间（秒），到期自动停止。不传则一直监听到手动停止"},
                    "max_records": {"type": "number", "description": "最大记录条数，超出覆盖旧记录。默认 100，最大 500"},
                    "filters": {
                        "type": "object",
                        "description": "可选过滤器，格式 {\"key\": \"value\"}，只记录匹配的事件。如 {\"hitTargetType\": \"BLOCK\"}",
                        "additionalProperties": {"type": "string"}
                    }
                },
                "required": ["event"]
            }
        },
        {
            "name": "mc_get_event_records",
            "description": "获取事件监听器的触发记录",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "listen_id": {"type": "string", "description": "监听器 ID（mc_listen_event 返回的 listen_id）"},
                    "clear": {"type": "boolean", "description": "获取后是否清除记录。默认 true"}
                },
                "required": ["listen_id"]
            }
        },
        {
            "name": "mc_stop_listen",
            "description": "停止并销毁一个事件监听器，释放资源",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "listen_id": {"type": "string", "description": "监听器 ID"}
                },
                "required": ["listen_id"]
            }
        }
    ]

    _TOOL_MAP = {t["name"]: t for t in SYSTEM_TOOLS}

    def __init__(self, namespace, name):
        super(MCPControllerSystem, self).__init__(namespace, name)
        print("===== MCPControllerSystem 初始化 =====")

        # 日志捕获 — 同时写入文件和控制台（不干扰原始输出）
        try:
            # 使用相对路径，基于项目根目录
            log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "mc_tools", "mc_mod_log.txt")
            self._log_file = open(log_path, "a", 1)  # 行缓冲，减少磁盘写入
            self._log_file.write("\n===== MCPControllerSystem START =====\n")
            self._log_file.flush()
            # stdout + stderr 分流：同时写文件和原始流
            sys.stdout = _TeeStream(self._log_file, sys.stdout)
            sys.stderr = _TeeStream(self._log_file, sys.stderr)
            # 启用官方日志 API（手机端可用）
            try:
                serverApi.SetMcpModLogCanPostDump(True)
            except Exception:
                pass
        except Exception as e:
            print("[MCPController] 日志设置失败: %s" % str(e))
            self._log_file = None

        self._server = None
        self._running = False
        self._thread = None

        # 命令队列 + 结果存储：TCP 线程放，主线程 OnTick 执行
        self._cmd_queue = []  # [{"conn": conn, "request": data, "event": Event}]
        self._pending_results = {}  # {conn_fileno: result}
        self._queue_lock = threading.Lock()

        # 事件监听器系统
        self._event_listeners = {}    # {listen_id: listener_dict}
        self._event_handlers = {}     # {listen_id: handler_func} — 保存闭包引用用于取消注册
        self._listen_counter = 0      # 自增 ID 生成器
        self._tick_count = 0          # tick 计数器，用于超时判断

        # 注册 Tick 事件（主线程执行命令）
        self.ListenForEvent(
            serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
            "OnScriptTickServer", self, self._OnTick
        )

        # 启动 TCP 监听
        self._start_listener()

        print("===== MCPControllerSystem 初始化完成 =====")

    # ==================== TCP 监听器 ====================

    def _start_listener(self):
        """启动 TCP 监听（后台线程）"""
        self._running = True
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind(("127.0.0.1", 19997))
        self._server.listen(1)
        self._server.settimeout(2.0)
        print("[MCPController] 监听 127.0.0.1:19997")

        self._thread = threading.Thread(target=self._serve_loop, name="MCPController")
        self._thread.daemon = True
        self._thread.start()

    def _serve_loop(self):
        """监听循环"""
        while self._running:
            try:
                server = self._server
                if server is None:
                    break
                conn, addr = server.accept()
                self._handle_connection(conn)
            except socket.timeout:
                continue
            except Exception as e:
                # Bad file descriptor 是脚本重载时 socket 被关闭的正常现象，不打印
                if self._running and "Bad file descriptor" not in str(e):
                    print("[MCPController] accept 出错: %s" % str(e))

    def _handle_connection(self, conn):
        """处理单个连接：在后台线程中接收请求，放入队列等主线程处理"""
        try:
            conn.settimeout(60)
            raw_len = self._recv_exact(conn, 4)
            if not raw_len:
                return
            msg_len = struct.unpack(">I", raw_len)[0]
            if msg_len <= 0 or msg_len > 1048576:
                return

            raw_data = self._recv_exact(conn, msg_len)
            if not raw_data:
                return

            data = self._convert_unicode_to_str(json.loads(raw_data.decode("utf-8")))

            # 不需要主线程处理的命令（ping、list_tools）
            if data.get("type") in ("ping", "list_tools"):
                result = self._process(data)
                resp = json.dumps(result, ensure_ascii=True).encode("utf-8")
                conn.sendall(struct.pack(">I", len(resp)))
                conn.sendall(resp)
                return

            # 需要主线程执行的命令 → 放入队列等待 OnTick 处理
            fd = conn.fileno()
            self._pending_results[fd] = None
            event = threading.Event()
            with self._queue_lock:
                self._cmd_queue.append({
                    "conn": conn,
                    "request": data,
                    "event": event
                })
            # 等主线程处理（最多 5 秒）
            event.wait(5)

            # 取结果
            result = self._pending_results.pop(fd, None)
            if result is None:
                result = {"status": "error", "message": "处理超时"}
            resp = json.dumps(result, ensure_ascii=True).encode("utf-8")
            try:
                conn.sendall(struct.pack(">I", len(resp)))
                conn.sendall(resp)
            except Exception:
                pass

        except Exception as e:
            print("[MCPController] 处理出错: %s" % str(e))
        finally:
            try:
                conn.close()
            except Exception:
                pass
            # 清理残留记录
            self._pending_results.pop(conn.fileno(), None)
            with self._queue_lock:
                self._cmd_queue = [item for item in self._cmd_queue if item["conn"] != conn]

    def _OnTick(self, args=None):
        """主线程 Tick：处理命令队列 + 管理过期监听器（记录保留 30 秒以便拉取）"""
        self._tick_count += 1

        # Phase 1: 标记过期 + 取消注册 handler（记录保留在 _event_listeners 中）
        for lid, lst in self._event_listeners.items():
            if not lst.get("expired") and lst.get("duration_ticks") and \
               (self._tick_count - lst["start_tick"]) >= lst["duration_ticks"]:
                lst["expired"] = True
                lst["gc_tick"] = self._tick_count + 900  # 再过 30 秒彻底清理
                self._unregister_handler(lid)

        # Phase 2: 彻底清理超过保留期的监听器
        gc_list = [lid for lid, lst in self._event_listeners.items()
                   if lst.get("expired") and lst.get("gc_tick") and self._tick_count >= lst["gc_tick"]]
        for lid in gc_list:
            self._gc_listener(lid)

        try:
            with self._queue_lock:
                items = list(self._cmd_queue)
                self._cmd_queue = []

            for item in items:
                fd = item["conn"].fileno()
                try:
                    result = self._process(item["request"])
                    if fd in self._pending_results:
                        self._pending_results[fd] = result
                    item["event"].set()
                except Exception as e:
                    if fd in self._pending_results:
                        self._pending_results[fd] = {"status": "error", "message": str(e)}
                    item["event"].set()
        except Exception as e:
            print("[MCPController] OnTick 出错: %s" % str(e))

    @staticmethod
    def _recv_exact(conn, size):
        chunks = []
        remaining = size
        while remaining > 0:
            chunk = conn.recv(remaining)
            if not chunk:
                return None
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    @staticmethod
    def _convert_unicode_to_str(obj):
        """递归将 unicode 转为 str（Python 2 的 json.loads 产出 unicode，部分 API 需要 str）
        
        注意：Python 2 的 str(unicode) 默认用 ascii 编码，中文字符会 UnicodeEncodeError。
        因此改用 encode('utf-8')，确保中文指令/参数能正确传递到 SDK API。
        """
        if isinstance(obj, dict):
            return {MCPControllerSystem._convert_unicode_to_str(k): MCPControllerSystem._convert_unicode_to_str(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [MCPControllerSystem._convert_unicode_to_str(item) for item in obj]
        elif isinstance(obj, unicode):
            return obj.encode('utf-8')
        return obj

    # ==================== 命令处理 ====================

    def _process(self, data):
        """处理 JSON 命令"""
        cmd_type = data.get("type", "")

        if cmd_type == "ping":
            return {"status": "ok", "type": "pong"}

        if cmd_type == "list_tools":
            return {"status": "ok", "type": "tool_list", "tools": self.SYSTEM_TOOLS}

        if cmd_type == "execute_command":
            return self._execute_command(data.get("command", ""))

        # 通过 tool 名调用
        tool_name = data.get("tool", "")
        if tool_name:
            return self._call_tool(tool_name, data.get("args", {}))

        return {"status": "error", "message": "未知命令类型"}

    def _call_tool(self, tool_name, args):
        """按工具名执行"""
        # 安全处理：Trae 内置 MCP 客户端可能把 args 当字符串传
        if not isinstance(args, dict):
            try:
                args = json.loads(args) if isinstance(args, basestring) else {}
            except (ValueError, TypeError):
                args = {}
        if not isinstance(args, dict):
            args = {}
        if tool_name == "mc_execute":
            return self._execute_command(args.get("command", ""))

        elif tool_name == "mc_time_set":
            return self._execute_command("time set %d" % int(args.get("time", 0)))

        elif tool_name == "mc_weather_set":
            return self._execute_command("weather %s" % args.get("weather", "clear"))

        elif tool_name == "mc_summon":
            etype = args.get("entity_type", "")
            x = int(args.get("x", 0))
            y = int(args.get("y", 0))
            z = int(args.get("z", 0))
            return self._execute_command("summon %s %d %d %d" % (etype, x, y, z))

        elif tool_name == "mc_kill":
            return self._execute_command("kill %s" % args.get("target", "@e[type=!player]"))

        elif tool_name == "mc_effect":
            eff = args.get("effect", "")
            duration = int(args.get("duration", 30))
            amp = int(args.get("amplifier", 0))
            target = args.get("target", "@p")
            return self._execute_command("effect %s %s %d %d" % (target, eff, duration, amp))

        elif tool_name == "mc_give_item":
            player = args.get("player_name", "@p")
            item = args.get("item_name", "")
            count = int(args.get("count", 1))
            return self._execute_command("give %s %s %d" % (player, item, count))

        elif tool_name == "mc_teleport":
            target = args.get("target", "@p")
            x = int(args.get("x", 0))
            y = int(args.get("y", 0))
            z = int(args.get("z", 0))
            return self._execute_command("tp %s %d %d %d" % (target, x, y, z))

        elif tool_name == "mc_list_players":
            return self._execute_command("list")

        elif tool_name == "mc_inject_python":
            return self._execute_python(args.get("code", ""))

        elif tool_name == "mc_listen_event":
            return self._listen_event_start(args)
        elif tool_name == "mc_get_event_records":
            return self._get_event_records(
                args.get("listen_id", ""),
                args.get("clear", True)
            )
        elif tool_name == "mc_stop_listen":
            return self._stop_listener(args.get("listen_id", ""))

        return {"status": "error", "message": "未知工具: %s" % tool_name}

    def _execute_python(self, code):
        """在模组服务端执行任意 Python 代码"""
        import sys
        from StringIO import StringIO
        try:
            old_stdout = sys.stdout
            sys.stdout = buffer = StringIO()
            exec(code, {"serverApi": serverApi, "GetPlayerList": serverApi.GetPlayerList})
            sys.stdout = old_stdout
            raw = buffer.getvalue()
            # Python 2 的 str 可能是 utf-8 编码的字节，安全转成 unicode
            if isinstance(raw, str):
                raw = raw.decode("utf-8", errors="replace")
            output = raw.strip()
            if output:
                return {"status": "ok", "message": output}
            return {"status": "ok", "message": "代码已执行，无输出"}
        except Exception as e:
            return {"status": "error", "message": "执行出错: %s" % str(e)}
        finally:
            sys.stdout = old_stdout

    def _execute_command(self, command):
        """执行 MC 指令（数据已在入口处由 _convert_unicode_to_str 处理过）"""
        try:
            if not command:
                return {"status": "error", "message": "指令不能为空"}
            if not command.startswith("/"):
                command = "/" + command
            cmd_comp = serverApi.GetEngineCompFactory().CreateCommand(serverApi.GetLevelId())

            player_list = serverApi.GetPlayerList()
            executor = player_list[0] if player_list else ""
            if executor:
                result = cmd_comp.SetCommand(command, executor, False)
            else:
                result = cmd_comp.SetCommand(command)

            if result:
                return {"status": "ok", "message": "指令已执行: %s" % command}
            return {"status": "error", "message": "指令执行失败: %s" % command}
        except Exception as e:
            print("[MCPController] 执行指令出错: %s" % str(e))
            return {"status": "error", "message": "执行失败: %s" % str(e)}

    # ==================== 事件监听器系统 ====================

    def _listen_event_start(self, args):
        """启动一个事件监听器，注册 ListenForEvent 并返回 listen_id"""
        event_name = args.get("event", "")
        if not event_name:
            return {"status": "error", "message": "事件名称不能为空"}

        duration = args.get("duration", 0)  # 秒，0=一直监听
        max_records = min(int(args.get("max_records", 100)), 500)
        filters = args.get("filters", {})

        # 生成唯一 ID
        self._listen_counter += 1
        listen_id = "evt_%03d" % self._listen_counter

        ns = serverApi.GetEngineNamespace()
        sys = serverApi.GetEngineSystemName()

        # 创建事件处理函数并设为实例属性（SDK 通过 func.__name__ 在实例上查找 handler，所以函数名=属性名）
        attr_name = "_evt_%s" % listen_id
        def _handler(event_args=None):
            listener = self._event_listeners.get(listen_id)
            if not listener:
                return
            if self._match_filters(event_args, listener.get("filters", {})):
                record = {
                    "tick": self._tick_count,
                    "data": self._serialize_args(event_args)
                }
                listener["records"].append(record)
                if len(listener["records"]) > listener.get("max_records", 100):
                    listener["records"] = listener["records"][-listener["max_records"]:]
        _handler.__name__ = attr_name
        setattr(self, attr_name, _handler)
        callback = getattr(self, attr_name)

        # 注册事件监听
        try:
            self.ListenForEvent(ns, sys, event_name, self, callback)
        except Exception as e:
            return {"status": "error", "message": "注册事件监听失败: %s" % str(e)}

        # 存储状态
        duration_ticks = int(duration * 30) if duration > 0 else 0  # 30 tick/s
        gc_ticks = duration_ticks + 900 if duration > 0 else 0  # 过期后再保留 30 秒（900 tick）
        self._event_listeners[listen_id] = {
            "event": event_name,
            "filters": filters,
            "records": [],
            "max_records": max_records,
            "duration_ticks": duration_ticks,
            "start_tick": self._tick_count,
            "expired": False,
            "gc_tick": gc_ticks,
        }
        self._event_handlers[listen_id] = callback  # 保存引用用于取消注册

        detail = "事件: %s" % event_name
        if filters:
            detail += ", 过滤器: %s" % str(filters)
        if duration > 0:
            detail += ", 时长: %.1f秒" % duration
        detail += ", 最大记录: %d" % max_records

        return {"status": "ok", "type": "listener_started", "listen_id": listen_id, "message": detail}

    def _get_event_records(self, listen_id, clear=True):
        """获取监听器记录（过期监听器仍可查询，30 秒内有效）"""
        if not listen_id:
            return {"status": "error", "message": "listen_id 不能为空"}
        listener = self._event_listeners.get(listen_id)
        if not listener:
            return {"status": "error", "message": "未找到监听器: %s" % listen_id}

        records = list(listener["records"])
        if clear:
            listener["records"] = []

        return {
            "status": "ok",
            "type": "event_records",
            "listen_id": listen_id,
            "event": listener["event"],
            "expired": listener.get("expired", False),
            "count": len(records),
            "records": records
        }

    def _unregister_handler(self, listen_id):
        """仅取消注册事件 handler，保留记录不删除"""
        handler = self._event_handlers.get(listen_id)
        listener = self._event_listeners.get(listen_id)
        if not handler or not listener:
            return
        try:
            ns = serverApi.GetEngineNamespace()
            sys = serverApi.GetEngineSystemName()
            self.UnListenForEvent(ns, sys, listener["event"], self, handler)
        except Exception as e:
            print("[MCPController] 取消监听失败: %s" % str(e))
        # 清理实例属性上的 handler 引用
        attr_name = "_evt_%s" % listen_id
        if hasattr(self, attr_name):
            delattr(self, attr_name)

    def _gc_listener(self, listen_id):
        """彻底清理过期监听器（记录已被拉取或超时丢弃）"""
        self._event_listeners.pop(listen_id, None)
        self._event_handlers.pop(listen_id, None)

    def _stop_listener(self, listen_id):
        """手动停止并立即销毁监听器（不保留记录）"""
        if not listen_id:
            return {"status": "error", "message": "listen_id 不能为空"}
        listener = self._event_listeners.get(listen_id)
        if not listener:
            return {"status": "error", "message": "未找到监听器: %s" % listen_id}
        self._unregister_handler(listen_id)
        self._gc_listener(listen_id)
        return {"status": "ok", "message": "已停止监听: %s (%s)" % (listener["event"], listen_id)}

    @staticmethod
    def _match_filters(args, filters):
        """检查事件参数是否匹配过滤器。过滤器为空则全匹配。"""
        if not filters:
            return True
        for key, expected in filters.items():
            actual = args.get(key)
            if actual is None and key not in args:
                return False
            # 按字符串比较，兼容 int/str/unicode
            if str(actual) != str(expected):
                return False
        return True

    @staticmethod
    def _serialize_args(args):
        """递归将事件参数转为 JSON 可序列化格式"""
        if isinstance(args, dict):
            return {k: MCPControllerSystem._serialize_args(v) for k, v in args.items()}
        elif isinstance(args, (list, tuple)):
            return [MCPControllerSystem._serialize_args(v) for v in args]
        elif isinstance(args, (int, float, bool, str, unicode, type(None))):
            return args
        else:
            return str(args)
