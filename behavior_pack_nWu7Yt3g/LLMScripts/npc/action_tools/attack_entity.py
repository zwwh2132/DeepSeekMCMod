# -*- coding: utf-8 -*-
"""
attack_entity: 让 NPC 追击并近战攻击指定目标
"""
import mod.server.extraServerApi as serverApi
from .base import ActionTool
from .tool_registry import ToolRegistry
from LLMScripts.npc.NPCManager import NPCManager


class AttackEntityAction(ActionTool):
    name = "attack_entity"
    description = "让NPC追击并近战攻击指定目标。用 target_name 指定NPC/玩家名字，或用 target_id 指定实体ID。攻击模式会持续追击直到目标死亡（health<=0）。重要：如果你已经在追击一个目标且它还活着，不要对另一个目标再次使用本工具，必须逐个击破"
    parameters = {
        "type": "object",
        "properties": {
            "target_name": {"type": "string", "description": "目标NPC的显示名字或玩家名字，与 target_id 二选一"},
            "target_id": {"type": "string", "description": "目标实体的 entityId，与 target_name 二选一"},
            "damage": {"type": "number", "description": "每次攻击伤害值，默认10"}
        },
        "required": ["damage"]
    }

    @classmethod
    def execute(cls, entityId, params, context=None):
        # 解析目标：优先用 target_name，其次 target_id
        target_name = params.get("target_name", "")
        target_id = params.get("target_id", "")
        damage = float(params.get("damage", 10))

        if target_name:
            # 先查玩家
            player_list = serverApi.GetPlayerList()
            for pid in player_list:
                name_comp = serverApi.GetEngineCompFactory().CreateName(pid)
                if name_comp.GetName() == target_name:
                    target_id = pid
                    break
            if not target_id:
                # 再查 NPC
                resolved = NPCManager.resolve_name(target_name)
                if resolved:
                    target_id = resolved
                else:
                    return {"status": "error", "message": "未找到目标「%s」（不是在线玩家也不是已知NPC）" % target_name}
        elif not target_id:
            return {"status": "error", "message": "请指定 target_name（NPC/玩家名字）或 target_id（实体ID）"}

        extra = serverApi.GetEngineCompFactory().CreateExtraData(entityId)
        # 清除跟随模式
        extra.SetExtraData("follow_target_player", "")
        # 设置攻击模式
        extra.SetExtraData("attack_target_id", str(target_id))
        extra.SetExtraData("attack_target_name", target_name or "")
        extra.SetExtraData("attack_damage", str(damage))

        label = target_name or target_id
        return {"status": "ok", "message": "开始追击「%s」，攻击力=%.1f" % (label, damage)}


ToolRegistry.register(AttackEntityAction)
