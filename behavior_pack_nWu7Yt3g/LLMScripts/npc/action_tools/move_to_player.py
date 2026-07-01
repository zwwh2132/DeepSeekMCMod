# -*- coding: utf-8 -*-
"""
move_to_player: 让 NPC 移动到指定玩家身边（距离过远时自动传送）
"""
import math
import mod.server.extraServerApi as serverApi
from .base import ActionTool
from .tool_registry import ToolRegistry

TELEPORT_THRESHOLD = 30  # 超过此距离直接传送


class MoveToPlayerAction(ActionTool):
    name = "move_to_player"
    description = "让NPC移动到某个玩家的位置，距离超过30格时自动传送"
    parameters = {
        "type": "object",
        "properties": {
            "speed": {"type": "number", "description": "移动速度(0.5~2.0)，默认1.0"},
            "stop_distance": {"type": "number", "description": "停止距离，默认2格"}
        },
        "required": []
    }

    @classmethod
    def execute(cls, entityId, params, context=None):
        playerId = (context or {}).get("playerId")
        if not playerId:
            return {"status": "error", "message": "缺少玩家上下文"}

        posComp = serverApi.GetEngineCompFactory().CreatePos(playerId)
        playerPos = posComp.GetPos()
        if not playerPos:
            return {"status": "error", "message": "无法获取玩家位置"}

        npcPosComp = serverApi.GetEngineCompFactory().CreatePos(entityId)
        npcPos = npcPosComp.GetPos()
        if not npcPos:
            return {"status": "error", "message": "无法获取NPC位置"}

        dist = math.sqrt((playerPos[0] - npcPos[0]) ** 2 +
                         (playerPos[1] - npcPos[1]) ** 2 +
                         (playerPos[2] - npcPos[2]) ** 2)

        if dist > TELEPORT_THRESHOLD:
            # 距离太远，直接传送到玩家旁边
            tp_x = playerPos[0]
            tp_y = playerPos[1]
            tp_z = playerPos[2]
            npcPosComp.SetPos((tp_x, tp_y, tp_z))
            return {"status": "ok", "message": "距离%.0f格过远，已传送到玩家身边" % dist}

        comp = serverApi.GetEngineCompFactory().CreateMoveTo(entityId)
        speed = params.get("speed", 1.0)
        comp.SetMoveSetting((playerPos[0], -1, playerPos[2]), speed, 500, None)
        return {"status": "ok", "message": "距离%.0f格，正在向玩家移动" % dist}


ToolRegistry.register(MoveToPlayerAction)
