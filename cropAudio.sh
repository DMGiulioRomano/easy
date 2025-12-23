#!/bin/bash
INPUT=$1
SKIP=${2:-0}
FINE=${3:-30.0}
DURATA=$(echo "scale=4; $FINE - $SKIP" | bc )
SKIP_="${SKIP//./_}"
DURATA_="${DURATA//./_}"

make INPUT=$INPUT SKIP=$SKIP DURATA=$DURATA "$INPUT-$SKIP_-$DURATA_.wav"