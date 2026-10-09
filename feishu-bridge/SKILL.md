---
name: "feishu-bridge"
description: "Connect a Feishu (Lark) bot to the assistant over the official WebSocket API: receive user DMs in real time and reply through a local inbox/outbox pipeline. Use when the user wants to chat with the assistant from Feishu, or asks to set up / operate / troubleshoot a Feishu bot bridge."
metadata: { "includeInPrompt": true }
---

# Feishu Bridge

## Purpose

Give the assistant a private Feishu DM channel: the user messages the bot in
Feishu, the bridge receives it in real time over the official `lark-oapi`
WebSocket long connection, and replies flow back through a local
inbox → worker → outbox pipeline. The user always gets an instant
"received" ack within seconds (liveness proof), then the real reply.

## Tooling

Helper lives in `scripts/` (copy it to your own bridge dir, e.g.
`~/workspace/feishu-bridge/`):

- `scripts/feishu_bridge.py` — the bridge. Stdlib + `lark-oapi` only.
  Run with a venv python that has `lark-oapi` installed.
- `scripts/feishu-inbox-watch.sh` — hook polling script (20s cadence).

Three commands:

| Command | Effect |
|---|---|
| `python3 feishu_bridge.py serve` | Daemon: WS receive → `inbox/`; outbox loop sends every 2s |
| `python3 feishu_bridge.py send --text "hi"` | Test send (uses chat_id from latest inbox msg) |
| `python3 feishu_bridge.py status` | creds present/absent, owner, process, inbox/outbox counts (never prints secrets) |

Directory layout it manages:

```
<bridge-dir>/
├── feishu_bridge.py
├── inbox/                # one <message_id>.json per received DM
├── outbox/pending/       # {"chat_id","text"} — serve sends every 2s
├── outbox/sent/          # archive
├── logs/serve.log
└── state/                # feishu.json (600), owner_open_id, processed.json, serve.pid
```

## Auth

1. Create a Feishu open-platform custom app, enable bot capability, add the
   `im.message.receive_v1` event, grant single-chat send/receive permissions,
   and choose **WebSocket long connection** (no public URL needed).
   See `references/setup.md` for the click path.
2. Write `{"app_id": "...", "app_secret": "..."}` to
   `<bridge-dir>/state/feishu.json` with mode **600**.
3. Never print, log, or memorize the secret. `status` prints present/absent only.
   If a secret was ever pasted in chat, treat it as exposed and rotate it in
   the open platform after debugging.

## Operating Rules

1. **Proxy patch is load-bearing.** If the host's outbound traffic must go
   through a proxy, the SDK's WS client defaults to `proxy=None` and will not
   connect. The script monkey-patches
   `lark_oapi.ws.client._ws_connect_kwargs` to `{"proxy": True}` (env proxy).
   Do not remove it; without it the WS handshake fails.
2. **Event payload lives under `data.event`.** `P2ImMessageReceiveV1` carries
   `data.event.message` (message_id, message_type, chat_type, chat_id,
   content as JSON string) and `data.event.sender.sender_id.open_id`.
   Reading `data.message` directly drops messages silently.
3. **Receive filters (in order):** only `chat_type == "p2p"`, only
   `message_type == "text"`. The first DM sender is locked as owner
   (`state/owner_open_id`); later messages from anyone else are ignored.
   The bot **cannot initiate** a conversation — the user must DM first.
4. **Reply guarantee:** the handler sends an instant ack
   ("received, replying…") synchronously after the inbox write — this is the
   liveness signal. A scheduled worker (hook every ~20s) then generates the
   real reply per `references/operations.md` and drops it in
   `outbox/pending/`; serve sends it within 2s. If the user gets no ack in
   ~10s, the bridge is down (watchdog restarts it).
5. **Watchdog:** run `status` every 5 minutes; if serve is not running,
   restart it (`kill $(cat state/serve.pid)`, then `nohup … serve &`).
   Never `pkill -f` the bridge — the pattern matches your own shell.
6. **VM rebuilds** wipe `/etc` but keep the workspace: after a rebuild,
   re-run `serve`; the watchdog covers this automatically.
7. Text only. Images/voice/video are discarded by design.
