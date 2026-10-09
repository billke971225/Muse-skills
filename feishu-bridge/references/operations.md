# Operations

## Reply rules (worker prompt logic)

- Tone: warm and direct, like texting a friend. Keep it under ~200 words.
- Simple chit-chat / simple Q&A (no tools, no decisions): reply directly.
- Needs tools, actions, decisions, or touches **money, deleting data, or
  sending things externally**: reply the fixed line
  "Got it, noted — I'll get back to you shortly", summarize the request for
  the main agent, and **never execute on your own**.
- Never output secrets, session contents, or internal system paths.

## What the user experiences

1. Sends a DM → instant ack ("received, replying…") in seconds = bridge alive.
2. Real reply ~20–60s later.
3. No ack within ~10s = bridge down; watchdog restarts it within 5 min.

## Routine commands

```bash
cd ~/workspace/feishu-bridge
<venv>/bin/python feishu_bridge.py status   # health (no secrets printed)
tail -20 logs/serve.log                     # recent activity

# restart (kill by pidfile precisely; never pkill -f — it kills your shell):
[ -f state/serve.pid ] && kill $(cat state/serve.pid); sleep 2
nohup <venv>/bin/python feishu_bridge.py serve > logs/serve.log 2>&1 &
sleep 10; tail -3 logs/serve.log

# test send (needs at least one inbox message for chat_id):
<venv>/bin/python feishu_bridge.py send --text "test"
```

## Known pitfalls

1. **Proxy patch** (SKILL.md rule 1): removed = WS never connects.
2. **Event structure**: payload is under `data.event`; `data.message`
   silently drops messages.
3. **No proactive first message**: the bot cannot DM the user first; the
   user must message once to establish `chat_id` and owner binding.
4. **Duplicate serve instances**: serve + watchdog can each start one,
   causing double acks. If two `feishu_bridge.py serve` processes exist,
   kill the older one, keep the pid in `state/serve.pid`.
5. **WS drops**: the egress proxy periodically kills long connections;
   the SDK's `auto_reconnect=True` re-establishes. Messages during the gap
   may be lost — ask the user to resend anything critical.
6. **Text only**: images/voice/video are discarded, not stored.
7. **Credential hygiene**: `state/*.json` must stay 600. If a secret ever
   appeared in chat, rotate it in the open platform console.

## Handoff checklist (new assistant taking over)

- [ ] `feishu_bridge.py status` → serve running, credentials present
- [ ] `tail -5 logs/serve.log` → recent inbox/outbox activity, no tracebacks
- [ ] `state/feishu.json` exists and is 600
- [ ] inbox hook enabled, watchdog cron present
- [ ] user sends a DM → ack in seconds → real reply within ~1 min
