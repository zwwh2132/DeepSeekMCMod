# -*- coding: utf-8 -*-
"""
damage_entity: 对指定实体造成伤害
"""
import mod.server.extraServerApi as serverApi
from .base import ActionTool
from .tool_registry import ToolRegistry
from LLMScripts.npc.NPCManager import NPCManager


class DamageEntityAction(ActionTool):
    name = "damage_entity"
    description = "对指定实体造成伤害。用 target_name 指定NPC名字，或用 target_id 指定实体ID"
    parameters = {
        "type": "object",
        "properties": {
            "target_name": {"type": "string", "description": "目标NPC的显示名字（如「战士」、「老村民」），与 target_id 二选一"},
            "target_id": {"type": "string", "description": "目标实体的entityId，与 target_name 二选一"},
            "damage": {"type": "number", "description": "伤害值，如10表示10点伤害（5颗心）"}
        },
        "required": ["damage"]
    }

    @classmethod
    def execute(cls, entityId, params, context=None):
        # 解析目标：优先用 target_name，其次 target_id
        target_name = params.get("target_name", "")
        target_id = params.get("target_id", "")
        if target_name:
            resolved = NPCManager.resolve_name(target_name)
            if not resolved:
                return {"status": "error", "message": "未找到名字为「%s」的NPC" % target_name}
            target_id = resolved
        elif not target_id:
            return {"status": "error", "message": "请指定 target_name（NPC名字）或 target_id（实体ID）"}

        target_id = str(target_id)
        damage = float(params.get("damage", 0))
        attacker_id = str(entityId)
        print("[damage_entity] 攻击者=%s, 目标=%s, 伤害=%s" % (attacker_id, target_id, damage))
        if not target_id or damage <= 0:
            return {"status": "error", "message": "请指定目标实体ID和有效的伤害值"}
        try:
            hurt_comp = serverApi.GetEngineCompFactory().CreateHurt(target_id)
            mc_enum = serverApi.GetMinecraftEnum()
            cause = mc_enum.ActorDamageCause.EntityAttack
            result = hurt_comp.Hurt(damage, cause, attacker_id, attacker_id, False)
            print("[damage_entity] Hurt返回值: %s" % result)
            if result:
                return {"status": "ok", "message": "对%s造成了%.1f点伤害" % (target_id, damage)}
            return {"status": "error", "message": "伤害失败"}
        except Exception as e:
            print("[damage_entity] 异常: %s" % str(e))
            return {"status": "error", "message": "伤害异常: %s" % str(e)}


ToolRegistry.register(DamageEntityAction)
