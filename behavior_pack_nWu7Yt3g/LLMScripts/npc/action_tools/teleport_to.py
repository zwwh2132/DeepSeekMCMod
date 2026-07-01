# -*- coding: utf-8 -*-
"""
teleport_to: 将 NPC 瞬间传送到指定坐标位置
"""
import mod.server.extraServerApi as serverApi
from .base import ActionTool
from .tool_registry import ToolRegistry


class TeleportToAction(ActionTool):
    name = "teleport_to"
    description = "将NPC瞬间传送到指定坐标位置（相当于tp指令）"
    parameters = {
        "type": "object",
        "properties": {
            "x": {"type": "number", "description": "目标X坐标"},
            "y": {"type": "number", "description": "目标Y坐标（可选，不传则保持当前Y）"},
            "z": {"type": "number", "description": "目标Z坐标"}
        },
        "required": ["x", "z"]
    }

    @classmethod
    def execute(cls, entityId, params, context=None):
        target_x = params.get("x", 0)
        target_z = params.get("z", 0)
        target_y = params.get("y")

        # 如果没传 Y，保持当前 Y
        if target_y is None:
            pos_comp = serverApi.GetEngineCompFactory().CreatePos(entityId)
            current = pos_comp.GetPos()
            if current:
                target_y = current[1]
            else:
                target_y = 0

        pos_comp = serverApi.GetEngineCompFactory().CreatePos(entityId)
        result = pos_comp.SetPos((target_x, target_y, target_z))
        if result:
            return {"status": "ok", "message": "已传送到 (%.1f, %.1f, %.1f)" % (target_x, target_y, target_z)}
        return {"status": "error", "message": "传送失败"}


ToolRegistry.register(TeleportToAction)
