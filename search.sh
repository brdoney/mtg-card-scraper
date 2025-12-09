#!/usr/bin/env bash
file=$(python3 -u search.py "$1" | tee /dev/tty | tail -1)
./search-lib.sh --title="Search: $1" "$file"
