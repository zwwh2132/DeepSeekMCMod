# -*- coding: utf-8 -*-
"""
get_pos: 获取 NPC 自身或指定目标的坐标位置
支持：
  - 不传参数 → 获取自己坐标
  - target=玩家名 → 按名字查找玩家
  - target=实体ID → 按ID查找任意实体
"""
import mod.server.extraServerApi as serverApi
from .base import ActionTool
from .tool_registry import ToolRegistry


class GetPosAction(ActionTool):
    name = "get_pos"
    description = "获取NPC自身或指定目标的坐标位置（目标可以是玩家名或实体ID）"
    parameters = {
        "type": "object",
        "properties": {
            "target": {"type": "string", "description": "可选，要查询的目标：玩家名字或实体ID。不传则返回自己的坐标"}
        },
        "required": []
    }

    @classmethod
    def execute(cls, entityId, params, context=None):
        target = params.get("target", "").strip()

        if not target:
            # 查自己
            pos_comp = serverApi.GetEngineCompFactory().CreatePos(entityId)
            pos = pos_comp.GetFootPos()
            if pos:
                return {"status": "ok", "message": "当前坐标: x=%.1f, y=%.1f, z=%.1f" % pos[:3]}
            return {"status": "error", "message": "无法获取坐标"}

        target_id = None

        # 先尝试当玩家名查找
        player_list = serverApi.GetPlayerList()
        for pid in player_list:
            name_comp = serverApi.GetEngineCompFactory().CreateName(pid)
            if name_comp.GetName() == target:
                target_id = pid
                break

        # 没找到就当实体ID直接用
        if not target_id:
            target_id = target

        pos_comp = serverApi.GetEngineCompFactory().CreatePos(target_id)
        pos = pos_comp.GetFootPos()
        if pos:
            return {"status": "ok", "message": "「%s」的坐标: x=%.1f, y=%.1f, z=%.1f" % (target, pos[0], pos[1], pos[2])}
        return {"status": "error", "message": "未找到目标「%s」或无法获取坐标" % target}


ToolRegistry.register(GetPosAction)
