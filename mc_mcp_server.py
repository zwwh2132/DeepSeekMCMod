#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mc_mcp_server.py — Minecraft 控制 MCP Server

通信架构：
  Trae IDE ←[MCP stdio]→ mc_mcp_server.py ←[TCP :19997]→ Minecraft Mod
  
启动方式（配置到 IDE 的 MCP 设置中）：
  py -3 此文件的完整路径/mc_mcp_server.py

或者手动启动测试：
  python mc_mcp_server.py --stdio
"""
import json
import os
import socket
import struct
import sys

# ============================================================
# 配置
# ============================================================
MOD_HOST = "127.0.0.1"
MOD_PORT = 19997
SERVER_NAME = "mc_control"
SERVER_VERSION = "1.0.0"

# 日志文件路径（给 mc_read_log 使用），基于脚本所在目录的相对路径
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MOD_LOG_PATH = os.path.join(_SCRIPT_DIR, "mc_tools", "mc_mod_log.txt")

# ============================================================
# TCP 通信（与 Mod 的 MCPControllerSystem）
# ============================================================

def _send_to_mod(data):
    """通过 TCP 发送命令到模组并接收响应"""
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((MOD_HOST, MOD_PORT))

        payload = json.dumps(data, ensure_ascii=True).encode("utf-8")
        sock.sendall(struct.pack(">I", len(payload)))
        sock.sendall(payload)

        # 读响应长度头
        raw_len = _recv_exact(sock, 4)
        if not raw_len:
            return {"status": "error", "message": "模组无响应"}
        msg_len = struct.unpack(">I", raw_len)[0]
        raw_data = _recv_exact(sock, msg_len)
        if not raw_data:
            return {"status": "error", "message": "模组无响应数据"}
        return json.loads(raw_data.decode("utf-8"))
    except socket.timeout:
        return {"status": "error", "message": "连接模组超时，请确认游戏已启动且模组已加载"}
    except ConnectionRefusedError:
        return {"status": "error", "message": "模组未运行或端口 %d 未监听" % MOD_PORT}
    except socket.error as e:
        return {"status": "error", "message": "无法连接模组 [%s:%d]: %s" % (MOD_HOST, MOD_PORT, e)}
    except Exception as e:
        return {"status": "error", "message": "通信错误: %s" % e}
    finally:
        if sock:
            try:
                sock.close()
            except Exception:
                pass


def _recv_exact(conn, size):
    """精确读取指定字节数"""
    chunks = []
    remaining = size
    while remaining > 0:
        chunk = conn.recv(remaining)
        if not chunk:
            return None
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _fetch_tools():
    """从模组的 MCPControllerSystem 获取工具列表"""
    result = _send_to_mod({"type": "list_tools"})
    if result.get("status") == "ok":
        return result.get("tools", [])
    print("[mc_mcp] 获取工具列表失败: %s" % result.get("message", "未知错误"), file=sys.stderr)
    return []


def _call_tool(tool_name, args):
    """调用模组工具（统一通过 tool 字段）
    
    特别处理 mc_execute：如果 command 参数包含非 ASCII 字符（如中文），
    自动转为 Python 注入方式执行，以绕过 Trae MCP 客户端的 JSON 编码限制。
    """
    # 检测 args 中是否有非 ASCII 字符串
    def _has_non_ascii(obj):
        if isinstance(obj, str):
            return any(ord(c) > 127 for c in obj)
        if isinstance(obj, dict):
            return any(_has_non_ascii(v) for v in obj.values())
        if isinstance(obj, (list, tuple)):
            return any(_has_non_ascii(v) for v in obj)
        return False

    # 如果 mc_execute 的 command 含中文，自动转 mc_inject_python
    if tool_name == "mc_execute" and _has_non_ascii(args):
        cmd = args.get("command", "")
        # 把每个中文字符转为 \uXXXX 转义序列，并转义字符串中的引号和反斜杠
        escaped_parts = []
        for ch in cmd:
            code = ord(ch)
            if ch == "\\":
                escaped_parts.append("\\\\")
            elif ch == "'":
                escaped_parts.append("\\'")
            elif code > 127:
                escaped_parts.append("\\u%04x" % code)
            else:
                escaped_parts.append(ch)
        escaped_str = "".join(escaped_parts)
        # 构造 Python 注入代码（只用了 \uXXXX，全是 ASCII，无注入编码问题）
        py_code = (
            "# coding: utf-8\n"
            "import mod.server.extraServerApi as api\n"
            "c = api.GetEngineCompFactory().CreateCommand(api.GetLevelId())\n"
            "p = api.GetPlayerList()\n"
            "v = u'/%s'\n"
            "if p:\n"
            "    c.SetCommand(v.encode('utf-8'), p[0], False)\n"
            "else:\n"
            "    c.SetCommand(v.encode('utf-8'))\n"
            "print('ok')"
        ) % escaped_str

    return _send_to_mod({
        "tool": tool_name,
        "args": args
    })


def _handle_clear_log():
    """清空日志文件"""
    try:
        open(MOD_LOG_PATH, "w").close()
        return "日志已清空"
    except Exception as e:
        return "清空日志失败: %s" % str(e)


def _handle_read_log(args):
    """读取日志文件（服务端本地工具，不经过模组）"""
    lines = int(args.get("lines", 50))
    if lines < 1:
        lines = 1
    if lines > 500:
        lines = 500
    try:
        if not os.path.exists(MOD_LOG_PATH):
            return "日志文件不存在，请先启动游戏加载模组"
        with open(MOD_LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
        total = len(all_lines)
        start = max(0, total - lines)
        selected = all_lines[start:]
        result = "共 %d 行，显示后 %d 行：\n" % (total, len(selected))
        result += "".join(selected)
        return result
    except Exception as e:
        return "读取日志失败: %s" % str(e)


# ============================================================
# MCP 协议实现（JSON-RPC 2.0 over stdio）
# ============================================================

# 启动时从 MCPControllerSystem 获取工具列表
_TOOLS = []


def _init_tools():
    """从 MCPControllerSystem 获取工具列表，追加服务端本地工具"""
    global _TOOLS
    _TOOLS = _fetch_tools()
    # 追加服务端本地工具（不需要经过模组）
    _TOOLS.append({
        "name": "mc_read_log",
        "description": "读取模组运行日志文件，返回最新 N 行内容，用于排查错误和异常",
        "inputSchema": {
            "type": "object",
            "properties": {
                "lines": {"type": "number", "description": "要读取的行数，从末尾开始数，默认 50"}
            },
            "required": []
        }
    })
    _TOOLS.append({
        "name": "mc_clear_log",
        "description": "清空模组运行日志文件，重新开始记录",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    })
    print("[mc_mcp] 已加载 %d 个工具" % len(_TOOLS), file=sys.stderr)


def _handle_request(request):
    """处理 MCP JSON-RPC 请求"""
    req_id = request.get("id")
    method = request.get("method", "")
    params = request.get("params", {}) or {}

    # initialize
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION}
            }
        }

    # notifications 不需要响应
    if method.startswith("notifications/"):
        return None

    # tools/list
    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": _TOOLS}
        }

    # tools/call
    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})

        # 服务端本地工具（不经过模组）
        if tool_name == "mc_read_log":
            result_text = _handle_read_log(tool_args)
        elif tool_name == "mc_clear_log":
            result_text = _handle_clear_log()
        else:
            mod_result = _call_tool(tool_name, tool_args)
            # 安全处理 mod_result，无论返回什么类型
            if isinstance(mod_result, dict):
                result_text = mod_result.get("message", str(mod_result))
            else:
                result_text = str(mod_result)

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [{"type": "text", "text": result_text}]
            }
        }

    # 未知方法
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": "未知方法: %s" % method}
    }


def _process_line(line):
    """处理单行 JSON 输入"""
    line = line.strip()
    if not line:
        return None
    try:
        request = json.loads(line)
        return _handle_request(request)
    except json.JSONDecodeError:
        return {
            "jsonrpc": "2.0",
            "error": {"code": -32700, "message": "JSON 解析错误"}
        }


def main():
    """主入口：MCP stdio server"""
    # 初始化工具列表
    _init_tools()

    # 标准输入输出模式（MCP 标准）
    # 每行一个 JSON-RPC 消息
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        response = _process_line(line)
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=True) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
