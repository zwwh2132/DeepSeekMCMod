# -*- coding: utf-8 -*-
"""
NPCManager — NPC 实体生命周期管理
管理所有已生成的 NPC 实体，处理实体的创建、销毁、查询。
"""
import mod.server.extraServerApi as serverApi


class NPCManager(object):
    """NPC 实体管理器（单例）"""

    _instance = None

    # NPC 实体标识符
    NPC_IDENTIFIER = "zwwh:llm_npc"

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(NPCManager, cls).__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def __init__(self):
        if self._loaded:
            return
        self._loaded = True

        # {entityId: {"profile_id": str, "display_name": str, ...}}
        self._npcs = {}

        print("[NPCManager] 初始化完成")

    def set_system(self, system):
        """由 LLMServerSystem 注入系统实例（用于监听事件）"""
        self._system = system
        # 监听从场景中删除实体的事件（死亡、清除、玩家退出等）
        system.ListenForEvent(
            serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
            "EntityRemoveEvent", self, self._OnEntityRemove
        )
        # 监听生物死亡事件（提前释放名字，让玩家可以立即重建同名NPC）
        system.ListenForEvent(
            serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
            "MobDieEvent", self, self._OnMobDie
        )
        print("[NPCManager] 系统实例已注入")

    def _OnEntityRemove(self, args):
        """实体从场景中移除时清理 NPC 记录（死亡/清除/玩家退出等）"""
        eid = args.get("id", "")
        if eid in self._npcs:
            info = self._npcs.pop(eid)
            print("[NPCManager] 实体已移除: %s -> %s" % (eid, info.get("display_name", "?")))

    def _OnMobDie(self, args):
        """实体死亡时释放名字，允许同名重生"""
        eid = args.get("id", "")
        if eid in self._npcs:
            info = self._npcs.pop(eid)
            print("[NPCManager] 实体死亡，名字已释放: %s -> %s" % (eid, info.get("display_name", "?")))

    def create_npc(self, profile_id, playerId=None, display_name=None):
        """在玩家位置生成一个 NPC 实体
        注意：调用方必须在 self 上调用 CreateEngineEntityByTypeStr
        """
        # 获取生成位置
        if playerId:
            targetId = playerId
        else:
            playerList = serverApi.GetPlayerList()
            if not playerList:
                print("[NPCManager] 没有在线玩家")
                return None
            targetId = playerList[0]

        posComp = serverApi.GetEngineCompFactory().CreatePos(targetId)
        targetPos = posComp.GetPos()
        if not targetPos:
            print("[NPCManager] 无法获取玩家位置")
            return None

        # 获取维度
        dimensionComp = serverApi.GetEngineCompFactory().CreateDimension(targetId)
        dimensionId = dimensionComp.GetPlayerDimensionId()

        # 注意：此方法不再自己创建实体，改为返回位置信息让调用方创建
        # 调用方需要在自己的系统上下文中调用 CreateEngineEntityByTypeStr
        return {
            "pos": (targetPos[0], targetPos[1] + 2, targetPos[2]),
            "dimension_id": dimensionId,
            "target_id": targetId
        }

    def after_spawn(self, entityId, profile_id, display_name=None):
        """实体创建后的初始化（ExtraData + 命名）
        如果指定了 display_name 且已存在同名 NPC，返回 None 表示冲突。
        """
        if not entityId:
            print("[NPCManager] 生成实体失败")
            return None

        from LLMScripts.npc.NPCProfileManager import NPCProfileManager
        profile = NPCProfileManager().get(profile_id)

        # 如果指定了自定义名字，检查是否重名
        if display_name and self.find_by_display_name(display_name):
            print("[NPCManager] 名字已存在，拒绝生成: %s" % display_name)
            return None

        # 自动生成唯一名字
        if not display_name:
            display_name = self._generate_unique_name(profile)

        # 写入 ExtraData（存档用）
        extraData = serverApi.GetEngineCompFactory().CreateExtraData(entityId)
        extraData.SetExtraData("profile_id", profile_id)
        extraData.SetExtraData("display_name", display_name)

        # 设置头顶显示名
        nameComp = serverApi.GetEngineCompFactory().CreateName(entityId)
        nameComp.SetName(display_name)

        # 获取位置
        posComp = serverApi.GetEngineCompFactory().CreatePos(entityId)
        pos = posComp.GetPos()

        # 记录到管理器
        self._npcs[entityId] = {
            "profile_id": profile_id,
            "display_name": display_name,
            "pos": pos
        }

        print("[NPCManager] 生成 NPC 实体: profile=%s, entityId=%s, name=%s" % (
            profile_id, entityId, display_name))
        return entityId

    def _generate_unique_name(self, profile):
        """基于 profile 自动生成唯一名字
        第一个叫"战士"，后面叫"战士-2"、"战士-3"...
        """
        base_name = profile.get("name", "NPC")
        # 统计已存在的同名 NPC 数量
        existing = [info for info in self._npcs.values()
                    if info.get("display_name", "").startswith(base_name)]
        max_suffix = 0
        for info in existing:
            name = info.get("display_name", "")
            if name == base_name:
                max_suffix = max(max_suffix, 1)
            elif name.startswith(base_name + "-"):
                try:
                    suffix = int(name[len(base_name) + 1:])
                    max_suffix = max(max_suffix, suffix)
                except ValueError:
                    pass
        if max_suffix == 0:
            return base_name
        return "%s-%d" % (base_name, max_suffix + 1)

    def remove_npc(self, entityId):
        """移除一个 NPC 实体"""
        if entityId in self._npcs:
            DestroyEntity(entityId)  # 直接调用引擎 API
            del self._npcs[entityId]
            print("[NPCManager] 移除 NPC 实体: %s" % entityId)
            return True
        return False

    def remove_all(self):
        """移除所有 NPC 实体"""
        ids = list(self._npcs.keys())
        for eid in ids:
            self.remove_npc(eid)
        return len(ids)

    def get_npc(self, entityId):
        """获取 NPC 信息"""
        return self._npcs.get(entityId)

    def get_all(self):
        """获取所有 NPC 实体信息"""
        return dict(self._npcs)

    def find_by_profile_id(self, profile_id):
        """按 profile_id 查找匹配的 NPC 实体"""
        matches = [eid for eid, info in self._npcs.items()
                   if info.get("profile_id") == profile_id]
        return matches

    def find_by_display_name(self, name):
        """按显示名查找 NPC 实体，返回 entityId 或 None
        如果记录中的实体已不存在于世界中，自动清理失效记录。
        """
        for eid, info in list(self._npcs.items()):
            if info.get("display_name") == name:
                if self._is_entity_alive(eid):
                    return eid
                # 实体已不存在（事件漏触发等），清理失效记录，名字释放
                del self._npcs[eid]
                print("[NPCManager] 清理失效的NPC记录: %s -> %s" % (eid, name))
                return None
        return None

    @classmethod
    def resolve_name(cls, name):
        """工具中使用的统一名字解析方法。
        按显示名查找 NPC 实体，返回 entityId；未找到则返回 None。
        所有 ActionTool 应通过此方法将名字转为 entityId。
        """
        instance = cls()
        return instance.find_by_display_name(name)

    def get_entity_profile_id(self, entityId):
        """从 ExtraData 读取实体的 profile_id"""
        extraData = serverApi.GetEngineCompFactory().CreateExtraData(entityId)
        return extraData.GetExtraData("profile_id")

    @staticmethod
    def _is_entity_alive(entityId):
        """检查实体是否仍存在于世界中"""
        try:
            all_actors = serverApi.GetEngineActor()
            return entityId in all_actors
        except Exception:
            return False

    def try_register(self, entityId):
        """从 ExtraData 尝试恢复 NPC 注册（用于存档重载时）
        如果实体已有 profile_id 且未注册，则自动注册。
        返回是否成功注册。
        """
        if entityId in self._npcs:
            return False

        profile_id = self.get_entity_profile_id(entityId)
        if not profile_id:
            return False

        from LLMScripts.npc.NPCProfileManager import NPCProfileManager
        profile = NPCProfileManager().get(profile_id)
        if not profile:
            print("[NPCManager] try_register: 未知 profile_id=%s" % profile_id)
            return False

        # 优先从 ExtraData 读取 display_name，其次是 NameComp
        extraData = serverApi.GetEngineCompFactory().CreateExtraData(entityId)
        display_name = extraData.GetExtraData("display_name")
        if not display_name:
            nameComp = serverApi.GetEngineCompFactory().CreateName(entityId)
            display_name = nameComp.GetName() or profile.get("name", "NPC")

        posComp = serverApi.GetEngineCompFactory().CreatePos(entityId)
        pos = posComp.GetPos()

        self._npcs[entityId] = {
            "profile_id": profile_id,
            "display_name": display_name,
            "pos": pos
        }
        print("[NPCManager] 从存档恢复 NPC: profile=%s, entityId=%s, name=%s" % (
            profile_id, entityId, display_name))
        return True

    def count(self):
        """当前 NPC 实体数量"""
        return len(self._npcs)


# 快捷方法：直接在引擎命名空间销毁实体
_DestroyEntity = None

def DestroyEntity(entityId):
    """销毁实体（独立方法，避免 System 上下文问题）"""
    global _DestroyEntity
    if _DestroyEntity is None:
        systemCls = serverApi.GetServerSystemCls()
        _DestroyEntity = systemCls(
            serverApi.GetEngineNamespace(),
            serverApi.GetEngineSystemName()
        ).DestroyEntity
    _DestroyEntity(entityId)
