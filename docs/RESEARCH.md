# Ballistics and data audit - 2026-09-16

## What is and is not verified

The shipped data contains 184 firearm cartridges and 38 individual ballistic plates,
including four 5.8x42 cartridges. Each of these 222 records has an exact item-ID image
and a SHA-256 entry in `resources/items/image-manifest.json`. `catalog.json` retains
source URLs, source-content hashes, exclusions and conflicts.

**The current closed-source game server was not independently measured.** The
penetration, post-penetration loss, wear and blunt calculations are a documented
community model, not a guarantee of exact current-patch game behavior. Passing unit
or Android/Windows consistency tests verifies the implementation and mathematical
contracts, not the truth of an unpublished game algorithm.

Sources, retrieved/reviewed 2026-09-16:

* Primary community Wiki mechanics/material coefficients:
  https://escapefromtarkov.fandom.com/wiki/Ballistics
* Primary Wiki plate inventory and material/class/durability cross-checks:
  https://escapefromtarkov.fandom.com/wiki/Armor_plates
* Chinese Wiki item-ID keyed ammo table and plate inventory:
  https://www.eftarkov.com/news/web_33.html
  https://www.eftarkov.com/news/web_40.html
* NoFoodAfterMidnight's author-maintained chart (pellet counts; cross-check damage,
  penetration and muzzle velocity): https://eft-ammo.vercel.app/
* Published community penetration curve:
  https://www.desmos.com/calculator/m8cmsfokkl
* Pinned community implementation used to audit wear/loss assumptions:
  https://github.com/bugybon/TarkovBallisticsSimulator/blob/82ea32437423c2f1d3ed9ad5d2807eaba15efbc4/api/balistics.js

The pinned JS contains suspicious clamp/parentheses expressions; it was **not**
copied blindly. Corrected expressions below remain community assumptions. Images
are game assets served by `https://assets.tarkov.dev/{item-id}-icon.webp`; original
rights remain with their owners. No unrelated material thumbnail is substituted
for a missing exact image. Historical TarkovTracker data is used only for stable
name/ID aliases during catalog preparation, never as current numerical truth.

## Data provenance and conflicts

The live `https://api.tarkov.dev/graphql` endpoint returned HTTP 422 / "GraphQL
server unavailable. Try again later." during the audit. Its response SHA-256 was
`b2943790ab6723ea651e4ac828bf4625b0b790111247145f6ff9d4563dfe66cf`.
Consequently this release says **Wiki-reviewed snapshot**, not "live API fully
updated". Old fallback data cannot silently overwrite it. Successful online
snapshots merge by exact ID and preserve verified entries absent from the response.

| 5.8x42 cartridge | Damage per projectile | Penetration | Armor damage % | Speed m/s |
|---|---:|---:|---:|---:|
| DBX95 | 57 | 33 | 40 | 910 |
| DBP191 | 53 | 39 | 43 | 840 |
| DVX12 | 48 | 47 | 54 | 850 |
| DVC12 | 46 | 52 | 60 | 872 |

All four have one projectile. The catalog retains the source spelling DVX12.
One Wiki/chart velocity disagreement (item `64b8f7b5389d7ffd620ccba2`, 703 versus
706 m/s) uses the Wiki's 703 and remains recorded. Fifteen flare, grenade and other
unmatched entries are explicitly excluded rather than inventing pellet counts.
A carrier's aggregate displayed durability is **not** an individual front plate's
durability. Plate templates are separate from manually specified soft layers and
helmets. Preset carrier/slot choices are conveniences, not a complete compatibility
validator or an automatic stacking of front and back plates.

## Implemented model

Let `d = current durability / original factory maximum`, `C = armor class`,
`P = incoming penetration`, and `R = (121 - 5000 / (45 + 200*d)) * C/10`.
Repaired maximum only limits the editable current durability; it does not replace
the factory denominator. A repaired 45/45 plate originally rated 60 uses 75%.

For intact armor, the clamped penetration probability is:

* `P >= R`: `(100 + P / (0.9*R - P)) / 100`.
* `R-15 < P < R`: `0.004 * (R-P-15)^2`.
* Otherwise zero. Nonpositive penetration cannot penetrate intact armor.

A zero-durability layer is bypassed with probability one, zero wear and no damage
or penetration loss. Do not extrapolate the intact formula to broken armor.

Wear is `max(1, P * armor_damage_percent/100 * destructibility * factor)`, clamped
to remaining durability. The community factor is `clamp(P/(10*C), 0.5, 0.9)` on
penetration and `clamp(P/(10*C), 0.6, 1.1)` when stopped. Each individual buckshot
pellet can consume the one-point minimum. Only layers actually reached lose wear.

Destructibility: aramid 0.1875; UHMWPE 0.3375; combined 0.375; titanium 0.4125;
aluminum 0.45; armor steel 0.525; ceramic and glass 0.6. The Chinese plate directory's
older derived ceramic effective-durability numbers are deliberately not copied.

On penetration, damage and penetration are multiplied by
`clamp(P/(R+12), 0.6, 1)`, using **pre-impact durability**. This respects the Wiki's
0-40% damage-loss range but its precise function remains unconfirmed. The blunt
model uses incoming damage, item-specific throughput and
`clamp(1 - 0.03*(R-P), 0.2, 1)` (plate multiplier 0.6). Full impulse attenuation
through backing soft armor is **not modeled**. Default throughput is an explicit
editable assumption, not a claim that every real armor item has identical throughput.

## Probabilities, shotgun semantics and timelines

All projectiles hit the same selected armor path. There is no partial-hit slider.
Pellets and subsequent shots resolve sequentially against updated durability.
Do not multiply a first-pellet result by pellet count or use independent-trial
formulas after armor has changed.

Single-shot/single-projectile expectations are exact under this selected model.
Dependent histories use seeded Monte Carlo trajectories (preview up to 4096;
frontends normally request 2048). A 95% Wilson interval quantifies **sampling**,
not game-model uncertainty. Values can differ within that interval when sampling.

`final_penetration_probability` means at least one fully penetrating projectile
in the **first trigger pull**. Expected flesh/blunt damage is also for that trigger;
explicit `expected_burst_*` fields are for the complete sequence. Conditional
penetrating damage equals first-trigger flesh expectation divided by its penetration
probability; for shotguns it is a conditional total, not damage per single pellet.

The first-penetration distribution comprises mutually exclusive first events.
The probability of at least one penetration within the first min(3,N) triggers is
its sum, not an independence approximation. The mean first-penetration shot is
conditional on penetration occurring within the simulated horizon.

Durability curves include shot zero and only enabled layers. Layer tables and the
durability-sweep probability curve describe the **first projectile**, whereas the
per-trigger curve describes the full shell. Units and scopes are labeled separately.

## Limits and independent verification

The chosen path assumes a hit; it does not model spread, ricochet/helmet angle,
fragmentation, armor coverage misses, skills or black-limb redistribution. Head and
thorax death estimates use 35 and 85 HP. Stomach destruction is not treated as death.
Distance decay is off by default in both frontends. The optional linear sensitivity
mode is explicitly experimental; it is not a validated EFT flight simulation.

`tests/test_ballistics_reference.py` contains independently calculated Decimal
anchors, monotonicity and hand-solvable path tests. Examples: class 5 / pen 40 gives
8.851353602665556% at full durability, 55.14399524375743% at half, and
95.66828156169849% at a quarter. These validate the cited equation, not in-game trials.
A four-durability plate struck by eight zero-penetration, 50-damage pellets blocks
four pellets, then admits four: 200 flesh damage, with the stopped pellets' blunt
component recorded separately. Additional tests compare analytic and sampled
expectations, conserve first/burst totals and reject non-finite inputs.

The six shared JSON vectors are regenerated **regression snapshots**, not independent
truth. Android instrumentation executes the same core on all six and compares its
probability/flesh/blunt outputs with desktop expectations. CI additionally exercises
UI resizing, editing, repaired durability, cache preservation and exact image IDs.
