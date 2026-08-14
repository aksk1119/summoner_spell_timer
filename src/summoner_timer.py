import sys
import time
import tkinter as tk
from functools import partial
from tkinter import messagebox, ttk

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _user32 = ctypes.windll.user32
    # 32-bit user32.dll doesn't export the "Ptr" variants at all.
    if ctypes.sizeof(ctypes.c_void_p) == 8:
        _LONG_PTR = ctypes.c_longlong
        _GetWindowLong = _user32.GetWindowLongPtrW
        _SetWindowLong = _user32.SetWindowLongPtrW
    else:
        _LONG_PTR = ctypes.c_long
        _GetWindowLong = _user32.GetWindowLongW
        _SetWindowLong = _user32.SetWindowLongW

    _GetWindowLong.restype = _LONG_PTR
    _GetWindowLong.argtypes = [wintypes.HWND, ctypes.c_int]
    _SetWindowLong.restype = _LONG_PTR
    _SetWindowLong.argtypes = [wintypes.HWND, ctypes.c_int, _LONG_PTR]
    _user32.SetWindowPos.argtypes = [
        wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
        ctypes.c_int, ctypes.c_int, wintypes.UINT,
    ]
    _user32.SetLayeredWindowAttributes.argtypes = [
        wintypes.HWND, wintypes.COLORREF, wintypes.BYTE, wintypes.DWORD,
    ]

    _GWL_EXSTYLE = -20
    _WS_EX_LAYERED = 0x00080000
    _WS_EX_TOPMOST = 0x00000008
    _WS_EX_NOACTIVATE = 0x08000000
    _WS_EX_TOOLWINDOW = 0x00000080
    _HWND_TOPMOST = -1
    _SWP_NOMOVE = 0x0002
    _SWP_NOSIZE = 0x0001
    _SWP_NOACTIVATE = 0x0010
    _LWA_ALPHA = 0x2

    def _apply_overlay_styles(hwnd, alpha):
        """One-time style setup. Changing GWL_EXSTYLE resets the layered
        window's alpha, so it must be reapplied via SetLayeredWindowAttributes
        right after, otherwise the overlay renders fully transparent/invisible."""
        ex_style = _GetWindowLong(hwnd, _GWL_EXSTYLE)
        ex_style |= _WS_EX_LAYERED | _WS_EX_TOPMOST | _WS_EX_NOACTIVATE | _WS_EX_TOOLWINDOW
        _SetWindowLong(hwnd, _GWL_EXSTYLE, ex_style)
        _user32.SetLayeredWindowAttributes(hwnd, 0, int(alpha * 255), _LWA_ALPHA)

    def _force_topmost(hwnd):
        """Reassert HWND_TOPMOST z-order only, so fullscreen games can't bury the overlay."""
        _user32.SetWindowPos(
            hwnd, _HWND_TOPMOST, 0, 0, 0, 0,
            _SWP_NOMOVE | _SWP_NOSIZE | _SWP_NOACTIVATE,
        )
else:
    def _apply_overlay_styles(hwnd, alpha):
        pass

    def _force_topmost(hwnd):
        pass


SPELL_COOLDOWNS = {
    "Barrier": 180,
    "Cleanse": 240,
    "Exhaust": 240,
    "Flash": 300,
    "Ghost": 210,
    "Heal": 240,
    "Ignite": 180,
    "Smite": 90,
    "Teleport": 360,
}
COSMIC_INSIGHT_SUMMONER_HASTE = 18
TIMER_OFFSET_SECONDS = 5


class CountdownTimer:
    def __init__(self, duration_seconds=0, clock=time.monotonic):
        self.duration_seconds = duration_seconds
        self._clock = clock
        self._deadline = None

    @property
    def is_running(self):
        return self._deadline is not None and self.remaining_seconds > 0

    @property
    def remaining_seconds(self):
        if self._deadline is None:
            return 0
        return max(0, int(self._deadline - self._clock() + 0.999))

    def start(self, duration_seconds=None):
        if duration_seconds is not None:
            self.duration_seconds = duration_seconds
        self._deadline = self._clock() + self.duration_seconds

    def reset(self):
        self._deadline = None


def format_time(seconds):
    minutes, seconds = divmod(max(0, seconds), 60)
    return "{:02d}:{:02d}".format(minutes, seconds)


class GameClock:
    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._start = None

    @property
    def is_running(self):
        return self._start is not None

    @property
    def elapsed_seconds(self):
        if self._start is None:
            return 0
        return int(self._clock() - self._start)

    def start(self):
        if self._start is None:
            self._start = self._clock()

    def reset(self):
        self._start = None


def adjusted_cooldown(base_seconds, cosmic_insight=False):
    if not cosmic_insight:
        return base_seconds
    return base_seconds / (1 + COSMIC_INSIGHT_SUMMONER_HASTE / 100.0)


def tracking_duration(base_seconds, cosmic_insight=False):
    cooldown = adjusted_cooldown(base_seconds, cosmic_insight)
    return max(0, cooldown - TIMER_OFFSET_SECONDS)


class SpellTimer(ttk.Frame):
    def __init__(self, parent, spell_name="Flash", cosmic_insight=None, shortcut="", game_clock=None):
        ttk.Frame.__init__(self, parent, style="Timer.TFrame", padding=(7, 5))
        self.timer = CountdownTimer()
        self.cosmic_insight = cosmic_insight
        self.game_clock = game_clock
        self.shortcut = shortcut
        self.spell_name = tk.StringVar(value=spell_name)
        self.cooldown = tk.StringVar(value=str(SPELL_COOLDOWNS[spell_name]))
        self.time_text = tk.StringVar(value="READY")
        self.ready_at_text = tk.StringVar(value="")
        self._ready_at_game_seconds = None

        self.spell_box = ttk.Combobox(
            self,
            textvariable=self.spell_name,
            values=sorted(SPELL_COOLDOWNS),
            state="readonly",
            width=9,
        )
        self.spell_box.grid(row=0, column=0, padx=(0, 5), sticky="w")
        self.spell_box.bind("<<ComboboxSelected>>", self._select_spell)

        cooldown_box = ttk.Spinbox(
            self,
            from_=1,
            to=999,
            textvariable=self.cooldown,
            width=4,
            justify="center",
        )
        cooldown_box.grid(row=0, column=1, padx=(0, 5))

        self.time_label = ttk.Label(
            self,
            textvariable=self.time_text,
            style="Ready.Timer.TLabel",
            width=6,
            anchor="center",
        )
        self.time_label.grid(row=0, column=2, padx=(0, 5))

        self.start_button = ttk.Button(
            self,
            text="Start [{}]".format(shortcut),
            command=self.start,
            width=8,
        )
        self.start_button.grid(row=0, column=3, padx=(0, 3))
        ttk.Button(
            self,
            text="Reset [Ctrl+{}]".format(shortcut),
            command=self.reset,
            width=12,
        ).grid(row=0, column=4)
        ttk.Label(
            self,
            textvariable=self.ready_at_text,
            style="ReadyAt.Timer.TLabel",
            width=7,
            anchor="center",
        ).grid(row=0, column=5, padx=(5, 0))

    def _select_spell(self, _event=None):
        self.cooldown.set(str(SPELL_COOLDOWNS[self.spell_name.get()]))
        self.reset()

    def start(self):
        if self.timer.is_running:
            return

        try:
            duration = int(self.cooldown.get())
            if duration <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid cooldown", "Cooldown must be a positive number.")
            return

        has_cosmic_insight = (
            self.cosmic_insight is not None and self.cosmic_insight.get()
        )
        self.timer.start(tracking_duration(duration, has_cosmic_insight))
        if self.game_clock is not None and self.game_clock.is_running:
            self._ready_at_game_seconds = self.game_clock.elapsed_seconds + self.timer.duration_seconds
        else:
            self._ready_at_game_seconds = None
        self.refresh()

    def reset(self):
        self._ready_at_game_seconds = None
        self.timer.reset()
        self.refresh()

    def refresh(self):
        remaining = self.timer.remaining_seconds
        if self.timer.is_running:
            self.time_text.set(format_time(remaining))
            self.time_label.configure(style="Running.Timer.TLabel")
            self.start_button.state(["disabled"])
            if self._ready_at_game_seconds is not None:
                self.ready_at_text.set(format_time(self._ready_at_game_seconds))
            else:
                self.ready_at_text.set("")
        else:
            self.time_text.set("READY")
            self.time_label.configure(style="Ready.Timer.TLabel")
            self.start_button.state(["!disabled"])
            self.ready_at_text.set("")


class SummonerRow(ttk.Frame):
    def __init__(self, parent, row_number, shortcuts, game_clock=None):
        ttk.Frame.__init__(self, parent, style="Row.TFrame", padding=(8, 6))
        self.columnconfigure(1, weight=1)
        self.name = tk.StringVar(value="Enemy {}".format(row_number))
        self.cosmic_insight = tk.BooleanVar(value=False)

        identity = ttk.Frame(self, style="Row.TFrame")
        identity.grid(row=0, column=0, padx=(0, 8), sticky="w")
        ttk.Entry(identity, textvariable=self.name, width=13).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Checkbutton(
            identity,
            text="Cosmic Insight",
            variable=self.cosmic_insight,
            style="Row.TCheckbutton",
        ).grid(row=0, column=1, sticky="w", padx=(7, 0))

        self.spells = (
            SpellTimer(self, "Flash", self.cosmic_insight, shortcuts[0], game_clock),
            SpellTimer(self, "Ignite", self.cosmic_insight, shortcuts[1], game_clock),
        )
        self.spells[0].grid(row=0, column=1, padx=(0, 5), sticky="ew")
        self.spells[1].grid(row=0, column=2, sticky="ew")

    def reset(self):
        for spell in self.spells:
            spell.reset()

    def refresh(self):
        for spell in self.spells:
            spell.refresh()


class OverlayWindow(tk.Toplevel):
    """Compact transparent overlay; mouse-only, no keyboard bindings."""

    _ALPHA_DEFAULT = 0.85
    _BG = "#0d1117"
    _BAR_BG = "#1a2430"

    def __init__(self, parent_app):
        super().__init__(parent_app.root)
        self._app = parent_app
        self._drag_x = self._drag_y = 0
        self._spell_entries = []  # (timer_label, start_btn, spell)

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self._alpha_var = tk.DoubleVar(value=self._ALPHA_DEFAULT)
        self.attributes("-alpha", self._ALPHA_DEFAULT)
        self.configure(bg=self._BG)
        self.resizable(False, False)

        self._build()
        self._reposition()
        self.update_idletasks()
        _apply_overlay_styles(self.winfo_id(), self._alpha_var.get())
        _force_topmost(self.winfo_id())

    def _build(self):
        bar = tk.Frame(self, bg=self._BAR_BG, height=26)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        title = tk.Label(bar, text="\u25a3 Spell Timer", bg=self._BAR_BG, fg="#98a7b3",
                         font=("Segoe UI", 9))
        title.pack(side="left", padx=(6, 4))

        tk.Label(
            bar, textvariable=self._app.game_time_text,
            bg=self._BAR_BG, fg="#c8b060", font=("Consolas", 9, "bold"),
        ).pack(side="left", padx=(0, 10))

        tk.Label(bar, text="Opacity", bg=self._BAR_BG, fg="#98a7b3",
                 font=("Segoe UI", 8)).pack(side="left")
        tk.Scale(
            bar, from_=0.2, to=1.0, resolution=0.05,
            variable=self._alpha_var, orient="horizontal", length=80,
            bg=self._BAR_BG, fg="#98a7b3", troughcolor="#2d3d4c",
            highlightthickness=0, showvalue=False,
            command=lambda _: self.attributes("-alpha", self._alpha_var.get()),
        ).pack(side="left", padx=(2, 8))

        tk.Button(
            bar, text="\u00d7", bg=self._BAR_BG, fg="#ff6b6b",
            font=("Segoe UI", 11, "bold"), bd=0, padx=4, pady=0,
            activebackground="#2d3d4c", command=self._close,
        ).pack(side="right")
        tk.Button(
            bar, text="Edit", bg=self._BAR_BG, fg="#98a7b3",
            font=("Segoe UI", 8), bd=0, padx=5, pady=0,
            activebackground="#2d3d4c", command=self._open_editor,
        ).pack(side="right", padx=(0, 2))

        for w in (bar, title):
            w.bind("<ButtonPress-1>", self._drag_start)
            w.bind("<B1-Motion>", self._drag_move)

        body = tk.Frame(self, bg=self._BG, padx=5, pady=3)
        body.pack(fill="both", expand=True)

        for row in self._app.rows:
            rf = tk.Frame(body, bg=self._BG)
            rf.pack(fill="x", pady=1)

            tk.Label(
                rf, textvariable=row.name,
                bg=self._BG, fg="#98a7b3",
                font=("Segoe UI", 9), width=10, anchor="w",
            ).pack(side="left", padx=(0, 3))

            for spell in row.spells:
                sf = tk.Frame(rf, bg="#141c24", padx=2, pady=1)
                sf.pack(side="left", padx=2)

                tk.Label(
                    sf, textvariable=spell.spell_name,
                    bg="#141c24", fg="#c8d0d6",
                    font=("Segoe UI", 9), width=7, anchor="w",
                ).pack(side="left")

                timer_lbl = tk.Label(
                    sf, textvariable=spell.time_text,
                    bg="#173c32", fg="#72e0b1",
                    font=("Consolas", 9, "bold"), width=6, anchor="center",
                )
                timer_lbl.pack(side="left", padx=2)

                start_btn = tk.Button(
                    sf, text="\u25b6", bd=0, padx=3, pady=0,
                    bg="#33414c", fg="#f4f0e8", font=("Segoe UI", 7),
                    activebackground="#496070", command=spell.start,
                )
                start_btn.pack(side="left")
                tk.Button(
                    sf, text="\u21ba", bd=0, padx=3, pady=0,
                    bg="#33414c", fg="#ff9a82", font=("Segoe UI", 7),
                    activebackground="#496070", command=spell.reset,
                ).pack(side="left", padx=(1, 0))

                self._spell_entries.append((timer_lbl, start_btn, spell))

    def _drag_start(self, event):
        self._drag_x, self._drag_y = event.x, event.y

    def _drag_move(self, event):
        x = self.winfo_x() + event.x - self._drag_x
        y = self.winfo_y() + event.y - self._drag_y
        self.geometry(f"+{x}+{y}")

    def _reposition(self):
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        w = self.winfo_reqwidth()
        self.geometry(f"+{sw - w - 20}+30")

    def _open_editor(self):
        self._app.root.deiconify()
        self._app.root.lift()

    def _close(self):
        self._app._overlay = None
        self._app.root.deiconify()
        self.destroy()

    def refresh(self):
        _force_topmost(self.winfo_id())
        for timer_lbl, start_btn, spell in self._spell_entries:
            if spell.timer.is_running:
                timer_lbl.configure(bg="#4b2525", fg="#ff9a82")
                start_btn.configure(state="disabled")
            else:
                timer_lbl.configure(bg="#173c32", fg="#72e0b1")
                start_btn.configure(state="normal")


class SummonerTimerApp:
    REFRESH_MS = 200
    SHORTCUT_KEYS = ("1", "2", "3", "4", "5", "6", "7", "8", "9", "0")

    def __init__(self, root):
        self.root = root
        self.root.title("Summoner Spell Timer")
        self.root.geometry("1380x520")
        self.root.minsize(1220, 460)
        self.root.configure(bg="#101418")
        self.always_on_top = tk.BooleanVar(value=True)
        self.game_clock = GameClock()
        self._overlay = None
        self._configure_styles()
        self._build_ui()
        self._bind_shortcuts()
        self._refresh()

    def _configure_styles(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("App.TFrame", background="#101418")
        style.configure("Row.TFrame", background="#1b2229")
        style.configure("Timer.TFrame", background="#252e36")
        style.configure("TEntry", font=("Segoe UI", 12))
        style.configure("TCombobox", font=("Segoe UI", 12))
        style.configure("TSpinbox", font=("Segoe UI", 12))
        style.configure(
            "Title.TLabel",
            background="#101418",
            foreground="#f4f0e8",
            font=("Segoe UI Semibold", 28),
        )
        style.configure(
            "Subtitle.TLabel",
            background="#101418",
            foreground="#98a7b3",
            font=("Segoe UI", 12),
        )
        style.configure(
            "Ready.Timer.TLabel",
            background="#173c32",
            foreground="#72e0b1",
            font=("Consolas", 15, "bold"),
            padding=(4, 4),
        )
        style.configure(
            "Running.Timer.TLabel",
            background="#4b2525",
            foreground="#ff9a82",
            font=("Consolas", 15, "bold"),
            padding=(4, 4),
        )
        style.configure(
            "ReadyAt.Timer.TLabel",
            background="#252e36",
            foreground="#b8a060",
            font=("Consolas", 12),
            padding=(4, 4),
        )
        style.configure(
            "GameTime.TLabel",
            background="#101418",
            foreground="#c8b060",
            font=("Consolas", 15, "bold"),
        )
        style.configure(
            "TButton",
            background="#33414c",
            foreground="#f4f0e8",
            font=("Segoe UI Semibold", 12),
            padding=(5, 4),
            borderwidth=0,
        )
        style.map("TButton", background=[("active", "#496070")])
        style.configure(
            "TEntry", fieldbackground="#11171c", foreground="#f4f0e8"
        )
        style.configure(
            "TCombobox", fieldbackground="#f4f0e8", foreground="#11171c"
        )
        style.configure(
            "TSpinbox", fieldbackground="#11171c", foreground="#f4f0e8"
        )
        style.configure(
            "TCheckbutton",
            background="#101418",
            foreground="#c8d0d6",
            font=("Segoe UI", 12),
        )
        style.map("TCheckbutton", background=[("active", "#101418")])
        style.configure(
            "Row.TCheckbutton",
            background="#1b2229",
            foreground="#c8d0d6",
            font=("Segoe UI", 11),
        )
        style.map("Row.TCheckbutton", background=[("active", "#1b2229")])

    def _build_ui(self):
        main = ttk.Frame(self.root, style="App.TFrame", padding=14)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)

        header = ttk.Frame(main, style="App.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 9))
        header.columnconfigure(0, weight=1)

        ttk.Label(header, text="Summoner Spell Timer", style="Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            header,
            text="Edit base cooldowns as needed; Cosmic Insight applies 18 summoner spell haste.",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(3, 0))
        ttk.Checkbutton(
            header,
            text="Always on top",
            variable=self.always_on_top,
            command=self._set_topmost,
        ).grid(row=0, column=1, padx=(12, 12))
        self.game_time_text = tk.StringVar(value="--:--")
        ttk.Label(
            header,
            textvariable=self.game_time_text,
            style="GameTime.TLabel",
        ).grid(row=0, column=2, padx=(0, 8))
        self.game_start_button = ttk.Button(
            header, text="Start Game [G]", command=self.start_game
        )
        self.game_start_button.grid(row=0, column=3, padx=(0, 6))
        ttk.Button(
            header, text="Reset Game [Ctrl+G]", command=self.reset_game
        ).grid(row=0, column=4, padx=(0, 12))
        ttk.Button(header, text="Reset all", command=self.reset_all).grid(
            row=0, column=5
        )
        ttk.Button(header, text="Overlay", command=self._toggle_overlay).grid(
            row=0, column=6, padx=(6, 0)
        )

        self.rows = []
        for row_number in range(1, 6):
            shortcut_offset = (row_number - 1) * 2
            shortcuts = tuple(
                key
                for key in self.SHORTCUT_KEYS[shortcut_offset : shortcut_offset + 2]
            )
            row = SummonerRow(main, row_number, shortcuts, self.game_clock)
            row.grid(row=row_number, column=0, sticky="ew", pady=2)
            self.rows.append(row)

        self._set_topmost()

    def _set_topmost(self):
        self.root.attributes("-topmost", self.always_on_top.get())

    def _bind_shortcuts(self):
        spells = [spell for row in self.rows for spell in row.spells]
        for key, spell in zip(self.SHORTCUT_KEYS, spells):
            self.root.bind(
                "<Key-{}>".format(key),
                partial(self._start_spell, spell),
            )
            self.root.bind(
                "<Control-Key-{}>".format(key),
                partial(self._reset_spell, spell),
            )
        self.root.bind("<Key-g>", self._on_start_game_key)
        self.root.bind("<Key-G>", self._on_start_game_key)
        self.root.bind("<Control-Key-g>", lambda _: self.reset_game())
        self.root.bind("<Control-Key-G>", lambda _: self.reset_game())

    def _start_spell(self, spell, event=None):
        editable_widgets = (tk.Entry, ttk.Entry, ttk.Spinbox, ttk.Combobox)
        if event is not None and isinstance(event.widget, editable_widgets):
            return None
        spell.start()
        return "break"

    def _reset_spell(self, spell, _event=None):
        spell.reset()
        return "break"

    def start_game(self):
        self.game_clock.start()
        self.game_start_button.state(["disabled"])

    def reset_game(self):
        self.game_clock.reset()
        self.game_time_text.set("--:--")
        self.game_start_button.state(["!disabled"])

    def _on_start_game_key(self, event=None):
        editable_widgets = (tk.Entry, ttk.Entry, ttk.Spinbox, ttk.Combobox)
        if event is not None and isinstance(event.widget, editable_widgets):
            return None
        self.start_game()
        return "break"

    def reset_all(self):
        for row in self.rows:
            row.reset()

    def _toggle_overlay(self):
        if self._overlay is not None:
            self._overlay._close()
            return
        self._overlay = OverlayWindow(self)
        self.root.withdraw()

    def _refresh(self):
        for row in self.rows:
            row.refresh()
        if self.game_clock.is_running:
            self.game_time_text.set(format_time(self.game_clock.elapsed_seconds))
        if self._overlay is not None:
            self._overlay.refresh()
        self.root.after(self.REFRESH_MS, self._refresh)


def main():
    root = tk.Tk()
    SummonerTimerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()