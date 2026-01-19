#!/bin/bash
INPUT=$1
SKIP=${2:-0}
END=${3:-30.0}
MM=${MM:-false}  # Parametro per formato minuti,secondi

# Funzione per convertire minuti,secondi.decimali in secondi
parse_time() {
    local time=$1
    if [ "$MM" = "true" ]; then
        # Se non c'è virgola, aggiungi "0," all'inizio
        if [[ $time != *,* ]]; then
            time="0,$time"
        fi
        # Formato mm,ss.dd → converte in secondi
        local mins=$(echo $time | cut -d, -f1)
        local secs=$(echo $time | cut -d, -f2)
        echo "scale=4; $mins * 60 + $secs" | bc
    else
        # Formato normale (secondi diretti, anche con decimali)
        echo $time
    fi
}

SKIP=$(parse_time $SKIP)
END=$(parse_time $END)
DUR=$(echo "scale=4; $END - $SKIP" | bc)

SKIP_="${SKIP//./_}"
DUR_="${DUR//./_}"

make INPUT=$INPUT SKIP=$SKIP DURATA=$DUR "$INPUT-$SKIP_-$DUR_.wav"