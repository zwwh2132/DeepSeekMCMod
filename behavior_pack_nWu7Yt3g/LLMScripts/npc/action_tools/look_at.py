# -*- coding: utf-8 -*-
"""
look_at: 让 NPC 看向某个方向
"""
import mod.server.extraServerApi as serverApi
from .base import ActionTool
from .tool_registry import ToolRegistry


class LookAtAction(ActionTool):
    name = "look_at"
    description = "让NPC看向指定方向（俯仰角/偏转角）"
    parameters = {
        "type": "object",
        "properties": {
            "pitch": {"type": "number", "description": "俯仰角(-90~90)，负值向上看"},
            "yaw": {"type": "number", "description": "偏转角(0~360)"}
        },
        "required": ["yaw"]
    }

    @classmethod
    def execute(cls, entityId, params, context=None):
        rotComp = serverApi.GetEngineCompFactory().CreateRot(entityId)
        pitch = params.get("pitch", 0)
        yaw = params.get("yaw", 0)
        rotComp.SetRot((pitch, yaw))
        return {"status": "ok", "message": "看向方向 (pitch=%.1f, yaw=%.1f)" % (pitch, yaw)}


ToolRegistry.register(LookAtAction)
