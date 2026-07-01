# JSON UI 规范

## 核心原则
- **`@common.xxx` 继承名必须来自官方文档或 vanilla UI 文件，不能凭想象**
- Minecraft JSON UI 和网页前端是两回事，不能用 HTML/CSS 的概念去类比

## 已知正确的控件模板名
| 用途 | 正确名称 | 错误名称 |
|------|----------|----------|
| 按钮 | `@common_buttons.light_text_button` | `@common.button` ❌ |
| 开关 | `@common_toggles.light_text_toggle` | `@common.toggle` ❌ |

## 写 UI JSON 之前的必做步骤
1. 查 Bedrock Wiki (wiki.bedrock.dev/json-ui) 确认控件模板名和变量名
2. 查 mcdk_assistant 的网易版UI文档确认绑定变量名
3. 看项目中已有的 UI JSON 文件参考实际用法
4. 不确定模板名时，宁可问用户也不编造
