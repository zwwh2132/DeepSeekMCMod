# -*- coding: utf-8 -*-
"""
run_command: 执行一条MC游戏指令，可指定执行者
"""
import mod.server.extraServerApi as serverApi
from .base import ActionTool
from .tool_registry import ToolRegistry


class RunCommandAction(ActionTool):
    name = "run_command"
    description = "执行一条Minecraft游戏指令（如give、tp、summon等）。默认以玩家本身身份执行，需要OP权限的指令也能生效。如需指定其他实体执行可传executor_id"
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "要执行的指令，如「give @p diamond 1」、「tp @p 100 64 100」等"},
            "executor_id": {"type": "string", "description": "指令执行者的实体ID。不传则默认以玩家本身身份执行（推荐）"}
        },
        "required": ["command"]
    }

    @classmethod
    def execute(cls, entityId, params, context=None):
        cmd = params.get("command", "").strip()
        executor_id = params.get("executor_id", "").strip()
        print("[run_command] entityId=%s, command=[%s], executor_id=%s" % (entityId, cmd, executor_id))
        if not cmd:
            return {"status": "error", "message": "指令不能为空"}

        # 确保指令以 / 开头
        if not cmd.startswith("/"):
            cmd = "/" + cmd

        # 默认用玩家本身作为执行者
        if not executor_id:
            executor_id = (context or {}).get("playerId", "")
        if not executor_id:
            player_list = serverApi.GetPlayerList()
            if player_list:
                executor_id = player_list[0]

        cmd_comp = serverApi.GetEngineCompFactory().CreateCommand(serverApi.GetLevelId())
        result = cmd_comp.SetCommand(cmd, executor_id, False)
        print("[run_command] result=%s, full_cmd=[%s], executor=%s" % (result, cmd, executor_id))
        if result:
            return {"status": "ok", "message": "指令已执行: %s" % cmd}
        return {"status": "error", "message": "指令执行失败: %s" % cmd}


ToolRegistry.register(RunCommandAction)
