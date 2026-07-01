# -*- coding: utf-8 -*-
"""
scan_blocks: 全量扫描指定坐标范围内的所有方块，返回各类方块的数量统计（数据精简）
"""
import mod.server.extraServerApi as serverApi
from .base import ActionTool
from .tool_registry import ToolRegistry

MAX_BLOCKS = 100000  # 最大扫描方块数


class ScanBlocksAction(ActionTool):
    name = "scan_blocks"
    description = "全量扫描指定坐标范围内的所有方块，返回各类方块的数量统计（精简数据，节省token）。注意：只扫描NPC所在维度"
    parameters = {
        "type": "object",
        "properties": {
            "x1": {"type": "number", "description": "起始X坐标"},
            "y1": {"type": "number", "description": "起始Y坐标"},
            "z1": {"type": "number", "description": "起始Z坐标"},
            "x2": {"type": "number", "description": "结束X坐标"},
            "y2": {"type": "number", "description": "结束Y坐标"},
            "z2": {"type": "number", "description": "结束Z坐标"},
            "exclude_air": {"type": "boolean", "description": "是否排除空气方块，默认true，建议开启以节省token"}
        },
        "required": ["x1", "y1", "z1", "x2", "y2", "z2"]
    }

    @classmethod
    def execute(cls, entityId, params, context=None):
        x1 = int(params.get("x1", 0))
        y1 = int(params.get("y1", 0))
        z1 = int(params.get("z1", 0))
        x2 = int(params.get("x2", 0))
        y2 = int(params.get("y2", 0))
        z2 = int(params.get("z2", 0))
        exclude_air = True
        raw_exclude = params.get("exclude_air", True)
        if isinstance(raw_exclude, bool):
            exclude_air = raw_exclude
        elif isinstance(raw_exclude, basestring):
            exclude_air = raw_exclude.lower() == "true"

        # 排序坐标
        min_x, max_x = min(x1, x2), max(x1, x2)
        min_y, max_y = min(y1, y2), max(y1, y2)
        min_z, max_z = min(z1, z2), max(z1, z2)

        # 检查范围是否超限
        total_blocks = (max_x - min_x + 1) * (max_y - min_y + 1) * (max_z - min_z + 1)
        if total_blocks > MAX_BLOCKS:
            return {"status": "error", "message": "扫描范围过大（共%d个方块），超过上限%d个，请缩小扫描范围" % (total_blocks, MAX_BLOCKS)}

        # 获取维度
        dim_comp = serverApi.GetEngineCompFactory().CreateDimension(entityId)
        dim_id = dim_comp.GetEntityDimensionId()

        block_comp = serverApi.GetEngineCompFactory().CreateBlockInfo(serverApi.GetLevelId())

        counts = {}
        scanned = 0
        for x in range(min_x, max_x + 1):
            for z in range(min_z, max_z + 1):
                for y in range(min_y, max_y + 1):
                    block_dict = block_comp.GetBlockNew((x, y, z), dim_id)
                    scanned += 1
                    if block_dict:
                        name = block_dict.get("name", "")
                        if exclude_air and name and "air" in name.lower():
                            continue
                        if name:
                            counts[name] = counts.get(name, 0) + 1

        if not counts:
            return {"status": "ok", "message": "扫描范围 (%d,%d,%d) ~ (%d,%d,%d) 内没有找到任何方块" % (min_x, min_y, min_z, max_x, max_y, max_z)}

        # 按数量降序排列
        sorted_blocks = sorted(counts.items(), key=lambda x: -x[1])

        lines = ["扫描范围 (%d,%d,%d) ~ (%d,%d,%d)，共扫描%d个方块:" % (min_x, min_y, min_z, max_x, max_y, max_z, scanned)]
        for name, count in sorted_blocks:
            lines.append("  %s x%d" % (name, count))

        return {"status": "ok", "message": "\n".join(lines)}


ToolRegistry.register(ScanBlocksAction)
