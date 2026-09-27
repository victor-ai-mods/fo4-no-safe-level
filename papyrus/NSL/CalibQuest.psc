Scriptname NSL:CalibQuest extends Quest

; No Safe Level — калибровочный прогон с включённым модом. Запуск из консоли:
;     startquest NSL_CalibQuest
; Нужен установленный NoSafeLevel.esp (его глобальные переменные берутся через GetFormFromFile).
;
; По очереди появляются атакующие (неуязвимые), на каждого три фазы по HITS_PER_PHASE попаданий:
;   off0 — мод выключен (NSL_Enabled = 0), сопротивление 0: чистый урон атаки;
;   offR — мод выключен, сопротивление RESIST: проверка ванильной модели;
;   onR  — мод включён, сопротивление RESIST: проверка мода.
; Для лазера меняется ER, для остальных DR. NSL_Debug = 1 на время теста — NSL:Main пишет в свой лог
; множители полос при каждом пересчёте. Запас здоровья +3000, после каждого попадания лечение.
; Лог: Data\NoSafeLevel\NoSafeLevel_Calib.log, разбор — tools/analyze_calib.py.

ActorValue Property Health Auto Const Mandatory
ActorValue Property DamageResist Auto Const Mandatory
ActorValue Property EnergyResist Auto Const Mandatory
ActorValue Property UnarmedDamage Auto Const Mandatory
ActorBase Property RaiderBase Auto Const Mandatory
Weapon Property Pistol10mm Auto Const Mandatory
Weapon Property PipeGun Auto Const Mandatory
Weapon Property LaserPistol Auto Const Mandatory
Ammo Property Ammo10mm Auto Const Mandatory
Ammo Property Ammo38 Auto Const Mandatory
Ammo Property AmmoFusionCell Auto Const Mandatory
ActorBase Property RadRoachBase Auto Const Mandatory
ActorBase Property RadRoachGlowingBase Auto Const Mandatory
ActorBase Property MoleratBase Auto Const Mandatory
ActorBase Property FeralGhoulBase Auto Const Mandatory
ActorBase Property DeathclawBase Auto Const Mandatory

String Property LOG_PATH = ".\\Data\\NoSafeLevel\\" AutoReadOnly
String Property LOG_FILE = "NoSafeLevel_Calib.log" AutoReadOnly
String Property MOD_PLUGIN = "NoSafeLevel.esp" AutoReadOnly
Int Property ID_ENABLED = 0x802 AutoReadOnly
Int Property ID_DEBUG = 0x803 AutoReadOnly
Int Property HITS_PER_PHASE = 5 AutoReadOnly
Float Property PHASE_TIMEOUT = 45.0 AutoReadOnly
Float Property RESIST = 300.0 AutoReadOnly
Float Property HP_BUFFER = 3000.0 AutoReadOnly
Float Property FULL_HEAL = 100000.0 AutoReadOnly
Float Property SETTLE = 4.0 AutoReadOnly            ; NSL:Main опрашивает раз в 3 с

Actor Player
Actor Npc
GlobalVariable NSL_Enabled
GlobalVariable NSL_Debug
String[] LogLines
Bool Running
Bool Measuring
Int PhaseHits
Int PhaseOther
Int PhasePower
String PhaseValues
Float LastHealth
Float DrDelta
Float ErDelta

Event OnQuestInit()
    StartTimer(1.0)
EndEvent

Event OnTimer(int aiTimerID)
    Run()
EndEvent

Function Run()
    Player = Game.GetPlayer()
    LogLines = new String[0]
    NSL_Enabled = Game.GetFormFromFile(ID_ENABLED, MOD_PLUGIN) as GlobalVariable
    NSL_Debug = Game.GetFormFromFile(ID_DEBUG, MOD_PLUGIN) as GlobalVariable
    If !NSL_Enabled || !NSL_Debug
        Debug.MessageBox("No Safe Level calibration: NoSafeLevel.esp is not loaded.")
        Stop()
        Return
    EndIf
    Running = true
    Log("No Safe Level calibration v1")
    Log("difficulty=" + Game.GetDifficulty() + " level=" + Player.GetLevel() + " HP=" + Player.GetValue(Health) \
        + " DR=" + Player.GetValue(DamageResist) + " ER=" + Player.GetValue(EnergyResist))
    Flush()
    Debug.Notification("No Safe Level calibration: started, stand still (~10 min)")
    NSL_Debug.SetValue(1.0)
    Player.ModValue(Health, HP_BUFFER)
    Player.RestoreValue(Health, FULL_HEAL)
    RegisterForHitEvent(Player)

    Attacker("raider_10mm", RaiderBase, Pistol10mm, Ammo10mm, false, 1000.0)
    Attacker("raider_pipe", RaiderBase, PipeGun, Ammo38, false, 1000.0)
    Attacker("raider_laser", RaiderBase, LaserPistol, AmmoFusionCell, true, 1000.0)
    Attacker("radroach", RadRoachBase, None, None, false, 500.0)
    Attacker("radroach_glowing", RadRoachGlowingBase, None, None, false, 500.0)
    Attacker("molerat", MoleratBase, None, None, false, 500.0)
    Attacker("feral_ghoul", FeralGhoulBase, None, None, false, 700.0)
    Attacker("deathclaw", DeathclawBase, None, None, false, 900.0)

    Finish("done")
EndFunction

Function Attacker(String asName, ActorBase akBase, Weapon akWeapon, Ammo akAmmo, Bool abEnergy, Float afDistance)
    Measuring = false
    Float angle = Player.GetAngleZ()
    Npc = Player.PlaceActorAtMe(akBase)
    If !Npc
        Log(asName + ": spawn failed")
        Return
    EndIf
    Npc.MoveTo(Player, afDistance * Math.sin(angle), afDistance * Math.cos(angle), 0.0, false)
    Npc.SetGhost(true)
    If akWeapon
        Npc.RemoveAllItems()
        Npc.AddItem(akAmmo, 500, true)
        Npc.AddItem(akWeapon, 1, true)
        Npc.EquipItem(akWeapon, true, true)
    EndIf
    Npc.StartCombat(Player)
    Log(asName + ": " + Npc.GetActorBase() + " lvl=" + Npc.GetLevel() + " unarmed=" + Npc.GetValue(UnarmedDamage) \
        + " weapon=" + akWeapon)
    Utility.Wait(2.0)

    ActorValue resistAV = DamageResist
    If abEnergy
        resistAV = EnergyResist
    EndIf
    Phase(asName + " off0", 0.0, resistAV, 0.0)
    Phase(asName + " offR", 0.0, resistAV, RESIST)
    Phase(asName + " onR", 1.0, resistAV, RESIST)

    Measuring = false
    Npc.StopCombat()
    Npc.Disable()
    Npc.Delete()
    Npc = None
    Utility.Wait(1.0)
EndFunction

Function Phase(String asName, Float afEnabled, ActorValue akResist, Float afResist)
    Measuring = false
    NSL_Enabled.SetValue(afEnabled)
    SetResist(akResist, afResist)
    Utility.Wait(SETTLE)
    Player.RestoreValue(Health, FULL_HEAL)
    PhaseHits = 0
    PhaseOther = 0
    PhasePower = 0
    PhaseValues = ""
    LastHealth = Player.GetValue(Health)
    Measuring = true
    Float waited = 0.0
    While PhaseHits < HITS_PER_PHASE && waited < PHASE_TIMEOUT
        Utility.Wait(0.5)
        waited += 0.5
    EndWhile
    Measuring = false
    Log(asName + ": enabled=" + afEnabled + " DR=" + Player.GetValue(DamageResist) + " ER=" \
        + Player.GetValue(EnergyResist) + " hits=" + PhaseHits + " other=" + PhaseOther + " power=" + PhasePower \
        + " time=" + waited + " dmg=" + PhaseValues)
    Flush()
EndFunction

Function SetResist(ActorValue akAV, Float afTarget)
    Float delta = afTarget - Player.GetValue(akAV)
    Player.ModValue(akAV, delta)
    If akAV == DamageResist
        DrDelta += delta
    Else
        ErDelta += delta
    EndIf
EndFunction

Event OnHit(ObjectReference akTarget, ObjectReference akAggressor, Form akSource, Projectile akProjectile, \
        bool abPowerAttack, bool abSneakAttack, bool abBashAttack, bool abHitBlocked, string asMaterialName)
    Float current = Player.GetValue(Health)
    If Measuring
        If akAggressor != Npc || abBashAttack
            PhaseOther += 1
        Else
            PhaseHits += 1
            If abPowerAttack
                PhasePower += 1
                PhaseValues += " P" + (LastHealth - current)
            Else
                PhaseValues += " " + (LastHealth - current)
            EndIf
        EndIf
    EndIf
    Player.RestoreValue(Health, FULL_HEAL)
    LastHealth = Player.GetValue(Health)
    If Running
        RegisterForHitEvent(Player)
    EndIf
EndEvent

Function Finish(String asReason)
    Running = false
    Measuring = false
    If Npc
        Npc.Disable()
        Npc.Delete()
    EndIf
    NSL_Enabled.SetValue(1.0)
    NSL_Debug.SetValue(0.0)
    Player.ModValue(DamageResist, -DrDelta)
    Player.ModValue(EnergyResist, -ErDelta)
    Player.ModValue(Health, -HP_BUFFER)
    Log("end: " + asReason + " DR=" + Player.GetValue(DamageResist) + " ER=" + Player.GetValue(EnergyResist))
    Flush()
    Debug.MessageBox("No Safe Level calibration finished (" + asReason + "). Load the save made before the test.")
    Stop()
EndFunction

Function Log(String asLine)
    LogLines.Add(asLine)
EndFunction

Function Flush()
    GardenOfEden3.WriteLinesToFile(LOG_FILE, LOG_PATH, LogLines, true)
EndFunction
