#!/usr/bin/env bash
set -o pipefail

trap 'echo; exit 0' INT

while true; do
    # Get search term
    if [[ -z "$1" ]]; then
        read -rp "Search (or 'exit'): " term || exit 0
    else
        term="$1"
        shift
    fi

    [[ "$term" == "exit" ]] && exit 0
    [[ -z "$term" ]] && continue

    # Run search and capture final JSON filename
    file=$(
        python3 -u search.py "$term" \
            | tee /dev/tty \
            | tail -n 1
    )

    # Validate output
    if [[ -z "$file" || ! -f "$file" ]]; then
        echo "Search failed or produced no output"
        continue
    fi

    if jq -e 'length > 0' "$file" >/dev/null 2>&1; then
        ./search-lib.sh --title="Search: $term" "$file"
        # fzf exited → loop again
    else
        echo "No results found"
    fi
done
