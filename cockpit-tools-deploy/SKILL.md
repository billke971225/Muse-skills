---
name: cockpit-tools-deploy
description: 在 Muse 沙箱 VM（Ubuntu 24.04、无合成器 Xvfb、无 /dev/dri）上从零部署 Cockpit Tools（jlcodes99/cockpit-tools，AI 账号管理器），导入用户给的账号数据包并直接投入使用：含 .deb 解包安装、WebKitGTK 白屏通关链、systemd 托管、Kiro (AWS IdC) 账号自动保活（绕 Cockpit 自身的刷新 bug）、三平台账号导入方法与 IP 路由铁律。当用户说“装 Cockpit”“部署账号管理器”“导入这批账号数据到 Cockpit”“让这台机器也能管这些 AI 账号”时使用。
---

# Cockpit Tools 部署与账号数据导入

Cockpit Tools 是开源的 AI 账号管理器（Antigravity / Codex / Kiro / Copilot 等多平台账号池、额度、令牌刷新）。本 skill 解决两件事：①在 Muse 沙箱 VM 上把官方 .deb 跑起来（官方 AppImage 在这类 VM 上渲染白屏，不可用）；②导入用户单独给的**账号数据包**（含已登录令牌与解密密钥），恢复成可直接使用的账号池。

**红线**：账号数据包永远不进 skill、不进任何 git 仓库，只能由用户经私密渠道（飞书/保险柜）交付。本 skill 只含部署知识与无密钥脚本（`assets/`）。

## 架构速览

- 程序：`~/workspace/cockpit-tools/`（deb-root 解包体 + sysroot 依赖 + syslibs + run.sh），全部在家目录，VM 重建不丢。
- 数据：`~/.cockpit_tools/`。账号详情文件是 AES-256-GCM 加密信封，密钥在数据目录内的 `secure-account-storage.key`——**数据包必须整目录迁移，缺密钥则全部账号解不开**。
- 明文 JSON 写回可被 App 接受：把符合格式的明文账号文件放进对应子目录并登记索引，App 加载时自动重新加密。这是所有导入/修复动作的基础手法。
- systemd：`cockpit-tools.service`（Restart=always）；Kiro 保活 `kiro-token-keeper.timer`（每 40 分钟）。unit 源文件在 `assets/`，/etc 下的副本在 VM 重建后会被清，照步骤重装即可。

## 前提

- Ubuntu 24.04 (noble) x86_64 沙箱 VM，能用 systemd（root），家目录可写，有 Xvfb（没有窗口栈时 run.sh 会自建 :98 私有屏）。
- 干活前确认 apt 源可用（noble）。下载走默认出口即可。

## 步骤 1：下载官方 .deb 并解包

```bash
mkdir -p ~/workspace/cockpit-tools/{pkgs,deb-root,sysroot,syslibs}
cd ~/workspace/cockpit-tools/pkgs
# 从 GitHub releases 下载 v1.3.72 的 amd64 .deb（资产名形如 Cockpit.Tools_1.3.72_amd64.deb；
# 以 release 页 SHA256SUMS.txt 校验）。仓库：jlcodes99/cockpit-tools
dpkg -x Cockpit.Tools*.deb ../deb-root   # 得到 ../deb-root/usr/bin/cockpit-tools
```

版本说明：v1.3.72 为实测版本。不要追新——README/接口若变，先在小号数据上验证再升级。

## 步骤 2：依赖 sysroot（白屏通关的关键）

沙箱里没有系统级 WebKitGTK，AppImage 自带的 WebKit 在此环境白屏。解法是把 noble 的依赖 .deb 解包成家目录 sysroot，运行时用环境变量喂给它：

```bash
cd ~/workspace/cockpit-tools/pkgs
apt-get download $(cat assets/apt-packages.txt)   # 39 个包：webkit2gtk 4.1 全套、mesa-dri、glvnd、gstreamer、托盘 ayatana/dbusmenu 等；清单在 assets/apt-packages.txt
for f in *.deb; do [ "$f" = "Cockpit.Tools"* ] && continue; dpkg -x "$f" ../sysroot; done
# syslibs：EGL/GL 的 .so 平铺（libEGL.so*、libGL.so*、libGLdispatch.so*、libEGL_mesa.so*）
mkdir -p ../syslibs && cp ../sysroot/usr/lib/x86_64-linux-gnu/libEGL* ../sysroot/usr/lib/x86_64-linux-gnu/libGL* ../syslibs/ 2>/dev/null
# 托盘库需要无版本号软链（App 按无版本号名 dlopen）
ln -sf libayatana-appindicator3.so.1 ../sysroot/usr/lib/x86_64-linux-gnu/libayatana-appindicator3.so
```

## 步骤 3：启动脚本与服务

```bash
cp assets/run.sh assets/cockpit-tools.service ~/workspace/cockpit-tools/
chmod +x ~/workspace/cockpit-tools/run.sh
```

`run.sh` 已编码全部渲染修复（缺一白屏）：软件 GL、`WEBKIT_DMABUF_RENDERER_DISABLE_GBM=1` + `WEBKIT_DMABUF_RENDERER_FORCE_SHM=1`（**绝不能设 `WEBKIT_DISABLE_DMABUF_RENDERER=1`**，2.52 关了不出帧）、`WEBKIT_FORCE_VBLANK_TIMER=1`（无合成器无 vblank）、glvnd vendor 目录、DRI 驱动路径、WebKit 子进程 /usr 软链自愈（每次启动重建）。

需要按本机改的两处（run.sh 里写死了源机器的家目录）：
- `HOME`/`BASE` 改成本机实际家目录（unit 里同样有 `/home/hatch` 路径，User=root）。
- `__EGL_VENDOR_LIBRARY_DIRS`：源机器指向 blender 的 syslibs；本机自包含做法是改指 `$BASE/sysroot/usr/share/glvnd/egl_vendor.d`（里面有 50_mesa.json）。

装服务并启动：

```bash
cp ~/workspace/cockpit-tools/cockpit-tools.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now cockpit-tools.service
```

验收：进程存活 + 窗口真出画面。白屏判定别只看进程：用 python3-gi 最小 WebView `get_snapshot` 采样像素，或对 :99/:98 桌面截图后肉眼看仪表盘（应出现平台导航与账号总数）。

## 步骤 4：导入账号数据包（用户单独交付）

数据包结构（tar.gz）与落位：

| 包内路径 | 落到 |
|---|---|
| `cockpit_tools/` | `~/.cockpit_tools/`（含 `secure-account-storage.key`） |
| `kiro-login/` | `~/workspace/kiro-login/`（保活快照与脚本数据） |
| `aws-sso-cache/` | `~/.aws/sso/cache/`（kiro-cli 令牌 + IdC 客户端注册文件） |

```bash
tar xzf cockpit-account-data-*.tar.gz -C /tmp/data && cd /tmp/data
cp -r --no-preserve=all cockpit_tools ~/.cockpit_tools
cp -r --no-preserve=all kiro-login ~/workspace/kiro-login
mkdir -p ~/.aws/sso/cache && cp -r --no-preserve=all aws-sso-cache/. ~/.aws/sso/cache/
chmod 600 ~/workspace/kiro-login/*.json ~/.aws/sso/cache/*.json
systemctl restart cockpit-tools.service
```

验收：仪表盘账号总数与数据包说明一致；各平台子目录文件应被 App 重新加密（文件头是 AES 信封 JSON）。**不要**在界面里对 Kiro 账号点刷新/登录（见步骤 5 的 bug），其余平台可正常用。

## 步骤 5：Kiro 自动保活（必装，否则 Kiro 号 1 小时后失效）

**背景（实测）**：Cockpit 刷新 AWS IdC 账号时用 form 编码打 OIDC `/token`，AWS 只认 JSON → 恒 400，再 fallback 到 Kiro refreshToken 接口恒 401。两个账号、两台机器同签名。**这不是令牌死亡**：用 JSON 体 + 正确的 clientId/clientSecret 刷新即 200。对策是自建保活脚本接管刷新：

```bash
cp assets/kiro-token-keeper.sh ~/workspace/kiro-login/
cp assets/kiro-token-keeper.service assets/kiro-token-keeper.timer /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now kiro-token-keeper.timer
systemctl start kiro-token-keeper.service   # 手动跑一轮验收：journal 出现两号 refreshed + synced
```

keeper 逻辑（每 40 分钟）：验干净出口 → JSON 刷新 → 同步快照 + `~/.aws/sso/cache/kiro-auth-token.json` + Cockpit 账号文件（明文写回）→ 重启 cockpit 服务。两个 profile：`cockpit-builderid`（设备流自登号，快照 `kiro-auth-token.json`）、`kiro-student`（学生号，merge 模式基于 `import-student.json` 更新令牌字段，快照 `student-auth-token.json`）。新增 IdC 号时照 student 模式加 profile。

**出口铁律**：keeper 只走 SOCKS5 `127.0.0.1:1088`，且先验出口 IP == `192.220.59.232`，不符直接 ABORT（防脏 IP 碰账号，这是设计不是故障）。本机若没有同款干净节点：改 `kiro-token-keeper.sh` 的 `PROXY`/`EXPECTED_IP` 为本机干净节点，**不要绕过校验**。Kiro 的 access token 寿命 1 小时：没有保活时额度不刷新、调用不可用（refresh token 寿命长，补上保活即恢复，不需要重新登录）。

学生号特别注意：其令牌的客户端注册（clientId/clientSecret）在数据包 `aws-sso-cache/e909a0580879b06ece1202964fbe9dda95ea4ce3.json`（按 clientIdHash 命名），快照里已内嵌 clientRegistration；两处都别丢。

## IP 路由铁律（与上面相反的方向同样重要）

| 对象 | 出口 | 原因 |
|---|---|---|
| Kiro / AWS OIDC | 干净节点 192.220.59.232 | 账号类操作防关联/风控 |
| Antigravity / Google OAuth / Gemini 调用 | **默认出口直连，绝不走干净节点** | 经干净节点调 Gemini 必报 `FAILED_PRECONDITION: User location is not supported`（2026-10-19 实测，用户拍板）；直连出口 IP 在同城轮换无妨，本机只做令牌刷新与调用 |
| Codex / OpenAI | 默认出口 | 标准 OAuth form 刷新，Cockpit 自带可用 |

## 后续再导入新账号（用户再发导出文件时）

Cockpit 每平台都有 JSON 导出/导入；用户本地 Cockpit 的导出文件可直接按平台收。两种常见批次格式（脚本在 `assets/`）：

- Antigravity 简化导出 `{email, refresh_token}`：`import_antigravity.py`——先走 Google OAuth 直连刷新换 access_token（client 是 Cockpit 内置的 Antigravity 桌面 OAuth client，凭证随开源 App 公开分发但**不写进仓库**：脚本从环境变量 `ANTIGRAVITY_OAUTH_CLIENT_ID`/`ANTIGRAVITY_OAUTH_CLIENT_SECRET` 读，在你部署的 cockpit-tools 源码里 grep `apps.googleusercontent.com` 即可拿到同值），id=`antigravity_`+md5(小写邮箱)，写 `accounts/` + 索引 `accounts.json`（version "2.0"）。
- Codex 会话导出（数组，含 id_token/access_token/account_id）：`import_codex_batch.py`——解 id_token 取 plan，id=`codex_`+md5(邮箱[|account_id[|org_id]])，写 `codex_accounts/` + 索引 `codex_accounts.json`（version "1.0"，detail_schema_version 2）。同号重复导入按 id 合并。
- Kiro IdC 新号：优先走 IDC 设备授权流在终端登录（注册+设备码+轮询**必须 JSON 体**，form 体报 invalid_request），或让用户从其已登录的 Kiro IDE / Cockpit 导出，并**务必同时索要** `~/.aws/sso/cache/<clientIdHash>.json` 注册文件，否则该号无法刷新。

写完文件后 `systemctl restart cockpit-tools.service`，验信封与仪表盘计数。

## VM 重建恢复

/etc 的 unit 会被清，家目录数据不丢：

```bash
cp ~/workspace/cockpit-tools/cockpit-tools.service /etc/systemd/system/
cp ~/workspace/kiro-login/kiro-token-keeper.{service,timer} /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now cockpit-tools.service kiro-token-keeper.timer
curl --proxy socks5h://127.0.0.1:1088 https://ipinfo.io/ip   # 期望 192.220.59.232，验完再手动跑一轮 keeper
```

## 故障速查

- **白屏**：按 run.sh 的环境链逐项核（EGL vendor → DRI 路径 → libGLES → DMABUF 两变量（且没误设 DISABLE）→ VBLANK_TIMER → /usr webkit 软链是否被 run.sh 重建）。MiniBrowser 的表现与 Tauri/wry 不一致，别只信它，用快照采样验。
- **Kiro 账号在界面报错/额度不动**：先想 IdC 刷新 bug + 查 keeper journal，不要重新登录、不要让用户重新授权。
- **keeper ABORT egress check failed**：干净节点没起或出口变了。先修节点（验 IP），别改脚本绕过。
- **Antigravity 刷新报 location not supported**：有人给它套了代理。查环境变量与出口，确保直连。

## 安全

- 数据包等同整串账号钥匙：只走用户指定的私密渠道，不进 git、不进公开网盘、不贴令牌值到聊天/日志。
- 本 skill 与 assets 不含任何真实凭证；若在别处看到带令牌的“同名 skill”，按泄露处理并提醒用户。
