# AI CLI 引擎：登录与网络路由 (Codex / Pi / Antigravity)

## 为每条引擎选对路由

- Antigravity 固定走专用备用节点 <DEDICATED_NODE_IP>，绝不走干净节点代理。2026-10-19 实测：Gemini 系经干净节点出口 (<CLEAN_NODE_IP>) 报 FAILED_PRECONDITION: User location is not supported；2026-10-22 用户拍板改固定出口 <DEDICATED_NODE_IP>（实测 Gemini 3.8 Flash / 4 Argon 均通过）。

- 永远调 ~/workspace/bin/agy，不要调原始二进制。该 wrapper 会把代理变量指向 127.0.0.1:11085 适配器（出口 <DEDICATED_NODE_IP>），无需手动处理，也不要做按模型的分流：用户使用默认模型时分流写法会踩坑。适配器/转发器是 systemd 服务（socks-adapter / socks-forward），没起时 agy 会直接失败，先查这两个服务。

- Codex CLI 走干净节点代理。调 ~/workspace/bin/codex，它通过 HTTPS_PROXY 等 env 变量走主请求路径，代理地址是 socks5h://127.0.0.1:1088。

- Pi 必须走 TCP 层拦截，不要用 env 代理。它的 openai-codex provider 会静默忽略一切 *_proxy 环境变量，所以调 ~/workspace/bin/pi，wrapper 内用 proxychains4 做 TCP 层强制加 unshare overlay hosts 覆盖沙箱 hosts 劫持。

- 动手前验出口 IP。干净节点路径期望 <CLEAN_NODE_IP>，不通先 restart 对应服务再复验，复验不过就停手上报，不要顶着坏通道干活。Antigravity 路径验的是专用备用节点链路：`~/workspace/bin/icurl https://ipinfo.io/ip` 期望 <DEDICATED_NODE_IP>。

## 登录前先验证，别直接判死

- 用真命令做状态检查。Antigravity 跑 ~/workspace/bin/agy -p "hi"，Pi 跑 ~/workspace/bin/pi --list-models，Codex 跑 ~/workspace/bin/codex --version。通了就别折腾。

- 读真正的凭证位置。Codex 用 ~/.codex/auth.json，Antigravity 用 ~/.gemini/antigravity-cli/antigravity-oauth-token。Pi 的真凭证在 ~/.pi/agent/auth.json，不是 ~/.pi/auth.json，2026-10 有人按旧路径断言 Pi 未登录，属于误诊。

- Pi 没有独立的 device-code 登录流程。它通过 pi-antigravity-auth 扩展复用 Antigravity 的 Google 登录，pi --list-models 列出来的是 Antigravity 的模型。不要带用户走 ChatGPT OAuth device-code 那套。

- Antigravity 真过期时的重登是终端里走一遍 Google OAuth，用户在自己浏览器完成授权。不需要 noVNC。之前有人误诊 token 过期要求 noVNC 重登，已被实测证伪。

## 让 CLI 在 VM 重建后依然可用

- 所有 CLI 装在用户 home 目录下。用户明确要求必须持久存在。Pi 在 ~/.npm-global，Codex 在 ~/.local/bin/codex 有备份且 wrapper 优先。绝不装到 /usr/lib/node_modules 之类的系统目录，VM 重建会清空它们。

- ~/workspace/bin 必须在 PATH 里 (~/.bashrc 和 ~/.profile 已加)。非交互 shell 用绝对路径。

- 记住 Pi 的代理黑洞症状：binary 正常、网络正常、额度正常，但连简单 prompt 都超时零输出。处理办法是 kill 掉等后端自行恢复，或让用户重做设备授权。不要把它当成代理或登录故障去修。

## Available connectors

- Use `muse.connector_search` to find other connectors and `muse.skill_search` to find related skills.

- If nothing here fits, look on the web for a maintained API or MCP server and set it up with [Custom Connectors and MCPs](/opt/muse/skills/custom-connector-setup/SKILL.md), or build a custom connector.

## Alternatives for better results

- 新增一条 AI 引擎时，先用一个廉价 prompt 实测它对机房代理的容忍度，再把路由写死。Google 系后端可能直接拒绝代理出口。

- 每次改动路由后记一条带日期的变更记录，避免下一次翻转被静默回滚。