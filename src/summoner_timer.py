import time
import tkinter as tk
from functools import partial
from tkinter import messagebox, ttk


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


def adjusted_cooldown(base_seconds, cosmic_insight=False):
    if not cosmic_insight:
        return base_seconds
    return base_seconds / (1 + COSMIC_INSIGHT_SUMMONER_HASTE / 100.0)


def tracking_duration(base_seconds, cosmic_insight=False):
    cooldown = adjusted_cooldown(base_seconds, cosmic_insight)
    return max(0, cooldown - TIMER_OFFSET_SECONDS)


class SpellTimer(ttk.Frame):
    def __init__(self, parent, spell_name="Flash", cosmic_insight=None, shortcut=""):
        ttk.Frame.__init__(self, parent, style="Timer.TFrame", padding=(7, 5))
        self.timer = CountdownTimer()
        self.cosmic_insight = cosmic_insight
        self.shortcut = shortcut
        self.spell_name = tk.StringVar(value=spell_name)
        self.cooldown = tk.StringVar(value=str(SPELL_COOLDOWNS[spell_name]))
        self.time_text = tk.StringVar(value="READY")

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
        self.refresh()

    def reset(self):
        self.timer.reset()
        self.refresh()

    def refresh(self):
        remaining = self.timer.remaining_seconds
        if self.timer.is_running:
            self.time_text.set(format_time(remaining))
            self.time_label.configure(style="Running.Timer.TLabel")
            self.start_button.state(["disabled"])
        else:
            self.time_text.set("READY")
            self.time_label.configure(style="Ready.Timer.TLabel")
            self.start_button.state(["!disabled"])


class SummonerRow(ttk.Frame):
    def __init__(self, parent, row_number, shortcuts):
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
            SpellTimer(self, "Flash", self.cosmic_insight, shortcuts[0]),
            SpellTimer(self, "Ignite", self.cosmic_insight, shortcuts[1]),
        )
        self.spells[0].grid(row=0, column=1, padx=(0, 5), sticky="ew")
        self.spells[1].grid(row=0, column=2, sticky="ew")

    def reset(self):
        for spell in self.spells:
            spell.reset()

    def refresh(self):
        for spell in self.spells:
            spell.refresh()


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
        ttk.Button(header, text="Reset all", command=self.reset_all).grid(
            row=0, column=2
        )

        self.rows = []
        for row_number in range(1, 6):
            shortcut_offset = (row_number - 1) * 2
            shortcuts = tuple(
                key
                for key in self.SHORTCUT_KEYS[shortcut_offset : shortcut_offset + 2]
            )
            row = SummonerRow(main, row_number, shortcuts)
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

    def _start_spell(self, spell, event=None):
        editable_widgets = (tk.Entry, ttk.Entry, ttk.Spinbox, ttk.Combobox)
        if event is not None and isinstance(event.widget, editable_widgets):
            return None
        spell.start()
        return "break"

    def _reset_spell(self, spell, _event=None):
        spell.reset()
        return "break"

    def reset_all(self):
        for row in self.rows:
            row.reset()

    def _refresh(self):
        for row in self.rows:
            row.refresh()
        self.root.after(self.REFRESH_MS, self._refresh)


def main():
    root = tk.Tk()
    SummonerTimerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()