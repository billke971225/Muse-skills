#!/usr/bin/env python3
"""Import Antigravity simple-format exports ({email, refresh_token}) into Cockpit,
replicating modules/import.rs::import_from_json_logic + account::upsert_account.
Refresh goes DIRECT (no proxy) per the Antigravity routing rule."""
import json, hashlib, time, os, subprocess, sys

CLIENT_ID = os.environ.get("ANTIGRAVITY_OAUTH_CLIENT_ID", "")  # Cockpit/Antigravity desktop OAuth client (public, ships in the open-source app); get it from the cockpit-tools source you deployed: grep for apps.googleusercontent.com
CLIENT_SECRET = os.environ.get("ANTIGRAVITY_OAUTH_CLIENT_SECRET", "")  # same source as CLIENT_ID; never commit the literal
CLIENT_KEY = "antigravity_enterprise"

BASE = os.path.expanduser("~/.cockpit_tools")
FILES = [
    "billjing211_2026-10-21.json", "billke971225_2026-10-21.json", "kcj95445_2026-10-21.json",
    "kcjbill95445_2026-10-21.json", "ke089160_2026-10-21.json", "ke95445_2026-10-21.json",
    "ke971125a_2026-10-21.json", "ke971225_2026-10-21.json", "kebill971225_2026-10-21.json",
    "support_2026-10-21.json",
]
SRC_DIR = "/home/hatch/workspace/user/files"

def refresh(refresh_token):
    body = {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
            "refresh_token": refresh_token, "grant_type": "refresh_token"}
    import urllib.request, urllib.parse
    req = urllib.request.Request("https://oauth2.googleapis.com/token",
                                 data=urllib.parse.urlencode(body).encode())
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")

os.makedirs(f"{BASE}/accounts", exist_ok=True)
idx_path = f"{BASE}/accounts.json"
index = {"version": "2.0", "accounts": []}
if os.path.exists(idx_path):
    index = json.load(open(idx_path))
by_id = {a["id"]: a for a in index["accounts"]}

results = []
for fname in FILES:
    items = json.load(open(f"{SRC_DIR}/{fname}"))
    item = items[0]
    email, rt = item["email"], item["refresh_token"]
    status, resp = refresh(rt)
    if status != 200 or "access_token" not in resp:
        results.append((email, f"FAIL http={status} err={resp.get('error', '?')}"))
        continue
    now = int(time.time())
    expires_in = int(resp.get("expires_in", 3600))
    aid = "antigravity_" + hashlib.md5(email.strip().lower().encode()).hexdigest()
    token = {
        "access_token": resp["access_token"],
        "refresh_token": resp.get("refresh_token", rt),
        "expires_in": expires_in,
        "expiry_timestamp": now + expires_in,
        "token_type": "Bearer",
        "email": email,
        "oauth_client_key": CLIENT_KEY,
    }
    if resp.get("id_token"):
        token["id_token"] = resp["id_token"]
    existing_created = by_id.get(aid, {}).get("created_at", now)
    account = {
        "id": aid, "email": email, "name": None,
        "pending_oauth": False,
        "token": token,
        "quota": None,
        "disabled": False,
        "created_at": existing_created,
        "last_used": now,
    }
    with open(f"{BASE}/accounts/{aid}.json", "w") as f:
        json.dump(account, f, indent=2, ensure_ascii=False)
    by_id[aid] = {"id": aid, "email": email, "name": None,
                  "created_at": existing_created, "last_used": now}
    results.append((email, "OK"))

index["accounts"] = list(by_id.values())
with open(idx_path, "w") as f:
    json.dump(index, f, indent=2, ensure_ascii=False)

for email, r in results:
    print(f"{email:28s} {r}")
print("total antigravity accounts in index:", len(index["accounts"]))
