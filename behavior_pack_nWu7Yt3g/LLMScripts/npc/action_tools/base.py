# -*- coding: utf-8 -*-
"""
ActionTool 基类
所有行为工具必须继承 ActionTool 并实现：
  - name: 工具唯一标识
  - description: 供 LLM 理解用途
  - parameters: 参数 schema（类 MCP 格式）
  - execute(cls, entityId, params, context): 执行行为
"""


class ActionTool(object):
    """行为工具基类"""

    name = ""
    description = ""
    parameters = {
        "type": "object",
        "properties": {},
        "required": []
    }

    @classmethod
    def execute(cls, entityId, params, context=None):
        """执行行为
        Args:
            entityId: NPC 实体的 entityId
            params: 参数字典，按 parameters schema 校验后的值
            context: 可选上下文 dict，如 {"playerId": "...", "levelId": "..."}
        Returns:
            dict: {"status": "ok"/"error", "message": "..."}
        """
        raise NotImplementedError
