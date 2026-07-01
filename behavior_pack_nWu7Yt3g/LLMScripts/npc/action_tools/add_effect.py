# -*- coding: utf-8 -*-
"""
add_effect: 为指定实体添加状态效果（药水效果）
"""
import mod.server.extraServerApi as serverApi
from .base import ActionTool
from .tool_registry import ToolRegistry
from LLMScripts.npc.NPCManager import NPCManager


class AddEffectAction(ActionTool):
    name = "add_effect"
    description = "为指定实体添加状态效果（如速度、力量、再生等）。用 target_name 指定NPC名字，或用 target_id 指定实体ID"
    parameters = {
        "type": "object",
        "properties": {
            "target_name": {"type": "string", "description": "目标NPC的显示名字（如「战士」、「老村民」），与 target_id 二选一"},
            "target_id": {"type": "string", "description": "目标实体的entityId，与 target_name 二选一"},
            "effect_name": {"type": "string", "description": "效果名称，如 speed(速度)、strength(力量)、regeneration(再生)、poison(中毒)、weakness(虚弱)、slowness(缓慢)、haste(急迫)、jump_boost(跳跃提升)、night_vision(夜视)、invisibility(隐身)、resistance(抗性)、fire_resistance(防火)、water_breathing(水下呼吸) 等"},
            "duration": {"type": "number", "description": "持续时间（秒），默认30"},
            "amplifier": {"type": "number", "description": "效果等级，0=I级 1=II级 2=III级，默认0"}
        },
        "required": ["effect_name"]
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
        effect_name = str(params.get("effect_name", ""))
        duration = float(params.get("duration", 30))
        amplifier = int(params.get("amplifier", 0))
        if not target_id or not effect_name:
            return {"status": "error", "message": "请指定目标实体ID和效果名称"}
        try:
            effect_comp = serverApi.GetEngineCompFactory().CreateEffect(target_id)
            result = effect_comp.AddEffectToEntity(effect_name, duration, amplifier, True)
            if result:
                return {"status": "ok", "message": "已为%s添加%s效果 %d秒 (等级%d)" % (target_id, effect_name, duration, amplifier + 1)}
            return {"status": "error", "message": "添加效果失败"}
        except Exception as e:
            return {"status": "error", "message": "添加效果异常: %s" % str(e)}


ToolRegistry.register(AddEffectAction)
