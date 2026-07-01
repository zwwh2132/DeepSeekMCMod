# -*- coding: utf-8 -*-
"""
ActionTool 行为工具包
每个工具是一个独立模块，按需自动注册到 ToolRegistry。
新增工具只需在 action_tools/ 下新建 .py 文件。
"""
# 使用相对导入，因为 action_tools 不是顶层模块
from .base import ActionTool
from .tool_registry import ToolRegistry, BridgeResponseParser
from . import move_to
from . import move_to_player
from . import look_at
from . import follow_player
from . import stop
from . import get_pos
from . import get_health
from . import get_entity_info
from . import scan_entities
from . import scan_blocks
from . import find_block
from . import teleport_to
from . import set_block
from . import break_block
from . import run_command
from . import get_block
from . import get_entity_info
from . import damage_entity
from . import add_effect
from . import set_entity_attr
from . import attack_entity
from . import set_attack_target
from . import execute_python
