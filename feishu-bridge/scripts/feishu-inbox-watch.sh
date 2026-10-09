#!/usr/bin/env bash
# feishu-inbox-watch: poll ~/workspace/feishu-bridge/inbox/ every 20s.
# Wake a worker when there are messages not yet in state/processed.json.
set -euo pipefail
source "$HATCH_HOOK_RUNTIME"

BASE="$HOME/workspace/feishu-bridge"
INBOX="$BASE/inbox"
PROCESSED="$BASE/state/processed.json"

[ -d "$INBOX" ] || { silent "no inbox dir" '{}'; }

# message_ids already processed
processed_ids=""
if [ -f "$PROCESSED" ]; then
  processed_ids=$(jq -r '.[]' "$PROCESSED" 2>/dev/null || true)
fi

new_msgs="[]"
for f in "$INBOX"/*.json; do
  [ -e "$f" ] || break
  mid=$(jq -r '.message_id // empty' "$f" 2>/dev/null || true)
  [ -n "$mid" ] || continue
  if ! printf '%s\n' "$processed_ids" | grep -qx "$mid"; then
    item=$(jq -c '{message_id, text, chat_id, ts}' "$f" 2>/dev/null || true)
    [ -n "$item" ] && new_msgs=$(printf '%s' "$new_msgs" | jq -c --argjson i "$item" '. + [$i]')
  fi
done

count=$(printf '%s' "$new_msgs" | jq 'length')
if [ "$count" -gt 0 ]; then
  wake "feishu-new-messages" "{\"count\": $count, \"messages\": $new_msgs}"
else
  silent "no new feishu messages" '{}'
fi
