#!/usr/bin/env bash
file=$(python3 -u search.py "$1" | tee /dev/tty | tail -1)

is_empty=$(jq -e length "$file")
if [[ is_empty -ne 0 ]]; then
	./search-lib.sh --title="Search: $1" "$file"
else
	echo "No results found"
fi
