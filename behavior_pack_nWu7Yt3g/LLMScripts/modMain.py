# -*- coding: utf-8 -*-

from mod.common.mod import Mod
import mod.server.extraServerApi as serverApi


@Mod.Binding(name="LLMTestMod", version="0.0.1")
class LLMTestMod(object):

    def __init__(self):
        pass

    @Mod.InitServer()
    def LLMTestModServerInit(self):
        serverApi.RegisterSystem(
            "LLMTestMod",
            "LLMServerSystem",
            "LLMScripts.LLMServerSystem.LLMServerSystem"
        )
        # MCP 控制器系统 — 完全独立，不依赖 NPC 系统
        serverApi.RegisterSystem(
            "LLMTestMod",
            "MCPControllerSystem",
            "LLMScripts.MCPControllerSystem.MCPControllerSystem"
        )

    @Mod.DestroyServer()
    def LLMTestModServerDestroy(self):
        pass

    @Mod.InitClient()
    def LLMTestModClientInit(self):
        import mod.client.extraClientApi as clientApi
        clientApi.RegisterSystem(
            "LLMTestMod",
            "LLMClientSystem",
            "LLMScripts.LLMClientSystem.LLMClientSystem"
        )

    @Mod.DestroyClient()
    def LLMTestModClientDestroy(self):
        pass
