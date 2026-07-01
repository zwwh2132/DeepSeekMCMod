# -*- coding: utf-8 -*-
"""
execute_python: 在服务端执行任意 Python 代码（完全权限）
让 NPC 可以动态执行代码来操控游戏，如修改属性、生成实体、调用 SDK API 等。
"""
import sys
from StringIO import StringIO
import mod.server.extraServerApi as serverApi
from .base import ActionTool
from .tool_registry import ToolRegistry


class ExecutePythonAction(ActionTool):
    name = "execute_python"
    description = "在Minecraft服务端执行任意Python代码，可操控游戏的一切（修改属性、生成实体、调用SDK等）。用 code 参数传入你要执行的 Python 代码。代码中可直接使用 serverApi 变量。print() 的输出会返回给你。"
    parameters = {
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "要执行的 Python 2 代码。可直接使用 serverApi 变量调用 SDK。例: print(serverApi.GetPlayerList())"}
        },
        "required": ["code"]
    }

    @classmethod
    def execute(cls, entityId, params, context=None):
        code = params.get("code", "").strip()
        if not code:
            return {"status": "error", "message": "代码不能为空"}

        # 准备执行环境
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            exec(code, {"serverApi": serverApi})
            output = sys.stdout.getvalue().strip()
            if output:
                return {"status": "ok", "message": output}
            return {"status": "ok", "message": "代码已执行，无输出"}
        except Exception as e:
            return {"status": "error", "message": "执行出错: %s" % str(e)}
        finally:
            sys.stdout = old_stdout


ToolRegistry.register(ExecutePythonAction)
