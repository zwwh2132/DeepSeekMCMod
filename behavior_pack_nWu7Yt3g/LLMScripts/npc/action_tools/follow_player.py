# -*- coding: utf-8 -*-
"""
follow_player: 让 NPC 持续跟随某个玩家
"""
import mod.server.extraServerApi as serverApi
from .base import ActionTool
from .tool_registry import ToolRegistry


class FollowPlayerAction(ActionTool):
    name = "follow_player"
    description = "让NPC持续跟随某个玩家移动"
    parameters = {
        "type": "object",
        "properties": {
            "speed": {"type": "number", "description": "跟随速度(0.1~0.5)，默认0.25"},
            "stop_distance": {"type": "number", "description": "停止距离，默认2格"}
        },
        "required": []
    }

    @classmethod
    def execute(cls, entityId, params, context=None):
        """follow 逻辑由行为节点的 Tick() 持续追踪实现，
        这里只是设置跟随状态，Tick() 中会按需导航。
        """
        # 设置 ExtraData 标记为跟随模式，同时清除攻击模式
        extra = serverApi.GetEngineCompFactory().CreateExtraData(entityId)
        extra.SetExtraData("follow_target_player", (context or {}).get("playerId", ""))
        extra.SetExtraData("attack_target_id", "")
        extra.SetExtraData("attack_target_name", "")
        extra.SetExtraData("attack_damage", "")
        return {"status": "ok", "message": "开始跟随玩家"}


ToolRegistry.register(FollowPlayerAction)
