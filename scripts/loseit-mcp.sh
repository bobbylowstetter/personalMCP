#!/bin/sh
# Start loseit-mcp with the GWT build IDs Lose It is serving right now, so a new
# Lose It web deploy doesn't break the server. Falls back to the pinned values
# in .mcp.json if discovery fails.
dir=$(dirname "$0")
ids=$(python3 -I "$dir/loseit_gwt_ids.py" 2>/dev/null)
sn=$(printf '%s\n' "$ids" | sed -n 's/^LOSEIT_STRONG_NAME=\([0-9A-F]\{32\}\)$/\1/p')
ph=$(printf '%s\n' "$ids" | sed -n 's/^LOSEIT_POLICY_HASH=\([0-9A-F]\{32\}\)$/\1/p')
if [ -n "$sn" ] && [ -n "$ph" ]; then
  export LOSEIT_STRONG_NAME="$sn" LOSEIT_POLICY_HASH="$ph"
else
  echo "loseit-mcp.sh: GWT ID discovery failed, using pinned values" >&2
fi
exec uvx --from git+https://github.com/cabird/loseit-mcp@c1bf69cefb2c709688a517fe9b030ad2fe3f67f5 loseit-mcp "$@"
