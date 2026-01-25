<CsoundSynthesizer>
<CsOptions>
; Select audio/midi flags here according to platform
;-odac     ;;;realtime audio out
;-iadc    ;;;uncomment -iadc if RT audio input is needed too
; For Non-realtime ouput leave only the line below:
 -o sinus.wav -W ;;; for file output any platform
</CsOptions>
<CsInstruments>

sr = 48000
ksmps = 32
nchnls = 2
0dbfs  = 1

instr 1
aSig  poscil .8, 440
      outs aSig, aSig
endin

</CsInstruments>
<CsScore>
i1 0 5
</CsScore>
</CsoundSynthesizer>