# -*- coding: utf-8 -*-
"""
move_to: 让 NPC 移动到世界中的指定坐标位置
"""
import mod.server.extraServerApi as serverApi
from .base import ActionTool
from .tool_registry import ToolRegistry


class MoveToAction(ActionTool):
    name = "move_to"
    description = "让NPC移动到世界中的指定坐标位置"
    parameters = {
        "type": "object",
        "properties": {
            "x": {"type": "number", "description": "目标X坐标"},
            "z": {"type": "number", "description": "目标Z坐标"},
            "speed": {"type": "number", "description": "移动速度(0.5~2.0)，默认1.0"}
        },
        "required": ["x", "z"]
    }

    @classmethod
    def execute(cls, entityId, params, context=None):
        comp = serverApi.GetEngineCompFactory().CreateMoveTo(entityId)
        targetX = params.get("x", 0)
        targetZ = params.get("z", 0)
        speed = params.get("speed", 1.0)
        comp.SetMoveSetting((targetX, -1, targetZ), speed, 500, None)
        return {"status": "ok", "message": "正在移动到 (%.1f, %.1f)" % (targetX, targetZ)}


ToolRegistry.register(MoveToAction)
