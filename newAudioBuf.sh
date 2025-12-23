#!/bin/bash
FROM=${2:-test}
TO=${3:-scherzetto}
shift 2

sed -i '' "s|${FROM}\.wav|${TO}\.wav|g" "$@"
