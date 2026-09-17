# Validation audit - 2026-09-18

This audit was performed for the 2.2.2 chart/data correction.  It separates
**public item data**, **documented game rules**, and **community-model assumptions**
so passing tests are not misrepresented as access to proprietary server code.

## Chart defect reproduced

The screenshot showed probability axes extending below 0% and above 100%, and x
ranges much wider than the selected shot horizon.  The values produced by the core
ruleset were already clamped to probability fractions in `[0, 1]`; the visible
`-50%` / `250%` labels were stale pyqtgraph view ranges, not negative or 250%
penetration results.

2.2.2 resets every chart viewport after each result and installs hard view limits:

- per-trigger penetration: y = 0..100%; x = actual trigger horizon only;
- durability timeline: x = shot 0 through the selected final shot; y starts at 0;
- durability sweep: y = 0..100%; x = 0 through the selected layer's editable maximum.

The displayed penetration line is also defensively clipped to 0..100% so a future
upstream regression cannot draw an impossible percentage.  A UI regression test
first forces ranges such as `-200..250%` and `-100..100 shots`, then verifies that
rendering restores the physical ranges.

## Current public ammo cross-check

Retrieved 2026-09-18.  The three checked fields are damage per projectile,
penetration power and armor-damage percent.

Sources:

- Tarkov101 current ammo table: https://tarkov101.com/ammo
- GameMaps current EFT ammo table: https://www.gamemaps.net/game/tarkov/tools/ammo-chart
- TarkovBox per-caliber tables used as an additional spot check:
  https://www.tarkovbox.com/gamewiki/ammo/762x39
  https://www.tarkovbox.com/en/gamewiki/ammo/9x19

| Round | Damage | Pen | Armor dmg % |
|---|---:|---:|---:|
| 5.56x45 M855 | 54 | 31 | 37 |
| 5.56x45 M855A1 | 49 | 44 | 47 |
| 5.56x45 M995 | 42 | 53 | 52 |
| 5.56x45 M856A1 | 52 | 38 | 44 |
| 5.45x39 BP | 48 | 45 | 46 |
| 5.45x39 BS | 45 | 54 | 57 |
| 5.45x39 7N40 | 55 | 42 | 45 |
| 5.45x39 BT | 54 | 37 | 44 |
| 5.45x39 PP | 51 | 34 | 42 |
| 5.45x39 PS | 56 | 28 | 40 |
| 7.62x39 BP | 58 | 47 | 63 |
| 7.62x39 PS | 61 | 35 | 52 |
| 7.62x51 M80 | 80 | 43 | 67 |
| 7.62x54R SNB | 75 | 62 | 87 |
| 9x19 Pst | 54 | 20 | 33 |
| 4.6x30 AP SX | 35 | 53 | 46 |
| 5.7x28 SS190 | 49 | 37 | 43 |

These 17 rows are executable regression anchors in
`tests/test_current_ammo_reference.py`.  The shipped catalog must match all of them
or CI fails.  This is intentionally broader than a single favorite caliber and
covers low, medium and high penetration values.

## Penetration rule boundary

The 0.14.6 armor-penetration rework states that a round with penetration power 15
above armor effective durability produces guaranteed penetration, while intact
armor effective durability is approximately class x 10 and damaged armor has lower
effective durability.  References:

- EFT Wiki changelog, 0.14.6.0.29862:
  https://escapefromtarkov.fandom.com/wiki/Changelog
- Patch-note mirror preserving the BSG text:
  https://tarkov.help/po/article/update-01460

The community curve remains useful inside the transition band, but previously it
could asymptotically return roughly 97-99% even after crossing the documented
`effective durability + 15` boundary.  Ruleset v3 now returns exactly 100% at and
above that boundary.  Tests cover full and damaged armor across classes 2, 4, 5 and
6, plus the existing monotonicity/bounds matrix.

## What this still does not prove

No public source exposes the exact current closed-source server function for every
armor interaction.  Starting penetration variation, velocity loss, intermediate
collisions, post-penetration damage/penetration loss, blunt trauma, ricochet and
fragmentation are not fully reconstructed here.  The application therefore keeps
its `APPROXIMATION` confidence label.  Passing the tests means the implementation
matches the documented/public anchors above; it does not convert unknown mechanics
into claimed facts.
