# -*- coding: utf-8 -*-
"""
set_attack_target: 设置或清除实体的仇恨目标（可指定任意实体）
"""
import mod.server.extraServerApi as serverApi
from .base import ActionTool
from .tool_registry import ToolRegistry


class SetAttackTargetAction(ActionTool):
    name = "set_attack_target"
    description = "设置或清除实体的仇恨目标。可让任意实体A去攻击实体B（斗蛐蛐用）。不传target_id则清除仇恨目标"
    parameters = {
        "type": "object",
        "properties": {
            "attacker_id": {"type": "string", "description": "要设置仇恨的实体ID（谁去打）。不传则默认NPC自己"},
            "target_id": {"type": "string", "description": "被仇恨的实体ID（打谁）。不传则清除仇恨目标"}
        },
        "required": []
    }

    @classmethod
    def execute(cls, entityId, params, context=None):
        # attacker_id 不传则用 NPC 自己
        attacker_id = params.get("attacker_id", "") or entityId
        target_id = params.get("target_id", "")

        comp = serverApi.GetEngineCompFactory().CreateAction(attacker_id)

        if not target_id:
            result = comp.ResetAttackTarget()
            if result:
                return {"status": "ok", "message": "已清除仇恨目标"}
            return {"status": "error", "message": "清除仇恨目标失败"}

        result = comp.SetAttackTarget(target_id)
        if result:
            # 获取双方名字用于反馈
            attacker_name = attacker_id
            try:
                name_comp = serverApi.GetEngineCompFactory().CreateName(attacker_id)
                if name_comp:
                    attacker_name = name_comp.GetName() or attacker_id
            except:
                pass
            target_name = target_id
            try:
                name_comp = serverApi.GetEngineCompFactory().CreateName(target_id)
                if name_comp:
                    target_name = name_comp.GetName() or target_id
            except:
                pass
            return {"status": "ok", "message": "已让「%s」仇恨「%s」" % (attacker_name, target_name)}
        return {"status": "error", "message": "设置仇恨目标失败，目标可能不存在"}


ToolRegistry.register(SetAttackTargetAction)
