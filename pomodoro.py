#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pomodoro Timer 番茄钟 — 桌面番茄工作法计时器
Python + tkinter 实现，零外部依赖
"""

import tkinter as tk
from tkinter import ttk
import math
import time
import threading
import winsound


# ============================================================
# 配色方案
# ============================================================
COLOR_BG = "#F5F5F5"           # 浅灰背景
COLOR_SURFACE = "#FFFFFF"      # 白色卡片/面板
COLOR_PRIMARY = "#E34F33"      # 番茄红（主色调）
COLOR_PRIMARY_DIM = "#F0D0C8"  # 浅粉（进度环底色）
COLOR_GREEN = "#4CAF50"        # 休息模式绿色
COLOR_BLUE = "#2196F3"         # 长休息蓝色
COLOR_TEXT = "#333333"         # 深色文字
COLOR_TEXT_DIM = "#999999"     # 次要文字灰色
COLOR_ACCENT = "#FF6B35"       # 橙色强调

# 模式配置: (名称, 默认分钟数, 颜色)
MODES = {
    "work":    ("🍅 工作", 25, COLOR_PRIMARY),
    "break":   ("☕ 短休",  5, COLOR_GREEN),
    "longbreak": ("🌴 长休", 15, COLOR_BLUE),
}

# ============================================================
# 主应用类
# ============================================================
class PomodoroApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Pomodoro 番茄钟")
        self.root.geometry("380x520")
        self.root.minsize(320, 460)
        self.root.configure(bg=COLOR_BG)

        # 窗口置顶
        self.always_on_top = tk.BooleanVar(value=True)
        self.root.attributes("-topmost", True)

        # 状态变量
        self.mode = "work"           # work / break / longbreak
        self.remaining = MODES["work"][1] * 60   # 剩余秒数
        self.total_seconds = self.remaining
        self.timer_state = "idle"    # idle / running / paused
        self.after_id = None
        self.tomato_count = 0

        # 构建界面
        self._build_ui()

        # 窗口居中
        self.root.update_idletasks()
        self._center_window()

        # 绑定关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ========================================================
    # UI 构建
    # ========================================================
    def _build_ui(self):
        # --- 顶部标题栏 ---
        title_frame = tk.Frame(self.root, bg=COLOR_BG)
        title_frame.pack(pady=(18, 0))

        self.title_label = tk.Label(
            title_frame, text="🍅 Pomodoro 番茄钟",
            font=("Microsoft YaHei UI", 16, "bold"),
            fg=COLOR_TEXT, bg=COLOR_BG
        )
        self.title_label.pack()

        # --- 置顶复选框 ---
        top_frame = tk.Frame(self.root, bg=COLOR_BG)
        top_frame.pack(pady=(4, 0))
        top_cb = tk.Checkbutton(
            top_frame, text="窗口置顶", variable=self.always_on_top,
            command=self._toggle_topmost,
            fg=COLOR_TEXT_DIM, bg=COLOR_BG,
            selectcolor=COLOR_SURFACE,
            activebackground=COLOR_BG,
            activeforeground=COLOR_TEXT,
            font=("Microsoft YaHei UI", 9)
        )
        top_cb.pack()

        # --- 进度环 + 计时数字 ---
        self.canvas_size = 260
        self.canvas = tk.Canvas(
            self.root, width=self.canvas_size, height=self.canvas_size,
            bg=COLOR_BG, highlightthickness=0
        )
        self.canvas.pack(pady=(10, 0))

        # 进度环中心文字
        self.progress_arc = None
        self.progress_bg = None
        self.timer_text = None
        self.mode_text = None
        self._draw_progress(1.0)

        # --- 模式切换按钮 ---
        mode_frame = tk.Frame(self.root, bg=COLOR_BG)
        mode_frame.pack(pady=(16, 0))

        self.mode_buttons = {}
        for key in ("work", "break", "longbreak"):
            name, _, color = MODES[key]
            btn = tk.Button(
                mode_frame, text=name,
                font=("Microsoft YaHei UI", 10),
                fg=COLOR_TEXT, bg=COLOR_SURFACE,
                activebackground=color,
                activeforeground="white",
                relief="flat",
                bd=0, padx=12, pady=6,
                cursor="hand2",
                command=lambda k=key: self._switch_mode(k)
            )
            btn.pack(side="left", padx=4)
            self.mode_buttons[key] = btn
        self._highlight_mode_button()

        # --- 控制按钮 ---
        ctrl_frame = tk.Frame(self.root, bg=COLOR_BG)
        ctrl_frame.pack(pady=(16, 0))

        # 开始/暂停按钮
        self.start_pause_btn = tk.Button(
            ctrl_frame, text="▶  开始",
            font=("Microsoft YaHei UI", 12, "bold"),
            fg="white", bg=COLOR_PRIMARY,
            activebackground="#C4402A", activeforeground="white",
            relief="flat", bd=0, padx=24, pady=10,
            cursor="hand2",
            command=self._toggle_start_pause
        )
        self.start_pause_btn.pack(side="left", padx=4)

        # 重置按钮
        self.reset_btn = tk.Button(
            ctrl_frame, text="↺  重置",
            font=("Microsoft YaHei UI", 12, "bold"),
            fg=COLOR_TEXT, bg=COLOR_SURFACE,
            activebackground="#3A3A50", activeforeground=COLOR_TEXT,
            relief="flat", bd=0, padx=24, pady=10,
            cursor="hand2",
            command=self._reset
        )
        self.reset_btn.pack(side="left", padx=4)

        # --- 统计信息 ---
        stats_frame = tk.Frame(self.root, bg=COLOR_BG)
        stats_frame.pack(pady=(16, 18))

        self.stats_label = tk.Label(
            stats_frame,
            text=f"✅ 已完成: {self.tomato_count} 个番茄",
            font=("Microsoft YaHei UI", 10),
            fg=COLOR_TEXT_DIM, bg=COLOR_BG
        )
        self.stats_label.pack()

        # 状态提示
        self.status_label = tk.Label(
            stats_frame,
            text="准备开始专注吧 ✨",
            font=("Microsoft YaHei UI", 9),
            fg=COLOR_TEXT_DIM, bg=COLOR_BG
        )
        self.status_label.pack(pady=(2, 0))

    # ========================================================
    # 进度环绘制
    # ========================================================
    def _draw_progress(self, ratio):
        """绘制圆形进度环，ratio 0.0 ~ 1.0"""
        self.canvas.delete("all")

        cx = self.canvas_size / 2
        cy = self.canvas_size / 2
        r = 100
        width = 12

        mode_color = MODES[self.mode][2]

        # 背景圆环
        self.canvas.create_arc(
            cx - r, cy - r, cx + r, cy + r,
            outline=COLOR_PRIMARY_DIM, width=width,
            style="arc", start=90, extent=-359.9
        )

        # 前景进度弧
        extent = -359.9 * ratio
        self.canvas.create_arc(
            cx - r, cy - r, cx + r, cy + r,
            outline=mode_color, width=width,
            style="arc", start=90, extent=extent
        )

        # 中心计时数字
        mins, secs = divmod(self.remaining, 60)
        time_str = f"{mins:02d}:{secs:02d}"

        self.canvas.create_text(
            cx, cy - 8,
            text=time_str,
            font=("Consolas", 40, "bold"),
            fill=COLOR_TEXT
        )

        # 模式名称
        name, _, _ = MODES[self.mode]
        self.canvas.create_text(
            cx, cy + 28,
            text=name,
            font=("Microsoft YaHei UI", 11),
            fill=COLOR_TEXT_DIM
        )

    # ========================================================
    # 计时逻辑
    # ========================================================
    def _tick(self):
        """每秒计时回调"""
        if self.timer_state != "running":
            return

        if self.remaining > 0:
            self.remaining -= 1
            ratio = self.remaining / self.total_seconds
            self._draw_progress(ratio)
            self.after_id = self.root.after(1000, self._tick)
        else:
            # 计时结束
            self._timer_finished()

    def _timer_finished(self):
        """计时结束处理"""
        self.timer_state = "idle"
        self.after_id = None

        # 工作模式结束时增加番茄计数
        if self.mode == "work":
            self.tomato_count += 1
            self.stats_label.config(text=f"✅ 已完成: {self.tomato_count} 个番茄")

        # 播放提示音
        self._play_sound()

        # 弹窗提示
        name, _, _ = MODES[self.mode]
        self._show_notification(f"{name} 时间到！")

        # 自动切换到下一个模式
        next_mode = self._get_next_mode()
        self._switch_mode(next_mode)

        # 自动开始下一个计时
        self._start()

    def _get_next_mode(self):
        """根据当前模式返回下一个模式"""
        if self.mode == "work":
            # 每4个番茄后长休息，否则短休息
            if self.tomato_count > 0 and self.tomato_count % 4 == 0:
                return "longbreak"
            return "break"
        else:
            return "work"

    def _start(self):
        """开始计时"""
        if self.remaining <= 0:
            # 时间已到，重置为当前模式时长
            _, minutes, _ = MODES[self.mode]
            self.remaining = minutes * 60
            self.total_seconds = self.remaining

        self.timer_state = "running"
        self.start_pause_btn.config(text="⏸  暂停", bg=COLOR_ACCENT)
        self.status_label.config(text="专注中... 🔥")
        self._draw_progress(self.remaining / self.total_seconds)
        self.after_id = self.root.after(1000, self._tick)

    def _pause(self):
        """暂停计时"""
        self.timer_state = "paused"
        if self.after_id:
            self.root.after_cancel(self.after_id)
            self.after_id = None
        self.start_pause_btn.config(text="▶  继续", bg=COLOR_PRIMARY)
        self.status_label.config(text="已暂停 ⏸")

    def _reset(self):
        """重置计时器"""
        if self.after_id:
            self.root.after_cancel(self.after_id)
            self.after_id = None
        self.timer_state = "idle"
        _, minutes, _ = MODES[self.mode]
        self.remaining = minutes * 60
        self.total_seconds = self.remaining
        self.start_pause_btn.config(text="▶  开始", bg=COLOR_PRIMARY)
        self.status_label.config(text="准备开始专注吧 ✨")
        self._draw_progress(1.0)

    def _toggle_start_pause(self):
        """开始/暂停切换"""
        if self.timer_state == "running":
            self._pause()
        else:
            self._start()

    # ========================================================
    # 模式切换
    # ========================================================
    def _switch_mode(self, mode_key):
        """切换工作/休息模式"""
        if self.after_id:
            self.root.after_cancel(self.after_id)
            self.after_id = None

        self.mode = mode_key
        _, minutes, color = MODES[mode_key]
        self.remaining = minutes * 60
        self.total_seconds = self.remaining
        self.timer_state = "idle"

        # 更新开始按钮颜色
        self.start_pause_btn.config(text="▶  开始", bg=color)
        self.status_label.config(text="准备开始专注吧 ✨")

        self._highlight_mode_button()
        self._draw_progress(1.0)

    def _highlight_mode_button(self):
        """高亮当前模式按钮"""
        for key, btn in self.mode_buttons.items():
            if key == self.mode:
                _, _, color = MODES[key]
                btn.config(bg=color, fg="white")
            else:
                btn.config(bg=COLOR_SURFACE, fg=COLOR_TEXT)

    # ========================================================
    # 提示与声音
    # ========================================================
    def _play_sound(self):
        """播放系统提示音（异步线程）"""
        def beep():
            # 三声短促提示
            for _ in range(3):
                winsound.Beep(880, 200)   # A5, 200ms
                time.sleep(0.15)
        t = threading.Thread(target=beep, daemon=True)
        t.start()

    def _show_notification(self, message):
        """弹出置顶消息窗口"""
        popup = tk.Toplevel(self.root)
        popup.title("⏰ 时间到")
        popup.geometry("280x120")
        popup.configure(bg=COLOR_SURFACE)
        popup.attributes("-topmost", True)
        popup.resizable(False, False)

        # 居中于主窗口
        popup.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 280) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 120) // 2
        popup.geometry(f"+{x}+{y}")

        tk.Label(
            popup, text="⏰", font=("Segoe UI Emoji", 28),
            bg=COLOR_SURFACE
        ).pack(pady=(16, 0))

        tk.Label(
            popup, text=message,
            font=("Microsoft YaHei UI", 12, "bold"),
            fg=COLOR_TEXT, bg=COLOR_SURFACE
        ).pack(pady=(4, 0))

        tk.Button(
            popup, text="知道了",
            font=("Microsoft YaHei UI", 10),
            fg="white", bg=COLOR_PRIMARY,
            activebackground="#C4402A", activeforeground="white",
            relief="flat", bd=0, padx=20, pady=6,
            cursor="hand2",
            command=popup.destroy
        ).pack(pady=(10, 0))

        # 5秒后自动关闭
        popup.after(5000, popup.destroy)

    # ========================================================
    # 窗口辅助
    # ========================================================
    def _toggle_topmost(self):
        self.root.attributes("-topmost", self.always_on_top.get())

    def _center_window(self):
        w, h = 380, 520
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _on_close(self):
        if self.after_id:
            self.root.after_cancel(self.after_id)
        self.root.destroy()


# ============================================================
# 入口
# ============================================================
if __name__ == "__main__":
    root = tk.Tk()
    app = PomodoroApp(root)
    root.mainloop()
