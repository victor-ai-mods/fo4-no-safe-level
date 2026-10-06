Scriptname NSL:Main extends Quest

; No Safe Level: урон по игроку не должен «проваливаться» с ростом уровня.
;
; Перк NSL_Perk на игроке умножает урон попадания на (1 + AV полосы): полоса — группа атак с близким
; уроном и одним типом (оружие Fallout4.esm по GetIsID, атаки существ по UnarmedDamage, прочее оружие
; по ключевым словам). Этот скрипт раз в POLL_INTERVAL секунд проверяет уровень, DR/ER, «Уровень угрозы»
; и множитель Выживания и, если что-то изменилось, пересчитывает AV всех полос.
;
; Для полосы с типичным уроном P нужный урон до брони Q = max(K(L)·P, c·Пол(L)), броня гасит на
; четверть меньше, «Уровень угрозы» умножает результат на s. Движок сам применяет броню, поэтому
; скрипт решает обратную задачу — во сколько раз умножить урон, чтобы ванильная формула выдала нужное:
;   физический урон: перк действует ДО брони, коэффициент брони считается от уже умноженного урона;
;   энергоурон: коэффициент брони движок считает от базового урона оружия (баг энергоурона), поэтому
;   множитель ложится поверх. Оба случая проверены тестовым плагином (PLAN.md, «Результаты теста»).
; Выживание даёт ×2 до брони (перк HC_DamageMultPerk через HC_IncomingDamageMult) и ×2 после (GMST);
; второе сокращается, первое учитывается как afPre.
; Силовая броня: ванильный перк PowerArmorPerk умножает входящий урон до брони на PADamageMult игрока,
; каждая целая часть ванильной силовой брони снижает его на 0.05 (EnchPA_ReducePADamageMult), полный
; костюм — 0.7. Мод компенсирует ровно эти 0.7: в целой силовой броне урон такой же, как в обычной
; броне с тем же DR, каждая сломанная часть добавляет урона (PA_REFERENCE).
;
; Здоровье врагов. Движок даёт NPC здоровье = раса + запись NPC + fNPCHealthLevelBonus (5) · (уровень − 1)
; (Fallout4.exe 1.10.163, 0x1405BADF0; у игрока своя GMST fPCHealthLevelBonus). Если задан предел
; NSL_HealthLevelCap, враг выше него теряет прибавку за уровни сверх предела: базовое здоровье его
; варианта остаётся, прибавка считается как на уровне предела. Снятое записывается на самого врага
; в NSL_HealthCapApplied, поэтому смена предела или выключение мода возвращают здоровье.

Perk Property NSL_Perk Auto Const Mandatory
ActorValue Property Health Auto Const Mandatory
ActorValue Property DamageResist Auto Const Mandatory
ActorValue Property EnergyResist Auto Const Mandatory
ActorValue Property UnarmedDamage Auto Const Mandatory
ActorValue Property HC_IncomingDamageMult Auto Const Mandatory
ActorValue Property PADamageMult Auto Const Mandatory
GlobalVariable Property HC_Rule_ScaleDamage Auto Const Mandatory
GlobalVariable Property NSL_ThreatLevel Auto Const Mandatory
GlobalVariable Property NSL_Enabled Auto Const Mandatory
GlobalVariable Property NSL_Debug Auto Const Mandatory
GlobalVariable Property NSL_HealthLevelCap Auto Const Mandatory
ActorValue Property NSL_HealthCapApplied Auto Const Mandatory
FormList Property NSL_ActorTypes Auto Const Mandatory

; Таблица полос (генерируется tools/gen_esp.py из data/bands.json).
ActorValue[] Property BandAV Auto Const Mandatory
Int[] Property BandKind Auto Const Mandatory
Float[] Property BandPhys Auto Const Mandatory
Float[] Property BandEnergy Auto Const Mandatory
Float[] Property BandFloorCoef Auto Const Mandatory
Float[] Property BandKWeight Auto Const Mandatory    ; 0 — атака существа: её урон и так растёт с уровнем, K не нужен
String[] Property BandName Auto Const Mandatory
Float[] Property KLevel Auto Const Mandatory
Float[] Property KValue Auto Const Mandatory

Int Property KIND_PHYS = 0 AutoReadOnly
Int Property KIND_ENERGY = 1 AutoReadOnly
Int Property KIND_MIXED = 2 AutoReadOnly            ; EP 36 смешанной полосы: считается по физической части
Int Property KIND_MIXED_ENERGY = 3 AutoReadOnly     ; EP 94 смешанной полосы: поправка энергетической части
Float Property ALPHA = 0.15 AutoReadOnly            ; fPhysicalDamageFactor
Float Property BETA = 0.365 AutoReadOnly            ; fPhysicalArmorDmgReductionExp
Float Property MAX_COEF = 0.99 AutoReadOnly
Float Property ARMOR_EFFECT = 0.75 AutoReadOnly     ; броня гасит на четверть меньше
Float Property FLOOR_DIVISOR = 16.0 AutoReadOnly    ; Пол = HP_эталон / 16: без брони на Выживании 4 попадания
Float Property Q_MAX = 20.0 AutoReadOnly            ; потолок Q/P: ошибка в типичном уроне полосы не станет убийством
Float Property PA_REFERENCE = 0.7 AutoReadOnly      ; PADamageMult целой ванильной силовой брони (6 частей по 0.05)
Float Property HP_REF_BASE = 105.0 AutoReadOnly     ; HP при ВЫН 5: 80 + 5·5 + (L − 1)·(2.5 + 5/2)
Float Property HP_REF_PER_LEVEL = 5.0 AutoReadOnly
Float Property POLL_INTERVAL = 3.0 AutoReadOnly
Float Property SCAN_RADIUS = 10000.0 AutoReadOnly   ; ~ загруженная область снаружи (uGridsToLoad 5)
String Property FAR_HARBOR = "DLCCoast.esm" AutoReadOnly
Int Property FAR_HARBOR_CREATURES = 0x057760 AutoReadOnly   ; DLC03AchievementCreaturesKeyword: у рас краба-
                                                            ; отшельника и туманного ползуна нет ActorType*
String Property LOG_PATH = ".\\Data\\NoSafeLevel\\" AutoReadOnly
String Property LOG_FILE = "NoSafeLevel.log" AutoReadOnly
Int Property MAX_LOG_LINES = 120 AutoReadOnly

Actor Player
Bool Calculated
Int LastLevel
Float LastDR
Float LastER
Float LastThreat
Float LastEnabled
Float LastPre
Float LastPA
Bool LastInPA
Bool DebugOn
Float LastHealth
String[] LogLines
Float HealthLevelBonus
Bool Scanning
Actor[] Skipped
String LastScanInfo

Event OnQuestInit()
    Setup()
EndEvent

Event Actor.OnPlayerLoadGame(Actor akSender)
    Setup()
EndEvent

Function Setup()
    Player = Game.GetPlayer()
    RegisterForRemoteEvent(Player, "OnPlayerLoadGame")
    If !Player.HasPerk(NSL_Perk)
        Player.AddPerk(NSL_Perk)
    EndIf
    HealthLevelBonus = Game.GetGameSettingFloat("fNPCHealthLevelBonus")
    If Game.IsPluginInstalled(FAR_HARBOR)
        Keyword creatures = Game.GetFormFromFile(FAR_HARBOR_CREATURES, FAR_HARBOR) as Keyword
        If creatures && !NSL_ActorTypes.HasForm(creatures)
            NSL_ActorTypes.AddForm(creatures)
        EndIf
    EndIf
    Scanning = false
    Calculated = false
    DebugOn = false
    Check()
    StartTimer(POLL_INTERVAL)
EndFunction

Event OnTimer(int aiTimerID)
    Check()
    CapEnemyHealth()
    StartTimer(POLL_INTERVAL)
EndEvent

Function Check()
    Int level = Player.GetLevel()
    Float dr = Player.GetValue(DamageResist)
    Float er = Player.GetValue(EnergyResist)
    Float threat = NSL_ThreatLevel.GetValue()
    Float enabled = NSL_Enabled.GetValue()
    Float pre = SurvivalPreMult()
    Float pa = Player.GetValue(PADamageMult)
    Bool inPA = Player.IsInPowerArmor()
    If !Calculated || level != LastLevel || Math.abs(dr - LastDR) > 0.5 || Math.abs(er - LastER) > 0.5 \
            || threat != LastThreat || enabled != LastEnabled || pre != LastPre || pa != LastPA || inPA != LastInPA
        Recalc(level, dr, er, threat, enabled, pre, pa, inPA)
        Calculated = true
        LastLevel = level
        LastDR = dr
        LastER = er
        LastThreat = threat
        LastEnabled = enabled
        LastPre = pre
        LastPA = pa
        LastInPA = inPA
        If DebugOn
            LogState()
        EndIf
    EndIf
    UpdateDebug()
EndFunction

; Множитель Выживания до брони: ванильный перк HC_DamageMultPerk умножает урон на HC_IncomingDamageMult,
; когда HC_Rule_ScaleDamage = 1.
Float Function SurvivalPreMult()
    If HC_Rule_ScaleDamage.GetValue() >= 0.5
        Return Player.GetValue(HC_IncomingDamageMult)
    EndIf
    Return 1.0
EndFunction

; afPA — PADamageMult (движок умножает на него урон до брони), abInPA — игрок в силовой броне.
Function Recalc(Int aiLevel, Float afDR, Float afER, Float afThreat, Float afEnabled, Float afPre, Float afPA, \
        Bool abInPA)
    Int n = BandAV.Length
    Int i = 0
    If afEnabled < 0.5
        While i < n
            Player.SetValue(BandAV[i], 0.0)
            i += 1
        EndWhile
        Return
    EndIf
    Float k = KFor(aiLevel)
    Float floorDamage = (HP_REF_BASE + HP_REF_PER_LEVEL * (aiLevel - 1)) / FLOOR_DIVISOR
    Float s = Math.pow(2.0, (afThreat - 5.0) / 4.0)
    ; Целая силовая броня — как обычная броня с тем же DR, сломанные части — урон × PADamageMult / 0.7.
    If afPA <= 0.0
        afPA = 1.0
    EndIf
    If abInPA
        s *= afPA / PA_REFERENCE
    EndIf
    Float ph
    Float en
    Float total
    Float q
    Float y
    Float kBand
    Int kind
    While i < n
        ph = BandPhys[i]
        en = BandEnergy[i]
        total = ph + en
        y = 1.0
        If total > 0.0
            kBand = 1.0 + BandKWeight[i] * (k - 1.0)
            q = Math.Min(Math.Max(kBand * total, BandFloorCoef[i] * floorDamage) / total, Q_MAX)
            kind = BandKind[i]
            If kind == KIND_PHYS || kind == KIND_MIXED
                y = SolvePhys(ph, q, s, afPre, afDR, afPA)
            ElseIf kind == KIND_ENERGY
                y = SolveEnergy(en, q, s, afPre, afER, afPA)
            Else
                y = SolveEnergy(en, q, s, afPre, afER, afPA) / SolvePhys(ph, q, s, afPre, afDR, afPA)
            EndIf
        EndIf
        Player.SetValue(BandAV[i], y - 1.0)
        i += 1
    EndWhile
EndFunction

; K(L): кусочно-линейно по таблице, за её пределами — по крайним отрезкам.
Float Function KFor(Int aiLevel)
    Float level = aiLevel as Float
    Int last = KLevel.Length - 1
    If level <= KLevel[0]
        Return KValue[0]
    EndIf
    Int i = 1
    While i < last && level > KLevel[i]
        i += 1
    EndWhile
    Float t = (level - KLevel[i - 1]) / (KLevel[i] - KLevel[i - 1])
    Return KValue[i - 1] + t * (KValue[i] - KValue[i - 1])
EndFunction

; Доля урона, проходящая через броню (ванильная формула; при сопротивлении 0 — вся).
Float Function Coef(Float afDamage, Float afResist)
    If afResist <= 0.0
        Return 1.0
    EndIf
    Float m = Math.pow(ALPHA * afDamage / afResist, BETA)
    If m > MAX_COEF
        Return MAX_COEF
    EndIf
    Return m
EndFunction

Float Function SoftCoef(Float afDamage, Float afResist)
    Return 1.0 - ARMOR_EFFECT * (1.0 - Coef(afDamage, afResist))
EndFunction

; x · Coef(x) = afTarget -> x.
Float Function InvertArmor(Float afTarget, Float afResist)
    If afResist <= 0.0
        Return afTarget
    EndIf
    Float x = Math.pow(afTarget * Math.pow(afResist / ALPHA, BETA), 1.0 / (1.0 + BETA))
    If Coef(x, afResist) >= MAX_COEF
        x = afTarget / MAX_COEF
    EndIf
    Return x
EndFunction

; Физический урон: множитель действует до брони. afPA — множитель силовой брони, движок применяет его
; до брони вместе с нашим, цель он не меняет.
Float Function SolvePhys(Float afDamage, Float afScale, Float afThreat, Float afPre, Float afResist, Float afPA)
    Float paper = afScale * afDamage * afPre
    Float target = afThreat * paper * SoftCoef(paper, afResist)
    Return InvertArmor(target, afResist) / (afDamage * afPre * afPA)
EndFunction

; Энергоурон: коэффициент брони движок берёт от базового урона, множители ложатся поверх.
Float Function SolveEnergy(Float afDamage, Float afScale, Float afThreat, Float afPre, Float afResist, Float afPA)
    Float paper = afScale * afDamage * afPre
    Float target = afThreat * paper * SoftCoef(paper, afResist)
    Return target / (afDamage * afPre * afPA * Coef(afDamage, afResist))
EndFunction

; --- здоровье врагов --------------------------------------------------------------------------

Function CapEnemyHealth()
    If Scanning
        Return
    EndIf
    Scanning = true
    Int cap = NSL_HealthLevelCap.GetValueInt()
    If NSL_Enabled.GetValue() < 0.5
        cap = 0
    EndIf
    ; По одному ключевому слову: FindAllReferencesWithKeyword со списком FormList находит 0 (проверено в игре),
    ; хотя в документации список разрешён. Актёр с двумя ключевыми словами попадёт дважды — второй раз
    ; CapActor ничего не сделает.
    Int total = 0
    Int k = 0
    Int types = NSL_ActorTypes.GetSize()
    While k < types
        ObjectReference[] found = Player.FindAllReferencesWithKeyword(NSL_ActorTypes.GetAt(k), SCAN_RADIUS)
        total += found.Length
        Int i = 0
        While i < found.Length
            Actor npc = found[i] as Actor
            If npc && npc != Player
                CapActor(npc, cap)
            EndIf
            i += 1
        EndWhile
        k += 1
    EndWhile
    If DebugOn
        LogScan(cap, total, types)
    EndIf
    Scanning = false
EndFunction

; Прибавка здоровья за уровень так, как её считает движок: (int)((L − 1) · fNPCHealthLevelBonus).
Float Function LevelBonus(Int aiLevel)
    Return Math.Floor((aiLevel - 1) * HealthLevelBonus) as Float
EndFunction

Function CapActor(Actor akActor, Int aiCap)
    Int level = akActor.GetLevel()
    Float wanted = 0.0
    If aiCap > 0 && level > aiCap
        wanted = LevelBonus(level) - LevelBonus(aiCap)
    EndIf
    Float applied = akActor.GetValue(NSL_HealthCapApplied)
    If wanted == applied || akActor.IsDead()
        Return
    EndIf
    ; Отключённые и ещё не загруженные (засады, ожидающие спавна) — здоровье у них ещё не рассчитано
    ; (в игре: база 50 при текущем 385), ModValue не держится. Их обработает обход после появления.
    If akActor.IsDisabled() || !akActor.Is3DLoaded()
        Return
    EndIf
    ; Новых — только врагов; у уже обработанных здоровье пересчитывается всегда (смена предела, выключение).
    If applied == 0.0 && (akActor.IsPlayerTeammate() || !akActor.IsHostileToActor(Player))
        If DebugOn && Skipped.Find(akActor) < 0 && Skipped.Length < 100
            Skipped.Add(akActor)
            Log("hpcap skip " + akActor + " " + akActor.GetActorBase() + " lvl=" + level + " hostile=" \
                + akActor.IsHostileToActor(Player) + " teammate=" + akActor.IsPlayerTeammate())
            Flush()
        EndIf
        Return
    EndIf
    Float change = wanted - applied                  ; > 0 — снять здоровье, < 0 — вернуть
    Float before = akActor.GetValue(Health)
    If change > 0.0 && change > before - 1.0
        change = before - 1.0                        ; тяжело раненого не убивать, остаток — в следующий раз
        If change <= 0.0
            Return
        EndIf
    EndIf
    akActor.ModValue(Health, -change)
    akActor.SetValue(NSL_HealthCapApplied, applied + change)
    If DebugOn
        Log("hpcap " + akActor.GetActorBase() + " lvl=" + level + " cap=" + aiCap + " base=" \
            + akActor.GetBaseValue(Health) + " hp " + before + " -> " + akActor.GetValue(Health) + " (" \
            + akActor.GetValuePercentage(Health) + ") removed=" + (applied + change))
        Flush()
    EndIf
EndFunction

; --- отладка: set NSL_Debug to 1 ------------------------------------------------------------

; Настройки обхода — когда они меняются (число найденных — на тот момент, оно само по себе не повод писать).
Function LogScan(Int aiCap, Int aiFound, Int aiTypes)
    String info = "hpcap scan cap=" + aiCap + " bonus=" + HealthLevelBonus + " types=" + aiTypes
    If info != LastScanInfo
        LastScanInfo = info
        Log(info + " found=" + aiFound)
        Flush()
    EndIf
EndFunction

Function UpdateDebug()
    Bool wanted = NSL_Debug.GetValue() >= 0.5
    If wanted && !DebugOn
        DebugOn = true
        LogLines = new String[0]
        Skipped = new Actor[0]
        LastScanInfo = ""
        LastHealth = Player.GetValue(Health)
        Log("debug on")
        LogState()
        RegisterForHitEvent(Player)
    ElseIf !wanted && DebugOn
        DebugOn = false
        UnregisterForHitEvent(Player)
        Log("debug off")
        Flush()
    EndIf
EndFunction

Function LogState()
    Log("state level=" + LastLevel + " DR=" + LastDR + " ER=" + LastER + " threat=" + LastThreat \
        + " enabled=" + LastEnabled + " pre=" + LastPre + " PA=" + LastInPA + " PADamageMult=" + LastPA \
        + " K=" + KFor(LastLevel))
    Int i = 0
    String line = "bands"
    While i < BandAV.Length
        line += " " + i + ":" + (1.0 + Player.GetValue(BandAV[i]))
        If i % 12 == 11
            Log(line)
            line = "bands"
        EndIf
        i += 1
    EndWhile
    Log(line)
    Flush()
EndFunction

Event OnHit(ObjectReference akTarget, ObjectReference akAggressor, Form akSource, Projectile akProjectile, \
        bool abPowerAttack, bool abSneakAttack, bool abBashAttack, bool abHitBlocked, string asMaterialName)
    If !DebugOn
        Return
    EndIf
    Float current = Player.GetValue(Health)
    Actor attacker = akAggressor as Actor
    String who = "none"
    If attacker
        who = attacker.GetActorBase() + " lvl=" + attacker.GetLevel() + " unarmed=" + attacker.GetValue(UnarmedDamage)
    EndIf
    Log("hit " + who + " src=" + akSource + " proj=" + akProjectile + " dmg=" + (LastHealth - current) \
        + " DR=" + Player.GetValue(DamageResist) + " ER=" + Player.GetValue(EnergyResist) \
        + " power=" + abPowerAttack + " bash=" + abBashAttack)
    LastHealth = current
    Flush()
    RegisterForHitEvent(Player)
EndEvent

Function Log(String asLine)
    LogLines.Add(asLine)
    If LogLines.Length > MAX_LOG_LINES
        LogLines.Remove(0)
    EndIf
EndFunction

Function Flush()
    GardenOfEden3.WriteLinesToFile(LOG_FILE, LOG_PATH, LogLines, true)
EndFunction
