# -*- coding: utf-8 -*-

import mod.client.extraClientApi as clientApi


class LLMClientSystem(clientApi.GetClientSystemCls()):

    def __init__(self, namespace, name):
        super(LLMClientSystem, self).__init__(namespace, name)
        print("===== LLMClientSystem 初始化 =====")

        self.ListenForEvent(
            "LLMTestMod",
            "LLMServerSystem",
            "LLMReplyEvent",
            self,
            self._OnLLMReply
        )

        print("===== LLMClientSystem 初始化完成 =====")

    def _OnLLMReply(self, args):
        try:
            message = args.get("message", "")
            if not message:
                return

            print("===== 客户端收到 AI 回复 =====")

            # 获取真实玩家 ID，发回服务端用 NotifyOneMessage 显示在聊天栏
            real_player_id = clientApi.GetLocalPlayerId()
            if real_player_id:
                event_data = self.CreateEventData()
                event_data["playerId"] = real_player_id
                event_data["message"] = message
                self.NotifyToServer("LLMShowChatEvent", event_data)
                print("===== 客户端已发送真实 playerId 到服务端 =====")

        except Exception as e:
            print("===== _OnLLMReply 出错: %s =====" % str(e))

    def Destroy(self):
        print("===== LLMClientSystem 销毁 =====")
