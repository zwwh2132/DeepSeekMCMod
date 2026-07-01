# -*- coding: utf-8 -*-
"""
stop: 让 NPC 停止当前所有动作
"""
import mod.server.extraServerApi as serverApi
from .base import ActionTool
from .tool_registry import ToolRegistry


class StopAction(ActionTool):
    name = "stop"
    description = "让NPC停止当前所有动作（移动、跟随等）"
    parameters = {
        "type": "object",
        "properties": {},
        "required": []
    }

    @classmethod
    def execute(cls, entityId, params, context=None):
        # 清除所有持续模式（跟随、攻击等）
        extra = serverApi.GetEngineCompFactory().CreateExtraData(entityId)
        extra.SetExtraData("follow_target_player", "")
        extra.SetExtraData("attack_target_id", "")
        extra.SetExtraData("attack_target_name", "")
        extra.SetExtraData("attack_damage", "")

        # 停止运动
        motionComp = serverApi.GetEngineCompFactory().CreateActorMotion(entityId)
        motionComp.SetMotion((0, 0, 0))

        return {"status": "ok", "message": "已停止所有动作（跟随、攻击等）"}


ToolRegistry.register(StopAction)
