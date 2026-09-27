Scriptname NSL:TestQuest extends Quest

; No Safe Level — тест механики урона (проверки из PLAN.md). Запуск из консоли:
;     startquest NSL_TestQuest
; Дальше всё идёт само, игроку нужно стоять на месте ~5 минут.
;
; Перк NSL_T_Perk на игроке содержит записи точек урона; каждая умножает урон на (1 + AV игрока),
; поэтому при AV = 0 ничего не делает. Фазы теста включают их по одной (AV = 3 -> x4) и меряют
; урон попаданий. DR/ER игрока выставляются через ModValue, запас здоровья — +3000 к максимуму,
; после каждого попадания здоровье восстанавливается. В конце всё возвращается, но надёжнее
; загрузить сохранение, сделанное перед тестом.
;
; Фазы:
;   X* — взрыв фраг-гранаты под ногами (без NPC), DR 1000
;   P* — рейдер с 10-мм пистолетом, DR 1000; Q* — то же при DR 0
;   L* — тот же рейдер с лазерным пистолетом, ER 1000; L4 — ER 0
; Лог: Data\NoSafeLevel\NoSafeLevel_Test.log (Garden of Eden), разбор — tools/analyze_test.py.

Perk Property TestPerk Auto Const Mandatory
ActorValue Property Health Auto Const Mandatory
ActorValue Property DamageResist Auto Const Mandatory
ActorValue Property EnergyResist Auto Const Mandatory
ActorValue Property HC_IncomingDamageMult Auto Const Mandatory
GlobalVariable Property HC_Rule_ScaleDamage Auto Const Mandatory
ActorBase Property RaiderBase Auto Const Mandatory
Weapon Property Pistol10mm Auto Const Mandatory
Weapon Property LaserPistol Auto Const Mandatory
Ammo Property Ammo10mm Auto Const Mandatory
Ammo Property AmmoFusionCell Auto Const Mandatory
Explosion Property FragExplosion Auto Const Mandatory

ActorValue Property Mul36 Auto Const Mandatory
ActorValue Property Mul94Phys Auto Const Mandatory
ActorValue Property Mul94En Auto Const Mandatory
ActorValue Property Mul124 Auto Const Mandatory
ActorValue Property Add36 Auto Const Mandatory
ActorValue Property ListA Auto Const Mandatory
ActorValue Property ListW Auto Const Mandatory
ActorValue Property IdW Auto Const Mandatory
ActorValue Property AttAV Auto Const Mandatory
ActorValue Property KwW Auto Const Mandatory
ActorValue Property Marker Auto Const Mandatory

String Property LOG_PATH = ".\\Data\\NoSafeLevel\\" AutoReadOnly
String Property LOG_FILE = "NoSafeLevel_Test.log" AutoReadOnly
Int Property HITS_PER_PHASE = 8 AutoReadOnly
Float Property PHASE_TIMEOUT = 60.0 AutoReadOnly
Float Property HP_BUFFER = 3000.0 AutoReadOnly
Float Property MULT_AV = 3.0 AutoReadOnly          ; x(1 + 3) = x4
Float Property ADD_AV = 50.0 AutoReadOnly
Float Property SPAWN_DISTANCE = 1000.0 AutoReadOnly
Float Property FULL_HEAL = 100000.0 AutoReadOnly

Actor Player
Actor Npc
String[] LogLines
Bool Running
Bool Measuring
String PhaseName
Int PhaseHits
Int PhaseBash
Int PhaseOther
String PhaseValues
Float LastHealth
Float DrDelta
Float ErDelta

Event OnQuestInit()
    StartTimer(1.0)
EndEvent

Event OnTimer(int aiTimerID)
    RunTest()
EndEvent

Function RunTest()
    Player = Game.GetPlayer()
    LogLines = new String[0]
    Running = true
    Log("No Safe Level test v1")
    Log("difficulty=" + Game.GetDifficulty() + " HC_Rule_ScaleDamage=" + HC_Rule_ScaleDamage.GetValue() \
        + " HC_IncomingDamageMult=" + Player.GetValue(HC_IncomingDamageMult) + " level=" + Player.GetLevel())
    Log("start DR=" + Player.GetValue(DamageResist) + " ER=" + Player.GetValue(EnergyResist) \
        + " HP=" + Player.GetValue(Health))
    Flush()
    Debug.Notification("No Safe Level test: started, stand still (~5 min)")

    Player.ModValue(Health, HP_BUFFER)
    Player.RestoreValue(Health, FULL_HEAL)
    SetMode(None, 0.0)
    Player.AddPerk(TestPerk)
    SetResist(DamageResist, 1000.0)
    SetResist(EnergyResist, 1000.0)

    ; --- взрывы, пока NPC нет ---
    ExplosionPhase("X0 base", None)
    ExplosionPhase("X1 Mul36", Mul36)
    ExplosionPhase("X2 Mul94Phys", Mul94Phys)
    ExplosionPhase("X3 Mul124", Mul124)

    ; --- рейдер с 10-мм пистолетом ---
    Debug.Notification("No Safe Level test: raider incoming (ghost, can't be hurt)")
    If !SpawnNpc()
        Finish("NPC spawn failed")
        Return
    EndIf
    ArmNpc(Pistol10mm, Ammo10mm)
    NpcPhase("P0 base", None, 0.0)
    If PhaseHits == 0
        Log("no hits, moving NPC closer")
        Npc.MoveTo(Player, 0.5 * SPAWN_DISTANCE * Math.Sin(Player.GetAngleZ()), \
            0.5 * SPAWN_DISTANCE * Math.Cos(Player.GetAngleZ()), 0.0, false)
        Npc.StartCombat(Player)
        NpcPhase("P0 base", None, 0.0)
        If PhaseHits == 0
            Finish("NPC does not hit the player")
            Return
        EndIf
    EndIf
    NpcPhase("P1 Mul36", Mul36, MULT_AV)
    NpcPhase("P2 Mul94Phys", Mul94Phys, MULT_AV)
    NpcPhase("P3 Mul94En", Mul94En, MULT_AV)
    NpcPhase("P4 Add36", Add36, ADD_AV)
    NpcPhase("P5 ListA", ListA, MULT_AV)
    NpcPhase("P6 ListW", ListW, MULT_AV)
    NpcPhase("P7 IdW", IdW, MULT_AV)
    NpcPhase("P8 AttAV", AttAV, MULT_AV)
    NpcPhase("P9 KwW", KwW, MULT_AV)
    NpcPhase("P10 base", None, 0.0)
    SetResist(DamageResist, 0.0)
    NpcPhase("Q0 base DR0", None, 0.0)
    NpcPhase("Q1 Mul36 DR0", Mul36, MULT_AV)
    SetResist(DamageResist, 1000.0)

    ; --- тот же рейдер с лазерным пистолетом ---
    ArmNpc(LaserPistol, AmmoFusionCell)
    NpcPhase("L0 base", None, 0.0)
    NpcPhase("L1 Mul94En", Mul94En, MULT_AV)
    NpcPhase("L2 Mul94Phys", Mul94Phys, MULT_AV)
    NpcPhase("L3 Mul36", Mul36, MULT_AV)
    SetResist(EnergyResist, 0.0)
    NpcPhase("L4 base ER0", None, 0.0)

    Finish("done")
EndFunction

; Все управляющие AV в 0, затем включить один режим.
Function SetMode(ActorValue akAV, Float afValue)
    Player.SetValue(Mul36, 0.0)
    Player.SetValue(Mul94Phys, 0.0)
    Player.SetValue(Mul94En, 0.0)
    Player.SetValue(Mul124, 0.0)
    Player.SetValue(Add36, 0.0)
    Player.SetValue(ListA, 0.0)
    Player.SetValue(ListW, 0.0)
    Player.SetValue(IdW, 0.0)
    Player.SetValue(AttAV, 0.0)
    Player.SetValue(KwW, 0.0)
    If akAV
        Player.SetValue(akAV, afValue)
    EndIf
EndFunction

Function SetResist(ActorValue akAV, Float afTarget)
    Float delta = afTarget - Player.GetValue(akAV)
    Player.ModValue(akAV, delta)
    If akAV == DamageResist
        DrDelta += delta
    Else
        ErDelta += delta
    EndIf
    Log("set " + akAV + " -> " + Player.GetValue(akAV))
EndFunction

Function ExplosionPhase(String asName, ActorValue akAV)
    SetMode(akAV, MULT_AV)
    String values = ""
    Int i = 0
    While i < 3
        Player.RestoreValue(Health, FULL_HEAL)
        Utility.Wait(1.0)
        Float before = Player.GetValue(Health)
        Player.PlaceAtMe(FragExplosion)
        Utility.Wait(2.5)
        values += " " + (before - Player.GetValue(Health))
        i += 1
    EndWhile
    Player.RestoreValue(Health, FULL_HEAL)
    Log(asName + ": DR=" + Player.GetValue(DamageResist) + " dmg=" + values)
    Flush()
EndFunction

Bool Function SpawnNpc()
    Float angle = Player.GetAngleZ()
    Npc = Player.PlaceActorAtMe(RaiderBase)
    If !Npc
        Return false
    EndIf
    Npc.MoveTo(Player, SPAWN_DISTANCE * Math.Sin(angle), SPAWN_DISTANCE * Math.Cos(angle), 0.0, false)
    Npc.SetGhost(true)
    Npc.SetValue(Marker, 5.0)
    Log("NPC spawned, marker=" + Npc.GetValue(Marker))
    RegisterForHitEvent(Player)
    Return true
EndFunction

Function ArmNpc(Weapon akWeapon, Ammo akAmmo)
    Measuring = false
    Npc.RemoveAllItems()
    Npc.AddItem(akAmmo, 500, true)
    Npc.AddItem(akWeapon, 1, true)
    Npc.EquipItem(akWeapon, true, true)
    Npc.StartCombat(Player)
    Utility.Wait(2.0)
    Log("NPC armed with " + akWeapon)
EndFunction

Function NpcPhase(String asName, ActorValue akAV, Float afValue)
    Measuring = false
    Utility.Wait(1.5)                   ; пули, выпущенные в прошлом режиме, долетают
    SetMode(akAV, afValue)
    Player.RestoreValue(Health, FULL_HEAL)
    PhaseName = asName
    PhaseHits = 0
    PhaseBash = 0
    PhaseOther = 0
    PhaseValues = ""
    LastHealth = Player.GetValue(Health)
    Measuring = true
    Float waited = 0.0
    While PhaseHits < HITS_PER_PHASE && waited < PHASE_TIMEOUT
        Utility.Wait(0.5)
        waited += 0.5
    EndWhile
    Measuring = false
    Log(asName + ": DR=" + Player.GetValue(DamageResist) + " ER=" + Player.GetValue(EnergyResist) \
        + " hits=" + PhaseHits + " bash=" + PhaseBash + " other=" + PhaseOther + " time=" + waited \
        + " dmg=" + PhaseValues)
    Flush()
EndFunction

Event OnHit(ObjectReference akTarget, ObjectReference akAggressor, Form akSource, Projectile akProjectile, \
        bool abPowerAttack, bool abSneakAttack, bool abBashAttack, bool abHitBlocked, string asMaterialName)
    Float current = Player.GetValue(Health)
    If Measuring
        If abBashAttack
            PhaseBash += 1
        ElseIf akAggressor != Npc || !akProjectile
            PhaseOther += 1
        Else
            PhaseHits += 1
            PhaseValues += " " + (LastHealth - current)
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
        Npc.StopCombat()
        Npc.Disable()
        Npc.Delete()
    EndIf
    SetMode(None, 0.0)
    Player.RemovePerk(TestPerk)
    Player.ModValue(DamageResist, -DrDelta)
    Player.ModValue(EnergyResist, -ErDelta)
    Player.ModValue(Health, -HP_BUFFER)
    Log("end: " + asReason + " DR=" + Player.GetValue(DamageResist) + " ER=" + Player.GetValue(EnergyResist) \
        + " HP=" + Player.GetValue(Health))
    Flush()
    Debug.MessageBox("No Safe Level test finished (" + asReason + "). Load the save made before the test.")
    Stop()
EndFunction

Function Log(String asLine)
    LogLines.Add(asLine)
EndFunction

Function Flush()
    GardenOfEden3.WriteLinesToFile(LOG_FILE, LOG_PATH, LogLines, true)
EndFunction
