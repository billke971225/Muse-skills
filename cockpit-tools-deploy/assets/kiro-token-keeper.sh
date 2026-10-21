#!/usr/bin/env bash
# Kiro IdC token keeper: refresh via JSON-body OIDC (Cockpit's form-body refresh is broken),
# then sync the fresh snapshot into (a) the profile snapshot, (b) ~/.aws/sso/cache,
# (c) the Cockpit account store (plaintext rewrite; the app re-encrypts on load).
# Usage: kiro-token-keeper.sh <profile-name>   (profiles defined below)
set -euo pipefail
export HOME="${HOME:-/home/hatch}"

PROFILE="${1:-cockpit-builderid}"
KIRO_DIR="$HOME/workspace/kiro-login"
COCKPIT_KIRO_DIR="$HOME/.cockpit_tools/kiro_accounts"
PROXY="socks5h://127.0.0.1:1088"
EXPECTED_IP="192.220.59.232"

case "$PROFILE" in
  cockpit-builderid)
    SNAPSHOT="$KIRO_DIR/kiro-auth-token.json"
    ACCOUNT_ID="kiro_e1a50564d035647658ce8582a65a9e8d"
    SSO_CACHE_COPY="$HOME/.aws/sso/cache/kiro-auth-token.json"
    MERGE_BASE=""
    ;;
  kiro-student)
    SNAPSHOT="$KIRO_DIR/student-auth-token.json"
    ACCOUNT_ID="kiro_83724c614126df868c89d505a0b0e7a6"
    SSO_CACHE_COPY=""
    MERGE_BASE="$KIRO_DIR/import-student.json"
    ;;
  *)
    echo "unknown profile: $PROFILE" >&2; exit 2;;
esac

# 1. Verify clean egress before touching AWS endpoints.
IP="$(curl -s --proxy "$PROXY" --max-time 15 https://ipinfo.io/ip || true)"
if [ "$IP" != "$EXPECTED_IP" ]; then
  echo "ABORT: clean egress expected $EXPECTED_IP got '${IP}'" >&2; exit 1
fi

# 2. Build refresh body from the current snapshot and call the OIDC token endpoint (JSON!).
python3 - "$SNAPSHOT" <<'PYEOF'
import json, sys
snap = json.load(open(sys.argv[1]))
reg = snap["clientRegistration"]
body = {"clientId": reg["clientId"], "clientSecret": reg["clientSecret"],
        "refreshToken": snap["refreshToken"], "grantType": "refresh_token"}
json.dump(body, open("/tmp/kiro-refresh-body.json", "w"))
PYEOF

RESP="/tmp/kiro-refresh-resp.json"
CODE="$(curl -s --proxy "$PROXY" --max-time 30 -o "$RESP" -w '%{http_code}' \
  -X POST https://oidc.us-east-1.amazonaws.com/token \
  -H 'Content-Type: application/json' -d @/tmp/kiro-refresh-body.json)"
if [ "$CODE" != "200" ]; then
  echo "ABORT: refresh HTTP $CODE: $(head -c 200 "$RESP")" >&2; exit 1
fi

# 3. Merge the response into the snapshot; sync all copies; rewrite the Cockpit account file.
python3 - "$SNAPSHOT" "$RESP" "$ACCOUNT_ID" "$COCKPIT_KIRO_DIR" "${SSO_CACHE_COPY:-}" "${MERGE_BASE:-}" <<'PYEOF'
import json, sys, time, os
snap_path, resp_path, account_id, cockpit_dir, sso_copy, merge_base = sys.argv[1:7]
snap = json.load(open(snap_path))
resp = json.load(open(resp_path))
snap["accessToken"] = resp["accessToken"]
if resp.get("refreshToken"):
    snap["refreshToken"] = resp["refreshToken"]
if resp.get("idToken"):
    snap["idToken"] = resp["idToken"]
snap["expiresIn"] = resp.get("expiresIn", 3600)
snap["expiresAt"] = int(time.time()) + snap["expiresIn"]
snap["tokenType"] = resp.get("tokenType", "Bearer")
json.dump(snap, open(snap_path, "w"), indent=2)
os.chmod(snap_path, 0o600)
if sso_copy:
    os.makedirs(os.path.dirname(sso_copy), exist_ok=True)
    json.dump(snap, open(sso_copy, "w"), indent=2)
    os.chmod(sso_copy, 0o600)

acct_path = os.path.join(cockpit_dir, f"{account_id}.json")
acct = {}
if os.path.exists(acct_path):
    try:
        acct = json.load(open(acct_path))
        if "ciphertext" in acct:  # encrypted envelope: rebuild from known fields
            acct = {}
    except Exception:
        acct = {}
now = int(time.time())
if merge_base:
    base = json.load(open(merge_base))[0]
    base["access_token"] = snap["accessToken"]
    base["refresh_token"] = snap["refreshToken"]
    base["expires_at"] = snap["expiresAt"]
    base["kiro_auth_token_raw"] = snap
    base.pop("quota_query_last_error", None)
    base.pop("quota_query_last_error_at", None)
    base["status"] = "normal"
    base["last_used"] = now
    json.dump(base, open(acct_path, "w"), indent=2, ensure_ascii=False)
    print("keeper: refreshed + synced (merge mode)", account_id)
else:
    base = {
        "id": account_id,
        "email": acct.get("email", ""),
        "login_provider": "BuilderId",
        "access_token": snap["accessToken"],
        "refresh_token": snap["refreshToken"],
        "token_type": snap.get("tokenType", "Bearer"),
        "expires_at": snap["expiresAt"],
        "idc_region": "us-east-1",
        "issuer_url": snap.get("issuerUrl", "https://view.awsapps.com/start"),
        "client_id": snap.get("clientId"),
        "kiro_auth_token_raw": snap,
        "created_at": acct.get("created_at", now),
        "last_used": now,
    }
    json.dump(base, open(acct_path, "w"), indent=2, ensure_ascii=False)
    print("keeper: refreshed + synced", account_id)
PYEOF

# 4. Restart Cockpit so it loads (and re-encrypts) the fresh account file.
systemctl restart cockpit-tools.service
echo "keeper: cockpit restarted"
