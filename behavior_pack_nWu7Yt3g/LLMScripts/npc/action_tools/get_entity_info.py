# -*- coding: utf-8 -*-
"""
get_entity_info: 查询任意实体的详细信息（坐标、血量、类型、状态等）
"""
import mod.server.extraServerApi as serverApi
from .base import ActionTool
from .tool_registry import ToolRegistry
from LLMScripts.npc.NPCManager import NPCManager


class GetEntityInfoAction(ActionTool):
    name = "get_entity_info"
    description = "查询任意实体的详细信息，包括坐标、血量、类型、维度、存活状态等。用 entity_name 指定NPC名字，或用 entity_id 指定实体ID"
    parameters = {
        "type": "object",
        "properties": {
            "entity_name": {"type": "string", "description": "目标NPC的显示名字（如「战士」、「老村民」），与 entity_id 二选一"},
            "entity_id": {"type": "string", "description": "要查询的实体ID，与 entity_name 二选一"}
        },
        "required": []
    }

    @classmethod
    def execute(cls, entityId, params, context=None):
        # 解析目标：优先用 entity_name，其次 entity_id
        entity_name = params.get("entity_name", "")
        target_id = params.get("entity_id", "")
        if entity_name:
            resolved = NPCManager.resolve_name(entity_name)
            if not resolved:
                return {"status": "error", "message": "未找到名字为「%s」的NPC" % entity_name}
            target_id = resolved
        elif not target_id:
            return {"status": "error", "message": "请指定 entity_name（NPC名字）或 entity_id（实体ID）"}

        target_id = str(target_id)
        lines = []
        lines.append("实体信息: %s" % target_id)

        # --- 存活判定（靠生命值，最准确）---
        alive = True
        try:
            attr_comp = serverApi.GetEngineCompFactory().CreateAttr(target_id)
            mc_enum = serverApi.GetMinecraftEnum()
            health = attr_comp.GetAttrValue(mc_enum.AttrType.HEALTH)
            if health is not None and health <= 0:
                alive = False
                lines.append("  状态: §c已死亡§r (health=%.1f)" % health)
            elif health is not None:
                alive = True
                lines.append("  状态: §a存活§r (health=%.1f)" % health)
        except Exception:
            alive = False
            lines.append("  状态: §c已死亡§r (无法获取生命值)")

        # 已死亡的实体不再查其他信息
        if not alive:
            return {"status": "ok", "message": "\n".join(lines)}

        # --- 标识（从 GetEngineActor 获取） ---
        try:
            all_actors = serverApi.GetEngineActor()
            if target_id in all_actors:
                lines.append("  标识: %s" % all_actors[target_id].get("identifier", "?"))
        except Exception:
            pass

        # --- 显示名 ---
        try:
            name_comp = serverApi.GetEngineCompFactory().CreateName(target_id)
            disp_name = name_comp.GetName()
            if disp_name:
                lines.append("  名称: %s" % disp_name)
        except Exception:
            pass

        # --- 实体类型 ---
        try:
            type_comp = serverApi.GetEngineCompFactory().CreateEngineType(target_id)
            type_str = type_comp.GetEngineTypeStr()
            if type_str:
                lines.append("  类型: %s" % type_str)
        except Exception:
            pass

        # --- 坐标 ---
        try:
            pos_comp = serverApi.GetEngineCompFactory().CreatePos(target_id)
            pos = pos_comp.GetFootPos()
            if pos:
                lines.append("  坐标: x=%.1f, y=%.1f, z=%.1f" % (pos[0], pos[1], pos[2]))
        except Exception:
            pass

        # --- 维度 ---
        try:
            dim_comp = serverApi.GetEngineCompFactory().CreateDimension(target_id)
            dim_id = dim_comp.GetEntityDimensionId()
            dim_names = {0: "主世界", 1: "下界", 2: "末地"}
            dim_name = dim_names.get(dim_id, "自定义(%d)" % dim_id)
            lines.append("  维度: %s" % dim_name)
        except Exception:
            pass

        # --- 属性（血量/速度/攻击等）---
        try:
            attr_comp = serverApi.GetEngineCompFactory().CreateAttr(target_id)
            mc_enum = serverApi.GetMinecraftEnum()

            attr_checks = [
                ("HEALTH", "血量"),
                ("SPEED", "速度"),
                ("ATTACK_DAMAGE", "攻击力"),
                ("ARMOR", "护甲"),
                ("HUNGER", "饥饿度"),
                ("SATURATION", "饱和度"),
            ]
            for attr_name, label in attr_checks:
                try:
                    attr_type = getattr(mc_enum.AttrType, attr_name)
                    value = attr_comp.GetAttrValue(attr_type)
                    if value is not None and value > -1:
                        if attr_name == "HEALTH":
                            try:
                                max_val = attr_comp.GetAttrMaxValue(attr_type)
                                lines.append("  生命值: %.1f / %.1f" % (value, max_val))
                            except Exception:
                                lines.append("  生命值: %.1f" % value)
                        else:
                            lines.append("  %s: %.2f" % (label, value))
                except Exception:
                    pass
        except Exception:
            pass

        # --- 属主（主人）---
        try:
            owner_comp = serverApi.GetEngineCompFactory().CreateActorOwner(target_id)
            if owner_comp:
                owner_id = owner_comp.GetEntityOwner()
                if owner_id:
                    owner_name = owner_id
                    try:
                        name_comp = serverApi.GetEngineCompFactory().CreateName(owner_id)
                        if name_comp:
                            owner_name = name_comp.GetName() or owner_id
                    except:
                        pass
                    lines.append("  属主: %s" % owner_name)
        except:
            pass

        if len(lines) <= 1:
            return {"status": "error", "message": "无法获取实体%s的信息" % target_id}

        return {"status": "ok", "message": "\n".join(lines)}


ToolRegistry.register(GetEntityInfoAction)
