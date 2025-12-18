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
    
    iStart  = p4
    iSpeed  = p5
    iVolume = p6
    iPan    = p7
    iSampleTable = p8
    iEnvTable    = p9
    
    ;-------------------------------------------------------------------------
    ; CALCOLI INIT-TIME
    ;-------------------------------------------------------------------------

    ; Ottieni la lunghezza del sample dalla tabella
    iSampleLen = ftlen(iSampleTable) / sr    ; ← MODIFICATO

    ; Normalizza start position (0-1)
    iStartNorm = iStart / iSampleLen
    
    ; Calcola frequenza per poscil3
    ; freq = speed / sample_length
    iFreq = iSpeed / iSampleLen
    
    ; Converti volume da dB a ampiezza lineare
    iAmp = ampdb(iVolume)
    
    ;-------------------------------------------------------------------------
    ; AUDIO PROCESSING
    ;-------------------------------------------------------------------------
    
    ; Genera envelope del grano
    aEnv = poscil3:a(iAmp, 1/p3, iEnvTable)
    
    ; Leggi il sample con la velocità specificata
    aSound = poscil3:a(aEnv, iFreq, iSampleTable, iStartNorm)
    
    ; Calcola panning (constant power)
    aLeft  = aSound * sqrt(1 - iPan)
    aRight = aSound * sqrt(iPan)
    
    ; Output stereo
    outs aLeft, aRight
endin