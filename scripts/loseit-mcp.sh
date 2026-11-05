#!/bin/sh
# Start loseit-mcp against the Lose It web build that's live right now:
# discover the GWT build IDs (falling back to the pinned values in .mcp.json),
# then run the server through loseit_serve.py, which refreshes the SDK's type
# schemas for that build.
dir=$(cd "$(dirname "$0")" && pwd)
ids=$(python3 -I "$dir/loseit_gwt_ids.py" 2>/dev/null)
sn=$(printf '%s\n' "$ids" | sed -n 's/^LOSEIT_STRONG_NAME=\([0-9A-F]\{32\}\)$/\1/p')
ph=$(printf '%s\n' "$ids" | sed -n 's/^LOSEIT_POLICY_HASH=\([0-9A-F]\{32\}\)$/\1/p')
if [ -n "$sn" ] && [ -n "$ph" ]; then
  export LOSEIT_STRONG_NAME="$sn" LOSEIT_POLICY_HASH="$ph"
else
  echo "loseit-mcp.sh: GWT ID discovery failed, using pinned values" >&2
fi
exec uvx -q --from git+https://github.com/cabird/loseit-mcp@c1bf69cefb2c709688a517fe9b030ad2fe3f67f5 \
  python -I "$dir/loseit_serve.py" "$@"
