# Feishu Open Platform App Setup

Do this once in the [Feishu open platform console](https://open.feishu.cn/app):

1. **Create app**: custom app for your own enterprise. Copy the **App ID**
   and **App Secret** from the credentials page.
2. **Enable bot**: add the bot capability (机器人).
3. **Events**: subscribe to `im.message.receive_v1` (receive messages).
4. **Permissions**: grant single-chat message receive + send
   (`im:message` family). Publish/apply as the console requires.
5. **Transport**: choose **WebSocket long connection** (长连接). No public
   URL or callback address needed — this is why the bridge works on a
   machine without inbound connectivity.
6. **Bind owner**: DM the bot once from Feishu. The first sender is locked
   as owner; the bridge ignores everyone else afterwards.

Then on the assistant host:

```bash
pip install lark-oapi          # into the venv you run the bridge with
mkdir -p ~/workspace/feishu-bridge
cp <skill>/scripts/feishu_bridge.py ~/workspace/feishu-bridge/
# write credentials (mode 600, never in chat logs):
printf '%s' '{"app_id": "YOUR_APP_ID", "app_secret": "YOUR_APP_SECRET"}' \
  > ~/workspace/feishu-bridge/state/feishu.json
chmod 600 ~/workspace/feishu-bridge/state/feishu.json
cd ~/workspace/feishu-bridge
nohup <venv>/bin/python feishu_bridge.py serve > logs/serve.log 2>&1 &
sleep 15 && <venv>/bin/python feishu_bridge.py status
```

Wire the reply loop (assistant-side scheduling):

- **Inbox hook** (every ~20s): use `<skill>/scripts/feishu-inbox-watch.sh`
  as the polling script. On wake, the worker reads new `inbox/*.json`,
  generates a reply per `operations.md`, writes
  `outbox/pending/<message_id>.json` as `{"chat_id","text"}`, and appends
  the id to `state/processed.json`.
- **Watchdog** (every 5 min): `status` → restart serve if not running.

Then DM the bot "hello" from Feishu: you should get the instant ack in
seconds and the real reply within about a minute.
