# -*- coding: utf-8 -*-
"""
find_block: 在 NPC 周围一定范围内搜索特定方块的位置
"""
import mod.server.extraServerApi as serverApi
from .base import ActionTool
from .tool_registry import ToolRegistry

MAX_RADIUS = 10
MAX_RESULTS = 50


class FindBlockAction(ActionTool):
    name = "find_block"
    description = "在NPC周围一定范围内搜索特定方块（如chest、furnace等），返回坐标"
    parameters = {
        "type": "object",
        "properties": {
            "block_name": {"type": "string", "description": "要搜索的方块名称（如chest、furnace、diamond_ore等）"},
            "radius": {"type": "number", "description": "搜索半径（格），默认10，最大10"}
        },
        "required": ["block_name"]
    }

    @classmethod
    def execute(cls, entityId, params, context=None):
        block_name = params.get("block_name", "").lower()
        if not block_name:
            return {"status": "error", "message": "请指定要搜索的方块名称"}
        radius = int(min(params.get("radius", 10), MAX_RADIUS))

        pos_comp = serverApi.GetEngineCompFactory().CreatePos(entityId)
        npc_pos = pos_comp.GetPos()
        if not npc_pos:
            return {"status": "error", "message": "无法获取自身位置"}

        dim_comp = serverApi.GetEngineCompFactory().CreateDimension(entityId)
        npc_dim = dim_comp.GetEntityDimensionId()
        block_comp = serverApi.GetEngineCompFactory().CreateBlockInfo(serverApi.GetLevelId())

        found = []
        for dx in range(-radius, radius + 1):
            for dz in range(-radius, radius + 1):
                if len(found) >= MAX_RESULTS:
                    break
                bx = int(npc_pos[0]) + dx
                bz = int(npc_pos[2]) + dz
                y_start = int(npc_pos[1]) + 3
                y_end = max(int(npc_pos[1]) - 10, -64)
                for by in range(y_start, y_end - 1, -1):
                    if len(found) >= MAX_RESULTS:
                        break
                    block_dict = block_comp.GetBlockNew((bx, by, bz), npc_dim)
                    if block_dict:
                        bname = block_dict.get("name", "").lower()
                        if block_name in bname:
                            found.append("(%d,%d,%d)" % (bx, by, bz))

        if not found:
            return {"status": "ok", "message": "半径%d格内没有找到%s" % (radius, block_name)}

        msg = "半径%d格内找到%d个%s:\n" % (radius, len(found), block_name)
        msg += ", ".join(found)
        return {"status": "ok", "message": msg}


ToolRegistry.register(FindBlockAction)
