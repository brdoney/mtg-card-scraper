#!/usr/bin/env bash

# Parse arguments
TITLE=""
JSON_FILES=()

for arg in "$@"; do
  if [[ "$arg" == --title=* ]]; then
    TITLE="${arg#--title=}"
  else
    JSON_FILES+=("$arg")
  fi
done

# Default to ./out/*.json if no files specified
if [ ${#JSON_FILES[@]} -eq 0 ]; then
  JSON_FILES=(./out/*.json)
fi

jq -r -s '
    map(.[])
    | sort_by(.price)
    | reverse
    | .[]
    | "\u001b]8;;\(.dest)\u0007\(.name | trim)\u001b]8;;\u0007\t\(.attributes | trim)\t\(.store)\tQty: \(.stock) $\(.price)\t\(.img_src)"
' "${JSON_FILES[@]}" >/tmp/cards.tsv

mkdir -p "$HOME/.cache/mtg-card-images"

# Clear kitty graphics on exit
trap 'kitty +kitten icat --clear' EXIT

# Build FZF command with optional title
FZF_OPTS=(--ansi --preview-window=right:50%:wrap --delimiter='\t' --no-sort --height=100%)
if [ -n "$TITLE" ]; then
  FZF_OPTS+=(--header="$TITLE")
fi

cat /tmp/cards.tsv | fzf "${FZF_OPTS[@]}" \
  --with-nth=1,2,3,4 \
  --preview '
    url=$(echo {} | cut -f5);
    rest=$(echo {} | cut -f1-4 | tr "\t" "\n")
    echo "$rest"

    width=$FZF_PREVIEW_COLUMNS
    height=$((FZF_PREVIEW_LINES - 4))

    fname="$HOME/.cache/mtg-card-images/$(echo "$url" | md5sum | cut -d" " -f1).png";
    if [ ! -f "$fname" ]; then
      curl -s --fail --max-time 5 -o "$fname" "$url" 2>/dev/null;
    fi;
    if [ -f "$fname" ]; then
      # echo "${FZF_PREVIEW_COLUMNS}x${FZF_PREVIEW_LINES}@0x0"
      kitty +kitten icat --clear --transfer-mode=memory --stdin=no --scale-up --place=${width}x${height}@0x0 "$fname";
    else
      echo "Image not available";
    fi
  '
