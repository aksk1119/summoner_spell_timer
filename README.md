# Summoner Spell Timer

A lightweight desktop tracker for League of Legends summoner spell cooldowns.
It uses only Python's standard library and keeps countdowns accurate with a
monotonic clock.

## Run

```powershell
py -3 summoner_timer.py
```

Enter each opponent's name, choose both spells, adjust a cooldown when needed,
select **Cosmic Insight** for enemies using the rune, and press **Start** when a
spell is used. Cosmic Insight applies 18 summoner spell haste to both spells in
that row. The cooldown field remains editable because base values can vary by
patch and game mode.

Start timers with **1** through **0**, ordered from the first enemy's left spell
to the fifth enemy's right spell. The shortcut is shown on each Start button
and works while the timer window is active. Number keys remain available while
editing a name or cooldown field.

## Test

```powershell
py -3 -m unittest -v
```