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
