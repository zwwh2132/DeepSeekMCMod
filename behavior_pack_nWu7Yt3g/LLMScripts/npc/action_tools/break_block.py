# -*- coding: utf-8 -*-
"""
break_block: 破坏指定坐标的方块
"""
import mod.server.extraServerApi as serverApi
from .base import ActionTool
from .tool_registry import ToolRegistry


class BreakBlockAction(ActionTool):
    name = "break_block"
    description = "破坏指定坐标处的方块（设置为空气）"
    parameters = {
        "type": "object",
        "properties": {
            "x": {"type": "number", "description": "目标X坐标"},
            "y": {"type": "number", "description": "目标Y坐标"},
            "z": {"type": "number", "description": "目标Z坐标"}
        },
        "required": ["x", "y", "z"]
    }

    @classmethod
    def execute(cls, entityId, params, context=None):
        x = int(params.get("x", 0))
        y = int(params.get("y", 0))
        z = int(params.get("z", 0))
        print("[break_block] entityId=%s, target=(%d,%d,%d)" % (entityId, x, y, z))

        dim_comp = serverApi.GetEngineCompFactory().CreateDimension(entityId)
        dim_id = dim_comp.GetEntityDimensionId()

        block_comp = serverApi.GetEngineCompFactory().CreateBlockInfo(serverApi.GetLevelId())
        block_dict = {"name": "minecraft:air"}
        result = block_comp.SetBlockNew((x, y, z), block_dict, 0, dim_id, True)
        print("[break_block] result=%s, dim=%d" % (result, dim_id))
        if result:
            return {"status": "ok", "message": "已破坏(%d,%d,%d)处的方块" % (x, y, z)}
        return {"status": "error", "message": "破坏失败，该位置可能已是空气"}


ToolRegistry.register(BreakBlockAction)
