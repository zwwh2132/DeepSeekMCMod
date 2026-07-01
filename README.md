# LLMTestMod — AI 聊天测试模组

网易《我的世界》基岩版模组，将 AI（DeepSeek）接入游戏，支持与 NPC 实体对话、AI 问答，以及通过 MCP 协议远程控制游戏。

## 整体架构

```
┌──────────────────────────────────────────────────────────────┐
│                       游戏内（模组）                          │
│                                                              │
│  LLMServerSystem ←→ NPCConversation ←→ Bridge(TCP:19999)    │
│       ↑                    ↑                                 │
│   /ainpc 指令         @NPC 聊天触发                           │
│                                                              │
│  MCPControllerSystem ←→ TCP:19997 ←→ mc_mcp_server.py       │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

- **LLMServerSystem** — 模组服务端，处理指令、管理对话、执行工具
- **NPCConversation** — 对话管理器，管理每个 NPC 的对话历史和 Bridge 通信
- **DEEPSEEK_BRIDGE_GUI.py** — DeepSeek API 桥梁程序（TCP:19999），转发请求并处理工具调用
- **MCPControllerSystem** — MCP 控制端系统（TCP:19997），接收外部命令在游戏内执行
- **mc_mcp_server.py** — MCP 协议服务器，将 IDE（如 Trae）的 MCP 请求转发给游戏模组

---

## 快速开始

### 1. 准备工作

1. 使用 [MC Studio](https://mc.163.com/) 打开此项目
2. 确保 Python 3 已安装，并在 PATH 中可用（用于运行 `mc_mcp_server.py`）

### 2. 启动 DeepSeek Bridge（AI 对话必需）

```bash
# 方式一：直接双击运行
DEEPSEEK_BRIDGE_GUI.py

# 方式二：命令行运行
python DEEPSEEK_BRIDGE_GUI.py
```

启动后：
1. 在窗口内填写 DeepSeek **API Key**
2. 点击 **保存配置**
3. 点击 **启动服务**（默认端口 19999）

> 配置文件保存在 `bridge_config.json`，下次启动会自动加载。

### 3. 启动游戏并加载模组

在 MC Studio 中启动游戏，该模组会自动加载。加载成功后，在游戏聊天栏输入指令即可使用。

### 4. 启动 MCP Server（IDE 远程控制，可选）

```bash
py -3 mc_mcp_server.py --stdio
```

---

## 游戏内指令

### AI 全局对话

| 指令 | 说明 |
|------|------|
| `/ai <问题>` | 向 AI 提问，全服可见 |

### NPC 管理

| 指令 | 说明 |
|------|------|
| `/ainpcs` | 列出所有可用的 NPC 模板配置 |
| `/ainpc <名字> <问题>` | 与指定 NPC 对话 |
| `/ainpc_spawn <模板> [名字]` | 在当前位置生成一个 NPC 实体 |
| `/ainpc_list` | 列出所有已生成的 NPC 实体 |
| `/ainpc_despawn [名字]` | 移除指定（或全部）NPC 实体 |
| `/ainpc_clear <名字>` | 清除指定 NPC 的对话历史 |
| `/ainpc_clear_all` | 清除所有 NPC 的对话历史 |
| `/aiclear` | 清除默认 AI 的对话历史 |

### 与 NPC 对话

除了用 `/ainpc` 指令，还可以在聊天栏输入：

```
@战士 你好！
@老村民 附近有村庄吗？
```

即用 `@NPC名字` 开头即可与该 NPC 对话。

### NPC 模板配置

项目内置了以下 NPC 模板（在游戏中使用 `/ainpcs` 查看）：

- **default** — 默认 AI 助手
- **old_villager** — 老村民
- **warrior** — 战士

NPC 模板定义在 `LLMScripts/npc/profiles/` 目录下，可以修改或新增。

---

## MCP 服务器 — 在 IDE 中使用

MCP（Model Context Protocol）服务器让你可以在 AI IDE（如 Trae、Cursor、VS Code + Continue 等）中直接控制 Minecraft 游戏。

### 工作原理

```
IDE (Trae) ──[MCP stdio]──→ mc_mcp_server.py ──[TCP:19997]──→ 游戏模组
```

IDE 通过标准输入/输出与 `mc_mcp_server.py` 通信，该脚本将 MCP 工具调用请求通过 TCP 转发到已在运行的游戏中执行。

### 在 Trae IDE 中配置

1. 打开 Trae IDE 的 **MCP 设置** 界面
2. 添加一个新的 MCP 服务器，配置如下：

   ```json
   {
     "mcpServers": {
       "mc_control": {
         "command": "py",
         "args": [
           "-3",
           "D:\\MCStudioDownload\\work\\z2710468140@163.com\\Cpp\\AddOn\\LLMTestMod\\mc_mcp_server.py",
           "--stdio"
         ]
       }
     }
   }
   ```

3. 保存后，IDE 会自动启动 MCP 服务器
4. 确保游戏已启动且模组已加载（MCPControllerSystem 会监听 127.0.0.1:19997）

> **注意：** 必须先启动游戏加载模组，MCP 服务器才能连接到游戏。如果游戏未运行，工具调用会返回"连接失败"错误。

### 可用 MCP 工具

配置成功后，你可以在 IDE 中通过 AI 直接执行以下操作：

| 工具名 | 说明 |
|--------|------|
| `mc_execute` | 执行任意游戏指令（give、tp、summon 等） |
| `mc_time_set` | 设置游戏时间（0=黎明，6000=中午，12000=夜晚） |
| `mc_weather_set` | 设置天气（clear/rain/thunder） |
| `mc_summon` | 在指定位置生成实体 |
| `mc_kill` | 清除指定类型的实体 |
| `mc_effect` | 给玩家或实体添加状态效果 |
| `mc_give_item` | 给指定玩家发放物品 |
| `mc_teleport` | 传送玩家或实体到指定坐标 |
| `mc_list_players` | 列出所有在线玩家 |
| `mc_inject_python` | 在模组服务端执行任意 Python 代码 |
| `mc_listen_event` | 注册监听游戏事件（如弹射物命中、实体生成等） |
| `mc_get_event_records` | 获取监听到的事件记录 |
| `mc_stop_listen` | 停止事件监听 |
| `mc_read_log` | 读取模组运行日志 |
| `mc_clear_log` | 清空模组运行日志 |

### 使用示例（IDE 中问 AI）

```
AI，帮我把时间设为白天。

AI，在我脚下生成一只苦力怕。

AI，监听一下 ProjectileDoHitEffectEvent，告诉我射出去的箭打中了什么。

AI，帮我把库存里的所有玩家列表列出来。
```

这些对话会被 IDE 中的 AI 理解，并自动调用对应的 MCP 工具来操纵游戏。

---

## 项目文件结构

```
LLMTestMod/
├── DEEPSEEK_BRIDGE_GUI.py         # DeepSeek API 桥梁程序（图形界面）
├── mc_mcp_server.py                # MCP 服务器（IDE 远程控制）
├── bridge_config.json              # Bridge 配置文件（自动生成）
├── studio.json                     # MC Studio 项目配置
├── work.mcscfg                     # MC Studio 工作区配置
│
├── behavior_pack_nWu7Yt3g/         # 行为包
│   ├── manifest.json
│   ├── entities/zwwh_llm_npc.json              # NPC 实体定义
│   ├── netease_commands/                       # 自定义指令定义
│   │   ├── zwwh_ai.json
│   │   ├── zwwh_aiclear.json
│   │   ├── zwwh_aiconfig.json
│   │   ├── zwwh_ainpc.json
│   │   ├── zwwh_ainpc_spawn.json
│   │   └── ...
│   └── LLMScripts/
│       ├── modMain.py                          # 模组入口
│       ├── LLMServerSystem.py                  # 服务端系统（指令/对话/工具）
│       ├── LLMClientSystem.py                  # 客户端系统
│       ├── MCPControllerSystem.py              # MCP 控制端系统（TCP:19997）
│       ├── __init__.py
│       └── npc/
│           ├── NPCConversation.py              # 对话管理器
│           ├── NPCManager.py                   # NPC 实体管理器
│           ├── NPCProfileManager.py            # NPC 配置管理器
│           ├── LLMNPCBehavior.py               # NPC 行为组件
│           ├── profiles/                       # NPC 模板配置
│           │   ├── default.py
│           │   ├── old_villager.py
│           │   └── warrior.py
│           └── action_tools/                   # NPC 动作工具
│               ├── tool_registry.py            # 工具注册中心
│               ├── base.py                     # 工具基类
│               ├── move_to.py
│               ├── attack_entity.py
│               ├── get_health.py
│               ├── get_pos.py
│               ├── set_block.py
│               ├── break_block.py
│               ├── scan_blocks.py
│               ├── scan_entities.py
│               └── ...
│
└── resource_pack_wGNFBvsB/        # 资源包
    ├── manifest.json
    ├── entity/llm_npc.entity.json              # 实体渲染定义
    ├── models/entity/zwwh_deepseek.geo.json    # 模型
    ├── textures/entity/llm_npc.png             # 贴图
    └── texts/zh_CN.lang                        # 中文语言文件
```

## 常见问题

**Q: 游戏提示 "Bridge 未运行"**
A: 请先启动 `DEEPSEEK_BRIDGE_GUI.py`，填写 API Key 并点击"启动服务"。

**Q: MCP 服务器提示 "连接模组超时"**
A: 请确认游戏已启动且模组已成功加载。MCPControllerSystem 在模组初始化时会自动监听 19997 端口。

**Q: MCP 服务器提示 "ConnectionRefusedError"**
A: 游戏未运行或模组未加载，请先启动游戏。

**Q: NPC 说中文显示乱码**
A: Bridge 和模组之间的通信使用 UTF-8 编码，如果出现乱码请检查系统默认编码设置。
