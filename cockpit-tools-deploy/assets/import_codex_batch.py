#!/usr/bin/env python3
"""Batch-import Codex session-shaped exports into Cockpit (merge by storage id)."""
import json, hashlib, time, os, base64, sys

BASE = os.path.expanduser("~/.cockpit_tools")
FILES = sys.argv[1:]

def claims(jwt):
    parts = jwt.split(".")
    if len(parts) != 3:
        return {}
    p = parts[1] + "=" * (-len(parts[1]) % 4)
    return json.loads(base64.urlsafe_b64decode(p))

idx_path = f"{BASE}/codex_accounts.json"
index = {"version": "1.0", "detail_schema_version": 2, "accounts": [], "current_account_id": None}
if os.path.exists(idx_path):
    index = json.load(open(idx_path))
by_id = {a["id"]: a for a in index["accounts"]}
now = int(time.time())

for src in FILES:
    item = json.load(open(src))[0]
    idc = claims(item["id_token"])
    acc = claims(item["access_token"])
    auth_id = idc.get("https://api.openai.com/auth", {})
    auth_acc = acc.get("https://api.openai.com/auth", {})
    email = item.get("email") or idc.get("email")
    user_id = auth_id.get("chatgpt_user_id") or auth_acc.get("chatgpt_user_id") or idc.get("sub")
    plan_type = auth_id.get("chatgpt_plan_type") or auth_acc.get("chatgpt_plan_type")
    account_id = item.get("account_id") or auth_acc.get("chatgpt_account_id") or auth_id.get("chatgpt_account_id")
    orgs = auth_acc.get("organizations") or auth_id.get("organizations") or []
    organization_id = orgs[0].get("id") if orgs else (auth_acc.get("organization_id") or auth_id.get("organization_id"))

    seed = email.strip()
    if account_id:
        seed += "|" + account_id
    if organization_id:
        seed += "|" + organization_id
    aid = "codex_" + hashlib.md5(seed.encode()).hexdigest()
    created = by_id.get(aid, {}).get("created_at", now)

    account = {
        "id": aid, "email": email, "user_id": user_id, "plan_type": plan_type,
        "account_id": account_id, "organization_id": organization_id,
        "account_name": item.get("account_name"), "account_structure": item.get("account_structure"),
        "tokens": {"id_token": item["id_token"], "access_token": item["access_token"],
                   "refresh_token": item.get("refresh_token")},
        "token_updated_at": now, "quota": None, "tags": None,
        "created_at": created, "last_used": now,
    }
    os.makedirs(f"{BASE}/codex_accounts", exist_ok=True)
    with open(f"{BASE}/codex_accounts/{aid}.json", "w") as f:
        json.dump(account, f, indent=2, ensure_ascii=False)
    by_id[aid] = {"id": aid, "email": email, "plan_type": plan_type,
                  "created_at": created, "last_used": now}
    print(f"{email:28s} plan={plan_type} id={aid} {'(merged)' if created != now else '(new)'}")

index["accounts"] = list(by_id.values())
with open(idx_path, "w") as f:
    json.dump(index, f, indent=2, ensure_ascii=False)
print("total codex accounts:", len(index["accounts"]))
