# -*- coding: utf-8 -*-
"""
set_block: 在指定坐标放置方块
"""
import mod.server.extraServerApi as serverApi
from .base import ActionTool
from .tool_registry import ToolRegistry


class SetBlockAction(ActionTool):
    name = "set_block"
    description = "在指定坐标放置一个方块"
    parameters = {
        "type": "object",
        "properties": {
            "x": {"type": "number", "description": "目标X坐标"},
            "y": {"type": "number", "description": "目标Y坐标"},
            "z": {"type": "number", "description": "目标Z坐标"},
            "block_name": {"type": "string", "description": "方块名称，如chest、stone、grass_block等"}
        },
        "required": ["x", "y", "z", "block_name"]
    }

    @classmethod
    def execute(cls, entityId, params, context=None):
        x = int(params.get("x", 0))
        y = int(params.get("y", 0))
        z = int(params.get("z", 0))
        block_name = params.get("block_name", "")
        print("[set_block] entityId=%s, target=(%d,%d,%d), block=%s" % (entityId, x, y, z, block_name))
        if not block_name:
            return {"status": "error", "message": "请指定方块名称"}

        # 补齐命名空间
        if ":" not in block_name:
            block_name = "minecraft:" + block_name

        dim_comp = serverApi.GetEngineCompFactory().CreateDimension(entityId)
        dim_id = dim_comp.GetEntityDimensionId()

        block_comp = serverApi.GetEngineCompFactory().CreateBlockInfo(serverApi.GetLevelId())
        block_dict = {"name": block_name}
        result = block_comp.SetBlockNew((x, y, z), block_dict, 0, dim_id, True)
        print("[set_block] result=%s, dim=%d" % (result, dim_id))
        if result:
            return {"status": "ok", "message": "已在(%d,%d,%d)放置%s" % (x, y, z, block_name)}
        return {"status": "error", "message": "放置失败，方块未变化或位置无效"}


ToolRegistry.register(SetBlockAction)
