# -*- coding: utf-8 -*-
# 确保所有模块在系统初始化时被加载
# 注意：这里必须使用 LLMScripts.npc 绝对路径
# 因为 npc 不是顶层模块，是 LLMScripts 的子模块
from LLMScripts.npc import action_tools
from LLMScripts.npc.NPCManager import NPCManager
from LLMScripts.npc.LLMNPCBehavior import LLMNPCBehavior, ActionQueueManager
