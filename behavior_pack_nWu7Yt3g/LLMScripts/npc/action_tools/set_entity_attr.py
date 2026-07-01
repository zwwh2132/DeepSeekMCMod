# -*- coding: utf-8 -*-
"""
set_entity_attr: 设置实体的属性值（血量、攻击力、移速、护甲、击退抗性等）
"""
import mod.server.extraServerApi as serverApi
from .base import ActionTool
from .tool_registry import ToolRegistry
from LLMScripts.npc.NPCManager import NPCManager


class SetEntityAttrAction(ActionTool):
    name = "set_entity_attr"
    description = "设置实体的属性值，支持血量、最大血量、攻击力、移速、护甲、击退抗性。用 target_name 指定NPC名字，或用 target_id 指定实体ID。不传的可选属性不会被修改"
    parameters = {
        "type": "object",
        "properties": {
            "target_name": {"type": "string", "description": "目标NPC的显示名字（如「战士」、「老村民」），与 target_id 二选一"},
            "target_id": {"type": "string", "description": "目标实体的 entityId，与 target_name 二选一"},
            "health": {"type": "number", "description": "设置当前生命值，如 100"},
            "max_health": {"type": "number", "description": "设置最大生命值，如 1000"},
            "attack_damage": {"type": "number", "description": "设置攻击力，如 50"},
            "movement_speed": {"type": "number", "description": "设置移动速度，如 0.5"},
            "armor": {"type": "number", "description": "设置护甲值，如 20"},
            "knockback_resistance": {"type": "number", "description": "设置击退抗性百分比，0~100，如 100 代表完全免疫击退"},
            "owner_id": {"type": "string", "description": "设置实体的属主（主人）实体ID，如玩家ID或NPC ID"}
        },
        "required": []
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
        compFactory = serverApi.GetEngineCompFactory()
        mc_enum = serverApi.GetMinecraftEnum()
        applied = []

        # 逐个处理可选的属性参数
        try:
            # 1. 最大生命值
            max_health = params.get("max_health")
            if max_health is not None:
                attr_comp = compFactory.CreateAttr(target_id)
                attr_comp.SetAttrMaxValue(mc_enum.AttrType.HEALTH, float(max_health))
                current = attr_comp.GetAttrValue(mc_enum.AttrType.HEALTH)
                if current > float(max_health):
                    attr_comp.SetAttrValue(mc_enum.AttrType.HEALTH, float(max_health))
                applied.append("最大生命值=%.1f" % float(max_health))

            # 2. 当前生命值
            health = params.get("health")
            if health is not None:
                attr_comp = compFactory.CreateAttr(target_id)
                cur_max = attr_comp.GetAttrMaxValue(mc_enum.AttrType.HEALTH)
                new_hp = float(health)
                if cur_max and new_hp > cur_max:
                    attr_comp.SetAttrMaxValue(mc_enum.AttrType.HEALTH, new_hp)
                attr_comp.SetAttrValue(mc_enum.AttrType.HEALTH, new_hp)
                applied.append("生命值=%.1f" % new_hp)

            # 3. 攻击力（通过 minecraft:attack 组件）
            attack_damage = params.get("attack_damage")
            if attack_damage is not None:
                event_comp = compFactory.CreateEntityEvent(target_id)
                if event_comp:
                    event_comp.AddActorComponent("minecraft:attack", '{"damage": %d}' % int(attack_damage))
                    applied.append("攻击力=%d" % int(attack_damage))

            # 4. 移动速度
            movement_speed = params.get("movement_speed")
            if movement_speed is not None:
                speed = float(movement_speed)
                attr_comp = compFactory.CreateAttr(target_id)
                attr_comp.SetAttrMaxValue(mc_enum.AttrType.SPEED, speed)
                attr_comp.SetAttrValue(mc_enum.AttrType.SPEED, speed)
                applied.append("移速=%.2f" % speed)

            # 5. 护甲
            armor = params.get("armor")
            if armor is not None:
                attr_comp = compFactory.CreateAttr(target_id)
                attr_comp.SetAttrMaxValue(mc_enum.AttrType.ARMOR, float(armor))
                attr_comp.SetAttrValue(mc_enum.AttrType.ARMOR, float(armor))
                applied.append("护甲=%.1f" % float(armor))

            # 6. 击退抗性（通过 knockback_resistance 组件）
            knockback = params.get("knockback_resistance")
            if knockback is not None:
                kb_pct = min(100, max(0, float(knockback)))
                event_comp = compFactory.CreateEntityEvent(target_id)
                if event_comp:
                    event_comp.AddActorComponent(
                        "minecraft:knockback_resistance",
                        '{"value": %f, "max": 100}' % kb_pct
                    )
                    applied.append("击退抗性=%d%%" % int(kb_pct))

            # 7. 实体属主（主人）
            owner_id = params.get("owner_id")
            if owner_id is not None:
                owner_id = str(owner_id)
                owner_comp = compFactory.CreateActorOwner(target_id)
                if owner_comp:
                    result = owner_comp.SetEntityOwner(owner_id)
                    if result:
                        # 获取主人名字用于反馈
                        owner_name = owner_id
                        try:
                            name_comp = compFactory.CreateName(owner_id)
                            if name_comp:
                                owner_name = name_comp.GetName() or owner_id
                        except:
                            pass
                        applied.append("属主=%s" % owner_name)
                    else:
                        applied.append("属主设置失败")

        except Exception as e:
            print("[set_entity_attr] 异常: %s" % str(e))
            return {"status": "error", "message": "设置属性异常: %s" % str(e)}

        if not applied:
            return {"status": "error", "message": "没有指定要设置的属性，支持: health, max_health, attack_damage, movement_speed, armor, knockback_resistance"}

        return {"status": "ok", "message": "已为%s设置属性: %s" % (target_id, ", ".join(applied))}


ToolRegistry.register(SetEntityAttrAction)
