#!/bin/bash
FROM=${1:-test}
TO=${2:-scherzetto}
shift 2

sed -i '' "s|${FROM}\.wav|${TO}\.wav|g" "$@"
