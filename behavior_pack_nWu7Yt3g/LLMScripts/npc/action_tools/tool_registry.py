# -*- coding: utf-8 -*-
"""
工具注册中心 + MCP 风格工具 Schema 生成 + 响应解析器
"""

import json
import re


class ToolRegistry(object):
    """工具注册中心"""
    _tools = {}  # {name: ActionTool 类}

    @classmethod
    def register(cls, tool_cls):
        """注册一个工具类"""
        if not tool_cls.name:
            print("[ToolRegistry] 跳过注册空名称的工具: %s" % tool_cls.__name__)
            return
        cls._tools[tool_cls.name] = tool_cls
        print("[ToolRegistry] 已注册工具: %s" % tool_cls.name)

    @classmethod
    def get(cls, name):
        """按名称获取工具类"""
        return cls._tools.get(name)

    @classmethod
    def get_all(cls):
        """获取所有已注册工具"""
        return dict(cls._tools)

    @classmethod
    def get_tools_mcp_schema(cls):
        """生成 OpenAI function calling 格式的工具定义列表
        返回格式:
        [
            {
                "type": "function",
                "function": {
                    "name": "move_to",
                    "description": "让NPC移动到...",
                    "parameters": {...}  // JSON Schema
                }
            },
            ...
        ]
        """
        tools = []
        for name, tool in sorted(cls._tools.items()):
            tools.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool.description,
                    "parameters": tool.parameters
                }
            })
        return tools

    @classmethod
    def get_tools_description(cls):
        """生成供 LLM 使用的工具描述文本（备用，MCP 模式下已不需要）"""
        if not cls._tools:
            return ""

        lines = []
        lines.append("[可用工具列表]")
        for name, tool in sorted(cls._tools.items()):
            lines.append("  - %s: %s" % (name, tool.description))
            props = tool.parameters.get("properties", {})
            if props:
                params_desc = []
                for pname, pinfo in props.items():
                    required = "必填" if pname in tool.parameters.get("required", []) else "可选"
                    ptype = pinfo.get("type", "any")
                    pdesc = pinfo.get("description", "")
                    params_desc.append("    %s (%s, %s): %s" % (pname, ptype, required, pdesc))
                lines.extend(params_desc)
        return "\n".join(lines)


class BridgeResponseParser(object):
    """解析 Bridge 返回的 JSON 响应（MCP 格式）"""

    @classmethod
    def parse(cls, reply):
        """解析 Bridge 返回的 JSON 字符串
        Bridge 返回格式:
        {
            "text": "回复文本内容",
            "tool_calls": [
                {"name": "move_to", "args": {"x": 100, "z": 200}},
                ...
            ]
        }
        Returns:
            dict: {"text": str, "tool_calls": [{"name":..., "args":{...}}, ...]}
        """
        try:
            data = json.loads(reply)
        except (ValueError, TypeError):
            # 非 JSON 格式，当作纯文本
            return {"text": reply.strip(), "tool_calls": []}

        text = data.get("text", "")
        tool_calls = data.get("tool_calls", [])

        return {
            "text": text.strip(),
            "tool_calls": tool_calls
        }
