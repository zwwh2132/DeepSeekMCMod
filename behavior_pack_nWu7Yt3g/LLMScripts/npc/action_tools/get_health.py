# -*- coding: utf-8 -*-
"""
get_health: 获取 NPC 自身、指定玩家或指定 NPC 的生命值
"""
import mod.server.extraServerApi as serverApi
from .base import ActionTool
from .tool_registry import ToolRegistry
from LLMScripts.npc.NPCManager import NPCManager


class GetHealthAction(ActionTool):
    name = "get_health"
    description = "获取NPC自身、指定玩家或指定NPC的生命值。传 player_name 查玩家，传 npc_name 查NPC，都不传查自己"
    parameters = {
        "type": "object",
        "properties": {
            "player_name": {"type": "string", "description": "可选，要查询的玩家名字"},
            "npc_name": {"type": "string", "description": "可选，要查询的NPC显示名字（如「战士」、「老村民」）"}
        },
        "required": []
    }

    @classmethod
    def execute(cls, entityId, params, context=None):
        player_name = params.get("player_name", "").strip()
        npc_name = params.get("npc_name", "").strip()

        target_id = None

        # 优先查玩家
        if player_name:
            player_list = serverApi.GetPlayerList()
            for pid in player_list:
                name_comp = serverApi.GetEngineCompFactory().CreateName(pid)
                if name_comp.GetName() == player_name:
                    target_id = pid
                    break
            if not target_id:
                return {"status": "error", "message": "未找到玩家「%s」" % player_name}
        # 其次查 NPC
        elif npc_name:
            resolved = NPCManager.resolve_name(npc_name)
            if not resolved:
                return {"status": "error", "message": "未找到名字为「%s」的NPC" % npc_name}
            target_id = resolved
        else:
            # 都不传，查自己
            target_id = entityId

        attr_comp = serverApi.GetEngineCompFactory().CreateAttr(target_id)
        mc_enum = serverApi.GetMinecraftEnum()
        current = attr_comp.GetAttrValue(mc_enum.AttrType.HEALTH)
        if current is not None:
            if player_name:
                return {"status": "ok", "message": "玩家%s的生命值: %.1f" % (player_name, current)}
            elif npc_name:
                return {"status": "ok", "message": "NPC%s的生命值: %.1f" % (npc_name, current)}
            return {"status": "ok", "message": "当前生命值: %.1f" % current}
        return {"status": "error", "message": "无法获取生命值"}


ToolRegistry.register(GetHealthAction)
