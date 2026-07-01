# -*- coding: utf-8 -*-
"""
DeepSeek Bridge GUI - AI聊天模组外部伴生程序（图形界面版）
v3 - MCP 风格工具调用支持
"""
import Tkinter as tk
import ttk
import tkMessageBox
import threading
import json
import urllib2
import os
import sys
import SocketServer
from datetime import datetime

reload(sys)
sys.setdefaultencoding("utf-8")

# ===== 默认配置 =====
DEFAULT_CONFIG = {
    "api_key": "",
    "port": 19999,
    "model": "deepseek-v4-flash"
}
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bridge_config.json")
# ====================

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"


def load_config():
    """加载本地配置文件"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                cfg = json.load(f)
                for k in DEFAULT_CONFIG:
                    if k not in cfg:
                        cfg[k] = DEFAULT_CONFIG[k]
                return cfg
        except:
            pass
    return dict(DEFAULT_CONFIG)


def save_config(cfg):
    """保存配置到本地文件"""
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(cfg, f, indent=2)
        return True
    except:
        return False


class BridgeServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


class BridgeHandler(SocketServer.BaseRequestHandler):
    """实际处理请求的 Handler（MCP 风格）"""

    def handle(self):
        try:
            # 先接收数据长度（4字节大端整数）
            raw_len_data = self.request.recv(4)
            if len(raw_len_data) < 4:
                return
            import struct
            expected_len = struct.unpack(">I", raw_len_data)[0]

            # 循环接收直到收完整
            chunks = []
            remaining = expected_len
            while remaining > 0:
                chunk = self.request.recv(min(remaining, 65536))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            raw = "".join(chunks)
            raw = raw.decode("utf-8").strip()
            try:
                payload = json.loads(raw)
                messages = payload.get("messages", [])
                tools = payload.get("tools", [])
            except (ValueError, TypeError):
                messages = [{"role": "user", "content": raw}]
                tools = []

            if not messages:
                self.request.sendall("")
                return

            self.server.gui.log("[Bridge] 收到请求: %d 条消息, %d 个工具定义" % (len(messages), len(tools)))
            reply = self._call_deepseek(messages, tools)
            try:
                self.request.sendall(reply.encode("utf-8"))
            except Exception as e:
                self.server.gui.log("[Bridge] 发送响应失败: %s" % e)
            self.server.gui.log("[Bridge] 回复: %s" % reply[:80])

        except Exception as e:
            try:
                self.request.sendall(("[Error] %s" % str(e)).encode("utf-8"))
            except:
                pass
            if hasattr(self, 'server') and hasattr(self.server, 'gui'):
                self.server.gui.log("[Error] %s" % str(e))

    def _call_deepseek(self, messages, tools):
        """调用 DeepSeek API，支持 function calling"""
        cfg = self.server.gui.get_config()
        api_key = cfg["api_key"]
        model = cfg["model"]

        post_data = {
            "model": model,
            "messages": messages,
            "stream": False,
            "max_tokens": 8192,
            "temperature": 0.7
        }

        if tools:
            # 请求中携带工具定义供模型调用
            for t in tools:
                func = t.get("function", {})
                if func:
                    func["strict"] = True
            post_data["tools"] = tools
            post_data["tool_choice"] = "auto"

        try:
            req = urllib2.Request(
                DEEPSEEK_API_URL,
                data=json.dumps(post_data),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer %s" % api_key
                }
            )
            response = urllib2.urlopen(req, timeout=60)
            result = json.loads(response.read())
        except urllib2.HTTPError as e:
            err_body = e.read()
            self.server.gui.log("[Bridge] API HTTP %d: %s" % (e.code, err_body[:100]))
            return json.dumps({"text": "[Error] API请求失败 HTTP %d" % e.code, "tool_calls": []})
        except urllib2.URLError as e:
            self.server.gui.log("[Bridge] API连接失败: %s" % str(e.reason))
            return json.dumps({"text": "[Error] API连接失败: %s" % str(e.reason), "tool_calls": []})
        except Exception as e:
            self.server.gui.log("[Bridge] API异常: %s" % str(e))
            return json.dumps({"text": "[Error] %s" % str(e), "tool_calls": []})

        # 解析响应
        try:
            choice = result["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as e:
            self.server.gui.log("[Bridge] API返回格式异常: %s" % str(e))
            return json.dumps({"text": "[Error] API返回格式异常", "tool_calls": []})

        result_data = {
            "text": choice.get("content", ""),
            "tool_calls": []
        }

        # 处理 tool_calls（OpenAI 原生格式）
        if choice.get("tool_calls"):
            for tc in choice["tool_calls"]:
                func = tc.get("function", {})
                try:
                    args = json.loads(func.get("arguments", "{}"))
                except (ValueError, TypeError):
                    args = {}
                result_data["tool_calls"].append({
                    "name": func.get("name", ""),
                    "args": args
                })
            self.server.gui.log("[Bridge] LLM调用了 %d 个工具" % len(result_data["tool_calls"]))
        else:
            # 兜底：尝试从文本中解析 JSON（模型有时输出文本格式而非原生 tool_calls）
            content = (result_data["text"] or "").strip()
            # 情况1：content 本身就是完整 JSON
            if content.startswith("{"):
                try:
                    parsed = json.loads(content)
                    if parsed.get("tool_calls"):
                        result_data["text"] = parsed.get("text", "")
                        result_data["tool_calls"] = parsed.get("tool_calls", [])
                        self.server.gui.log("[Bridge] 从文本中解析出 %d 个工具调用" % len(result_data["tool_calls"]))
                except (ValueError, TypeError):
                    pass
            # 情况2：content 里混了 tool_calls 但不是标准 JSON（DeepSeek 偶发）
            # 例如：text="说点啥", "tool_calls": [...]  这种残缺格式
            if not result_data["tool_calls"] and '"tool_calls"' in content:
                import re
                # 尝试提取 content 中第一个 { 到最后一个 } 的内容
                match = re.search(r'\{.*\}', content, re.DOTALL)
                if match:
                    try:
                        parsed = json.loads(match.group(0))
                        if parsed.get("tool_calls"):
                            result_data["text"] = parsed.get("text", "")
                            result_data["tool_calls"] = parsed.get("tool_calls", [])
                            self.server.gui.log("[Bridge] 从混合文本中提取出 %d 个工具调用" % len(result_data["tool_calls"]))
                    except (ValueError, TypeError):
                        pass

        return json.dumps(result_data, ensure_ascii=False)


class BridgeGUI:
    def __init__(self):
        self.window = tk.Tk()
        self.window.title("DeepSeek Bridge v3 - MCP Tool Calling")
        self.window.geometry("650x500")
        self.window.resizable(True, True)

        self.server = None
        self.server_thread = None
        self.running = False

        # 线程安全的日志队列，工作线程写入，主线程定期消费
        import Queue
        self._log_queue = Queue.Queue()

        self._build_ui()
        self._load_config_to_ui()
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)
        # 定期处理日志队列
        self.window.after(100, self._drain_log_queue)

    def _build_ui(self):
        # ===== 顶部：配置区域 =====
        frame_cfg = ttk.LabelFrame(self.window, text="配置", padding=10)
        frame_cfg.pack(fill="x", padx=10, pady=5)

        # API Key
        row1 = ttk.Frame(frame_cfg)
        row1.pack(fill="x", pady=2)
        ttk.Label(row1, text="API Key:", width=12).pack(side="left")
        self.api_key_var = tk.StringVar()
        self.api_key_entry = ttk.Entry(row1, textvariable=self.api_key_var, show="*")
        self.api_key_entry.pack(side="left", fill="x", expand=True)
        self.show_key_btn = ttk.Button(row1, text="显示", width=5, command=self._toggle_key_visible)
        self.show_key_btn.pack(side="right", padx=2)
        self._key_visible = False

        # 第二行：端口 + 模型
        row2 = ttk.Frame(frame_cfg)
        row2.pack(fill="x", pady=2)
        ttk.Label(row2, text="端口:", width=12).pack(side="left")
        self.port_var = tk.StringVar(value="19999")
        ttk.Entry(row2, textvariable=self.port_var, width=8).pack(side="left", padx=2)
        ttk.Label(row2, text="  模型:").pack(side="left")
        self.model_var = tk.StringVar(value="deepseek-v4-flash")
        ttk.Entry(row2, textvariable=self.model_var, width=25).pack(side="left", padx=2)

        # 第三行：按钮
        row3 = ttk.Frame(frame_cfg)
        row3.pack(fill="x", pady=5)
        self.start_btn = ttk.Button(row3, text="启动服务", command=self._toggle_server, width=15)
        self.start_btn.pack(side="left", padx=2)
        self.save_btn = ttk.Button(row3, text="保存配置", command=self._save_config, width=10)
        self.save_btn.pack(side="left", padx=2)
        self.status_label = ttk.Label(row3, text="  已停止", foreground="gray")
        self.status_label.pack(side="left", padx=10)

        # ===== 中间：日志区域 =====
        frame_log = ttk.LabelFrame(self.window, text="日志", padding=5)
        frame_log.pack(fill="both", expand=True, padx=10, pady=5)

        log_frame = ttk.Frame(frame_log)
        log_frame.pack(fill="both", expand=True)

        scrollbar = ttk.Scrollbar(log_frame)
        scrollbar.pack(side="right", fill="y")

        self.log_text = tk.Text(log_frame, height=12, wrap="word", state="disabled",
                                 yscrollcommand=scrollbar.set, font=("Consolas", 9))
        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.log_text.yview)

        # 清空日志按钮
        btn_row = ttk.Frame(frame_log)
        btn_row.pack(fill="x", pady=2)
        ttk.Button(btn_row, text="清空日志", command=self._clear_log, width=10).pack(side="left")

    def _toggle_key_visible(self):
        self._key_visible = not self._key_visible
        self.api_key_entry.config(show="" if self._key_visible else "*")
        self.show_key_btn.config(text="隐藏" if self._key_visible else "显示")

    def _load_config_to_ui(self):
        cfg = load_config()
        self.api_key_var.set(cfg.get("api_key", ""))
        self.port_var.set(str(cfg.get("port", 19999)))
        self.model_var.set(cfg.get("model", "deepseek-v4-flash"))

    def get_config(self):
        return {
            "api_key": self.api_key_var.get().strip(),
            "port": int(self.port_var.get().strip()),
            "model": self.model_var.get().strip()
        }

    def _save_config(self):
        try:
            cfg = self.get_config()
            if not cfg["api_key"]:
                tkMessageBox.showwarning("提示", "API Key 不能为空")
                return
            int(self.port_var.get().strip())
        except ValueError:
            tkMessageBox.showerror("错误", "端口必须为数字")
            return
        if save_config(cfg):
            self.log("配置已保存")
            tkMessageBox.showinfo("成功", "配置已保存到 bridge_config.json")
        else:
            self.log("配置保存失败")
            tkMessageBox.showerror("错误", "配置保存失败")

    def _toggle_server(self):
        if self.running:
            self._stop_server()
        else:
            self._start_server()

    def _start_server(self):
        cfg = self.get_config()
        if not cfg["api_key"]:
            tkMessageBox.showwarning("提示", "请先填写 API Key")
            return
        try:
            port = int(self.port_var.get().strip())
        except ValueError:
            tkMessageBox.showerror("错误", "端口必须为数字")
            return

        try:
            BridgeServer.allow_reuse_address = True
            self.server = BridgeServer(("127.0.0.1", port), BridgeHandler)
            self.server.gui = self

            self.server_thread = threading.Thread(target=self.server.serve_forever)
            self.server_thread.daemon = True
            self.server_thread.start()

            self.running = True
            self.start_btn.config(text="停止服务")
            self.status_label.config(text="  运行中 (端口:%d)" % port, foreground="green")
            self._set_config_editable(False)
            self.log("服务已启动，监听端口 %d。支持 MCP function calling" % port)
        except Exception as e:
            tkMessageBox.showerror("错误", "启动失败: %s" % str(e))
            self.log("启动失败: %s" % str(e))

    def _stop_server(self):
        if self.server:
            try:
                self.server.shutdown()
                self.server.server_close()
            except:
                pass
            self.server = None

        self.running = False
        self.start_btn.config(text="启动服务")
        self.status_label.config(text="  已停止", foreground="gray")
        self._set_config_editable(True)
        self.log("服务已停止")

    def _set_config_editable(self, editable):
        state = "normal" if editable else "disabled"
        self.api_key_entry.config(state=state)

    def _clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete(1.0, "end")
        self.log_text.config(state="disabled")

    def log(self, msg):
        """工作线程调用：把日志放入队列，由主线程消费"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = "[%s] %s" % (timestamp, msg)
        try:
            print(line)
        except (IOError, UnicodeEncodeError):
            pass
        self._log_queue.put(line)

    def _drain_log_queue(self):
        """主线程定期消费日志队列，写入 GUI"""
        try:
            while True:
                line = self._log_queue.get_nowait()
                self.log_text.config(state="normal")
                self.log_text.insert("end", line + "\n")
                self.log_text.see("end")
                self.log_text.config(state="disabled")
        except:
            pass
        self.window.after(100, self._drain_log_queue)

    def _on_close(self):
        if self.running:
            if not tkMessageBox.askokcancel("退出", "服务正在运行，确定要退出吗？"):
                return
            self._stop_server()
        self.window.destroy()

    def run(self):
        self.log("DeepSeek Bridge v3 - MCP Tool Calling")
        self.log("请配置 API Key 后点击「启动服务」")
        self.window.mainloop()


if __name__ == "__main__":
    gui = BridgeGUI()
    gui.run()
