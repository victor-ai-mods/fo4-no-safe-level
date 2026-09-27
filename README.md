# No Safe Level

A Fallout 4 mod that keeps the Commonwealth dangerous at any level. In vanilla, by the late game you
become a walking tank: enemies barely scratch you. With this mod armor damage resistance is reduced by
25%, and enemy damage gets correction multipliers, so a fight at level 50 feels like Corvega at level 4.
One MCM setting: **Threat level** 1-10 (5 is the intended balance, tuned for Survival).

Download: [Nexus Mods](https://www.nexusmods.com/fallout4/mods/109500).

**Spoiler warning.** The Nexus page keeps the mechanics secret on purpose. This repository explains them
in full: the design notes are in Russian (`ANALYSIS.md`, `PLAN.md`), the details below are in English.

Русское описание, устройство и сборка - [README.ru.md](README.ru.md).

## How it works (spoilers)

- A hidden perk on the player multiplies incoming weapon damage by `1 + AV` per **damage band** (a group of
  attacks with similar damage and type): base-game weapons by `GetIsID`, creature attacks by the
  attacker's `UnarmedDamage` (plus the weapon for creatures whose attack has its own damage), other
  weapons (DLC, mods) by keyword categories. Explosives are left alone.
- A Papyrus script (`papyrus/NSL/Main.psc`) recalculates every band's multiplier when your level, DR/ER,
  Threat level or the Survival multiplier changes. For a band with typical damage `P` the target hit is
  `max(K(level) * P, floor)`, where `K` keeps level-appropriate enemies as deadly as the Corvega raiders
  and the floor makes the weakest enemy kill an unarmored player in about 4 hits on Survival. Armor then
  stops 25% less of the damage. The script solves the inverse problem so the vanilla formula produces
  exactly that hit.
- Creature attacks get no `K` (their damage already grows with the variant level), only the floor and the
  armor change.
- The engine behaviour this relies on was measured in game with a test plugin (`TEST.md`): Survival is x2
  before armor (the vanilla `HC_DamageMultPerk`) and x2 after; the perk entry point multiplies bullets
  before armor and energy damage after it (the energy damage bug); creature damage is weapon damage plus
  `UnarmedDamage`.

## Requirements

- None beyond the base game. The plugin's only master is `Fallout4.esm`; no DLC required.
- Optional: Mod Configuration Menu (needs F4SE) for the Threat level slider; without it the level is 5
  (`set NSL_ThreatLevel to N` in the console).
- Optional: Garden of Eden Papyrus Script Extender, only for the debug log (`set NSL_Debug to 1`).

Tested on game version 1.10.163 (pre-Next-Gen).

## Building

See [README.ru.md](README.ru.md#сборка). Everything is generated from the game files: `tools/scan_weapons.py`
and `tools/bands.py` (damage bands), `tools/gen_esp.py` (the ESP), `tools/gen_mcm.py` (MCM config and
translations), PapyrusCompiler (the script), `tools/deploy.py` (into the game), `tools/gen_cover.py` and
`tools/gen_banner.py` (Nexus images). `tools/sim.py` checks the script's math.

## License

The Unlicense - public domain. Made with Claude Code.
