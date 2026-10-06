# No Safe Level

A Fallout 4 mod that keeps the Commonwealth dangerous at any level. In vanilla, by the late game you
become a walking tank: enemies barely scratch you. With this mod armor damage resistance is reduced by
25%, and enemy damage gets correction multipliers, so a fight at level 50 feels like Corvega at level 4.
MCM settings: **Threat level** 1-10 (5 is the intended balance, tuned for Survival) and **Remove +5 enemy
health per level above level** 0-100 (default 50, 0 = off): high-level enemies stop being bullet sponges.

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
  armor change. `Q/P` is capped at 20, so a wrong typical damage can't turn into a one-shot (the bloatfly's
  weapon says 1, a level 75 bloatfly shot hits for ~27: measured in game, used as the band damage).
- **Power armor.** The vanilla `PowerArmorPerk` multiplies incoming damage before armor by the player's
  `PADamageMult`; every intact piece of vanilla power armor lowers it by 0.05 (`EnchPA_ReducePADamageMult`),
  a full suit gives 0.7. The script compensates exactly 0.7: a full suit protects like ordinary armor with
  the same DR, every broken piece adds damage (x `PADamageMult` / 0.7).
- **Enemy health.** The engine gives an NPC health = race health + the NPC record's health +
  `fNPCHealthLevelBonus` (5) x (level - 1) (found in `Fallout4.exe` 1.10.163, function `0x1405BADF0`; confirmed
  in game: a level 68 survivalist raider has 40 + 350 + 5 x 67 = 725). Enemy variants are fixed-level
  records and only the top variant scales with the player, so above that level health grows only by this
  bonus. Every 3 s the script finds hostile actors around the player (`FindAllReferencesWithKeyword`, one
  search per `ActorType*` keyword - a FormList of keywords finds nothing) and lowers the max health of
  those above the cap by the bonus of the levels above it (`ModValue`), storing the amount on the actor in
  `NSL_HealthCapApplied`, so changing the cap or disabling the mod gives it back. Disabled and not yet
  loaded actors (ambushes) are skipped until they appear: their health is not calculated yet.
- The engine behaviour this relies on was measured in game with a test plugin (`TEST.md`): Survival is x2
  before armor (the vanilla `HC_DamageMultPerk`) and x2 after; the perk entry point multiplies bullets
  before armor and energy damage after it (the energy damage bug); creature damage is weapon damage plus
  `UnarmedDamage`.

## Requirements

- None beyond the base game. The plugin's only master is `Fallout4.esm`; no DLC required.
- Optional: Mod Configuration Menu (needs F4SE) for the Threat level slider; without it the level is 5
  (`set NSL_ThreatLevel to N` in the console) and the health cap is 50 (`set NSL_HealthLevelCap to N`).
- Optional: Garden of Eden Papyrus Script Extender, only for the debug log (`set NSL_Debug to 1`).

Tested on game version 1.10.163 (pre-Next-Gen).

## Building

See [README.ru.md](README.ru.md#сборка). Everything is generated from the game files: `tools/scan_weapons.py`
and `tools/bands.py` (damage bands), `tools/gen_esp.py` (the ESP), `tools/gen_mcm.py` (MCM config and
translations), PapyrusCompiler (the script), `tools/deploy.py` (into the game), `tools/gen_cover.py` and
`tools/gen_banner.py` (Nexus images). `tools/sim.py` checks the script's math.

## License

The Unlicense - public domain. Made with Claude Code.
