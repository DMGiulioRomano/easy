#!/bin/bash

NORMALIZE=0

if [[ "$1" == "-n" || "$1" == "--normalize" ]]; then
    NORMALIZE=1
    shift
fi

FILE=${1:-001}
SPEED_RATIO=${2:-1}
NUM_POINTS=${3:-10}
EXP_FACTOR=${4:-2.5}

declare -a x_points
declare -a y_points
globalScale=3
fileDur=$(soxi -D "refs/$FILE.wav")
realDur=$(bc -l <<< "scale=$globalScale; $fileDur / $SPEED_RATIO")
streamDur=$(bc -l <<< "scale=$globalScale; $NUM_POINTS * $realDur")
#echo "filedur: $fileDur durWithSpeed: $realDur numberOfBreakpoints: $NUM_POINTS"
#echo "streamDur: $streamDur"

generare_x() {
    local num_points=${1:-10}
    local real_dur=${2:-5}
    x_points=()   # Reset array globale
    for ((i=0; i<num_points; i++)); do
        x_points[i]=$(bc -l <<< "scale=$globalScale; $i * $real_dur")
    done
}

normalize_x() {
    local max="${1:?streamDur mancante}"
    local scale="${2:?globalScale mancante}"

    for i in "${!x_points[@]}"; do
        x_points[i]=$(bc -l <<< "scale=$scale; ${x_points[i]} / $max")
    done
}

generate_exp() {
    local min="${1:-0}" max="${2:-100}" N="${3:-10}" factor="${4:-1}"
    y_points=()   # Reset array globale
    while IFS= read -r val; do y_points+=("$val"); done < <(
        awk -v m="$min" -v M="$max" -v n="$N" -v f="$factor" 'BEGIN{for(i=0;i<n;i++){x=i/(n-1);y=f==0?x:(exp(f*x)-1)/(exp(f)-1);printf "%.3f\n",m+y*(M-m)}}'
    )
}

generate_exp 0 100 "$NUM_POINTS" "$EXP_FACTOR"

generare_x "$NUM_POINTS" "$realDur"

if (( NORMALIZE )); then
    normalize_x "$streamDur" "$globalScale"
fi

result="points: ["
# Iteriamo sull'array
for i in "${!x_points[@]}"; do
    # Aggiungiamo la coppia [tempo, indice]
    if [ "$i" -eq 0 ]; then 
        result+="[${x_points[i]},${y_points[i]}]"
    else
        result+=",[${x_points[i]},${y_points[i]}]"
    fi
done
result+="]"

echo "for a stream of $streamDur sec"
echo "$result"