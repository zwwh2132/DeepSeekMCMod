# -*- coding: utf-8 -*-
"""
get_block: 查询指定坐标处的方块信息
"""
import mod.server.extraServerApi as serverApi
from .base import ActionTool
from .tool_registry import ToolRegistry


class GetBlockAction(ActionTool):
    name = "get_block"
    description = "查询指定坐标处是什么方块"
    parameters = {
        "type": "object",
        "properties": {
            "x": {"type": "number", "description": "X坐标"},
            "y": {"type": "number", "description": "Y坐标"},
            "z": {"type": "number", "description": "Z坐标"}
        },
        "required": ["x", "y", "z"]
    }

    @classmethod
    def execute(cls, entityId, params, context=None):
        x = int(params.get("x", 0))
        y = int(params.get("y", 0))
        z = int(params.get("z", 0))

        dim_comp = serverApi.GetEngineCompFactory().CreateDimension(entityId)
        dim_id = dim_comp.GetEntityDimensionId()

        block_comp = serverApi.GetEngineCompFactory().CreateBlockInfo(serverApi.GetLevelId())
        block_dict = block_comp.GetBlockNew((x, y, z), dim_id)
        if block_dict:
            name = block_dict.get("name", "未知")
            aux = block_dict.get("aux", 0)
            return {"status": "ok", "message": "(%d,%d,%d) 处的方块: %s (aux=%d)" % (x, y, z, name, aux)}
        return {"status": "ok", "message": "(%d,%d,%d) 处没有方块（空气）" % (x, y, z)}


ToolRegistry.register(GetBlockAction)
