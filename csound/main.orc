sr=48000
kr=48000
nchnls=2
0dbfs=1

giTest init 2
giInstanceNo init 0
;=============================================================================
; STRUMENTO GRAIN
;=============================================================================
instr Grain
    ;-------------------------------------------------------------------------
    ; PARAMETRI INPUT (da Python via score)
    ;-------------------------------------------------------------------------
    ; p4 = iStart     : punto di start nel sample (secondi)
    ; p5 = iSpeed     : velocità di playback (1=normale, 2=doppio, 0.5=metà)
    ; p6 = iVolume    : volume in dB (0=originale, -6=metà, -inf=silenzio)
    ; p7 = iPan       : posizione stereo (0=left, 0.5=center, 1=right)
    ; p10 = iGrainReverse : 1=backward, 0=forward  ← AGGIUNTO
    iStart  = p4
    iSpeed  = p5
    iVolume = p6
    idegree    = p7
    iSampleTable = p8
    iEnvTable    = p9
    irad = (idegree * $M_PI)/180.0
    if giTest >= 1 then
        iId = giInstanceNo
        giInstanceNo +=1
    endif
    ;-------------------------------------------------------------------------
    ; CALCOLI INIT-TIME
    ;-------------------------------------------------------------------------
    ; Ottieni la lunghezza del sample dalla tabella
    iSampleLen = ftlen(iSampleTable) / ftsr(iSampleTable)    ; ← MODIFICATO
    ; Normalizza start position (0-1)
    iStartNorm = iStart / iSampleLen
    if giTest == 2 then    
        prints "grainId %d, iStartNorm: %f\n", iId, iStartNorm
    endif
    ; Calcola frequenza per poscil3
    ; freq = speed / sample_length
    iFreq = iSpeed / iSampleLen
    ; Converti volume da dB a ampiezza lineare
    ; ═══════════════════════════════════════════════════════════════════
    ; GRAIN REVERSE: se flag=1, inverte direzione lettura campioni
    ; ═══════════════════════════════════════════════════════════════════
    if giTest == 2 then    
        prints "grainId %d, iStartNorm: %f\n", iId, iStartNorm
    endif
    iAmp = ampdb(iVolume)
    ;-------------------------------------------------------------------------
    ; AUDIO PROCESSING
    ;-------------------------------------------------------------------------
    ; Genera envelope del grano
    aEnv = poscil:a(iAmp, 1/p3, iEnvTable)
    ; Leggi il sample con la velocità specificata
    aSound = poscil:a(aEnv, iFreq, iSampleTable, iStartNorm)
    ; Calcola panning (constant power)
    aMid = aSound*cos(irad)
    aSide = aSound*sin(irad)
    aLeft = (aMid + aSide) / sqrt(2)
    aRight = (aMid - aSide) / sqrt(2)
    if giTest == 1 then
        prints "grainId %d - fase iniziale puntatore %f - tempo %f\n", iId, iStartNorm, times()
        aTestStartPointer = a(iStartNorm)
        aTestPointerPhasor = phasor:a(iFreq,iStartNorm)
        ktrig metro 1000 ; metro accetta freq, non msec
        if ktrig == 1 then
        println "\tgrainId %d - fasore %f - tempo %f - k-rate %d", iId,k(aTestPointerPhasor), timek()/kr, timek()
        endif
        outc aLeft, aEnv, aTestStartPointer, aTestPointerPhasor;aRight
    else
        outc aLeft,aRight
    endif
endin


instr testWindowGrain
    iStart  = p4
    iSpeed  = p5
    iVolume = p6
    idegree    = p7
    iSampleTable = p8
    iEnvTable    = p9
    iGrainReverse = p10
    iAmp = ampdb(iVolume)
    irad = (idegree * $M_PI)/180.0
    aEnv = poscil:a(iAmp, 1/p3, iEnvTable)
    outs aEnv, aEnv
endin

;=============================================================================
; STRUMENTO TAPE RECORDER
;=============================================================================
instr TapeRecorder
    ;-------------------------------------------------------------------------
    ; PARAMETRI INPUT
    ;-------------------------------------------------------------------------
    ; p4 = iStartPos     : posizione iniziale nel file (secondi)
    ; p5 = iSpeed        : velocità di lettura con resampling
    ;                      1.0 = normale
    ;                      2.0 = doppia velocità (+1 ottava)
    ;                      0.5 = metà velocità (-1 ottava)
    ; p6 = iVolume       : volume in dB
    ; p7 = iPan          : posizione stereo (0-1)
    ; p8 = iLoop         : 0=no loop, 1=loop
    ; p9 = iLoopStart    : inizio loop in secondi (-1 = usa inizio sample)
    ; p10 = iLoopEnd     : fine loop in secondi (-1 = usa fine sample)
    ; p11 = iSampleTable : numero ftable del sample
    iStartPos = p4
    iSpeed = p5
    iVolume = p6
    iPan = p7
    iLoop = p8
    iLoopStart = p9
    iLoopEnd = p10
    iSampleTable = p11
    ;-------------------------------------------------------------------------
    ; SETUP
    ;-------------------------------------------------------------------------
    iSampleLen = ftlen(iSampleTable) / sr
    iAmp = ampdb(iVolume)
    ; Setup loop boundaries
    if iLoopStart < 0 then
        iLoopStart = 0
    endif
    if iLoopEnd < 0 then
        iLoopEnd = iSampleLen
    endif
    ;-------------------------------------------------------------------------
    ; LETTURA AUDIO 
    ;-------------------------------------------------------------------------    
    ; Per playback continuo: freq = speed / sample_length
    iFreq = iSpeed / iSampleLen
    ; Fase iniziale normalizzata
    iPhaseStart = iStartPos / iSampleLen
    if iLoop == 1 then
        ; MODE: LOOP
        ; Calcola durata del loop
        iLoopDur = iLoopEnd - iLoopStart
        iLoopFreq = iSpeed / iLoopDur
        
        ; Fase iniziale nel loop
        iLoopPhaseStart = iLoopStart / iSampleLen
        
        ; Leggi con loop (usando poscil3)
        aSound poscil3 iAmp, iLoopFreq, iSampleTable, iLoopPhaseStart
    else
        ; MODE: ONE-SHOT
        ; Leggi senza loop
        aSound poscil3 iAmp, iFreq, iSampleTable, iPhaseStart
    endif
    ;-------------------------------------------------------------------------
    ; OUTPUT
    ;-------------------------------------------------------------------------
    ; Fade in/out per evitare click
    aEnv = linseg:a(0, 0.01, 1, p3-0.02, 1, 0.01, 0)
    aSound = aSound * aEnv
    ; Panning (constant power)
    aLeft  = aSound * sqrt(1 - iPan)
    aRight = aSound * sqrt(iPan)
    ; Output stereo
    outs aLeft, aRight
endin

 