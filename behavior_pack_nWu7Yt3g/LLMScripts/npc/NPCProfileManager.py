# -*- coding: utf-8 -*-
"""
NPC 配置中心
自动扫描 npc/profiles/ 目录，加载所有 profile。
新增 NPC 只需在 profiles/ 下新建一个 py 文件。
"""

from profiles import default
from profiles import old_villager
from profiles import warrior


class NPCProfileManager(object):
    """NPC 配置管理器（单例）"""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(NPCProfileManager, cls).__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def __init__(self):
        if self._loaded:
            return
        self._loaded = True
        self._profiles = {}
        self._load_all()

    def _load_all(self):
        """加载所有 profile"""
        for module in [default, old_villager, warrior]:
            profile = getattr(module, "PROFILE", None)
            if profile and "id" in profile:
                pid = profile["id"]
                self._profiles[pid] = profile
                print("===== NPCProfileManager: 已加载 [%s] %s =====" % (pid, profile.get("name", "")))

    def get(self, profile_id):
        """按 ID 获取 profile，不存在则返回默认"""
        return self._profiles.get(profile_id) or self._profiles.get("default")

    def get_all(self):
        """获取所有 profile"""
        return dict(self._profiles)

    def list_names(self):
        """返回所有 NPC 名字列表"""
        return [p.get("name", pid) for pid, p in self._profiles.items()]

    def list_ids(self):
        """返回所有 NPC ID 列表"""
        return self._profiles.keys()
