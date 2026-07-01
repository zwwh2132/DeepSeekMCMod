# -*- coding: utf-8 -*-
"""
scan_entities: 搜索指定坐标范围内所有实体（玩家/生物），返回名称、类型和距离
使用 GetEntitiesInSquareArea 引擎API进行范围搜索
"""
import math
import mod.server.extraServerApi as serverApi
from .base import ActionTool
from .tool_registry import ToolRegistry


class ScanEntitiesAction(ActionTool):
    name = "scan_entities"
    description = "搜索指定立方体坐标范围内的所有实体（玩家/生物），返回名称、类型和距离。注意：只搜索NPC所在维度"
    parameters = {
        "type": "object",
        "properties": {
            "x1": {"type": "number", "description": "起始X坐标"},
            "y1": {"type": "number", "description": "起始Y坐标"},
            "z1": {"type": "number", "description": "起始Z坐标"},
            "x2": {"type": "number", "description": "结束X坐标"},
            "y2": {"type": "number", "description": "结束Y坐标"},
            "z2": {"type": "number", "description": "结束Z坐标"}
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

        min_x, max_x = min(x1, x2), max(x1, x2)
        min_y, max_y = min(y1, y2), max(y1, y2)
        min_z, max_z = min(z1, z2), max(z1, z2)

        dim_comp = serverApi.GetEngineCompFactory().CreateDimension(entityId)
        npc_dim = dim_comp.GetEntityDimensionId()

        level_id = serverApi.GetLevelId()
        game_comp = serverApi.GetEngineCompFactory().CreateGame(level_id)
        entity_list = game_comp.GetEntitiesInSquareArea(
            None,
            (min_x, min_y, min_z),
            (max_x, max_y, max_z),
            npc_dim
        )

        # 获取 NPC 位置用于计算距离
        pos_comp = serverApi.GetEngineCompFactory().CreatePos(entityId)
        npc_pos = pos_comp.GetPos()

        results = []
        for eid in entity_list:
            if eid == entityId:
                continue
            e_pos_comp = serverApi.GetEngineCompFactory().CreatePos(eid)
            e_pos = e_pos_comp.GetPos()
            if not e_pos:
                continue

            dist = 0.0
            if npc_pos:
                dist = math.sqrt((e_pos[0] - npc_pos[0]) ** 2 +
                                 (e_pos[1] - npc_pos[1]) ** 2 +
                                 (e_pos[2] - npc_pos[2]) ** 2)

            type_comp = serverApi.GetEngineCompFactory().CreateEngineType(eid)
            engine_type = type_comp.GetEngineTypeStr() if type_comp else ""
            identifier = engine_type or "未知"

            name_comp = serverApi.GetEngineCompFactory().CreateName(eid)
            e_name = name_comp.GetName() if name_comp else ""

            if "player" in engine_type:
                results.append("玩家「%s」 id=%s 位置(%.0f,%.0f,%.0f) 距%.0f格" % (
                    e_name or eid, eid, e_pos[0], e_pos[1], e_pos[2], dist))
            elif e_name:
                results.append("「%s」(%s) id=%s 位置(%.0f,%.0f,%.0f) 距%.0f格" % (
                    e_name, identifier, eid, e_pos[0], e_pos[1], e_pos[2], dist))
            else:
                results.append("%s id=%s 位置(%.0f,%.0f,%.0f) 距%.0f格" % (
                    identifier, eid, e_pos[0], e_pos[1], e_pos[2], dist))

        if not results:
            return {"status": "ok", "message": "范围 (%d,%d,%d)~(%d,%d,%d) 内没有发现任何实体" % (
                min_x, min_y, min_z, max_x, max_y, max_z)}

        msg = "范围 (%d,%d,%d)~(%d,%d,%d) 内发现%d个实体:\n" % (
            min_x, min_y, min_z, max_x, max_y, max_z, len(results))
        msg += "\n".join(results)
        return {"status": "ok", "message": msg}


ToolRegistry.register(ScanEntitiesAction)
