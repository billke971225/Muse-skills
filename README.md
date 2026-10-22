# Muse-skills

Production-grade skills for [Muse](https://muse.ai) personal-agent workspaces — built, battle-tested, and used daily by multiple Muse instances.

给 Muse 个人智能体工作区的生产级 skill 集合：真实环境在跑、多台 Muse 实例日常共用。

Download the whole collection: https://github.com/billke971225/Muse-skills/archive/refs/heads/main.zip

## About

These are not demos. Every skill in this repo was written to solve a real operational problem — running a Feishu bot bridge around the clock, keeping 15 AI accounts alive behind one dashboard, researching what Chinese social platforms talked about in the last 30 days — and each one carries the scar tissue to prove it: measured failure modes, hard-won workarounds, and explicit "don't do this, it breaks" notes.

Skills are shared between Muse instances: one instance writes and hardens a skill, the others download it from here and put it straight to work.

## Skills

| Skill | What it does | Production evidence |
|---|---|---|
| [cockpit-tools-deploy](cockpit-tools-deploy/) | Deploy Cockpit Tools and import account data — one dashboard to run many Antigravity / Codex / Kiro accounts | Manages **15 AI accounts** (10 Antigravity + 3 Codex + 2 Kiro) in daily production, with a token-keeper that works around an upstream refresh bug |
| [feishu-bridge](feishu-bridge/) | Connect a Feishu (Lark) bot to Muse over the official WebSocket API: real-time DMs in, replies out, via a local inbox/outbox pipeline | Runs **24/7** as the owner's primary chat channel, with a watchdog that self-heals the bridge |
| [ugc-ad-studio](ugc-ad-studio/) | Build mobile-shot-style vertical UGC video ads to Meta specs from a reference ad | Used to produce real client-sample ads for paid editing gigs |
| [last30days-cn](last30days-cn/) | Research the last 30 days of discussion on Chinese platforms (Xiaohongshu, Weibo, Bilibili, Douyin, WeChat) with timestamps, authors, engagement and source links | Powers a **daily public-opinion briefing**; sources with no real data path are skipped, never replaced by search-engine filler |
| [ai-cli-auth](ai-cli-auth/) | Pick the correct login flow and network route for local AI CLIs (Codex / Pi / Antigravity) and verify real state before diagnosing "login problems" | Distilled from weeks of running three AI engines side by side, including their proxy and credential-path traps |
| [jev-decision](jev-decision/) | Ask Jev (TypeSafe's System One decision model) for a fast typed judgment — choice, yes/no probability, or graded score | Used as the quality/triage gate in daily content and outreach pipelines |
| [x-growth-playbook](x-growth-playbook/) | Run an X/Twitter growth operation end-to-end: account setup, English voice guide, daily cadence of originals + replies, quality gate, publish pipeline | Adapted from a proven account-growth playbook; drives a real account's daily operations |
| [remote-clean-browser](remote-clean-browser/) | Spin up a disposable clean-IP remote browser (Xvnc + noVNC + stock Firefox behind a clean proxy) so the owner can hand-complete logins that are sensitive to IP and browser fingerprint | The standard route for Google / ChatGPT-class logins in this workspace; login state persists in the profile for later automation |
| [ui-clone-skills](ui-clone-skills/) | Clone a real website — especially GSAP / Framer Motion / Webflow / Lenis / Lottie animation — into a React + Tailwind implementation: capture evidence first, decode the motion parameters, verify screen by screen | Vendored from the upstream Apache-2.0 project (see its `LICENSE.txt`), used for product-grade site replicas |
| [ad-creative-intel](ad-creative-intel/) | Break down competitor ads from the Facebook Ad Library — creative formats, copy structure, testing methodology — into a ready-to-use creative brief | Used in live ad-creative research for UGC campaigns |
| [hypit-video](hypit-video/) | Direct and produce videos with Hypit: generated media + authored components, SVML/SVS/SVRun authoring, runtime and credential setup | The production playbook behind an ongoing AI-video pipeline |

## Install

1. Clone or download this repo.
2. Copy the skill folder(s) you want into your own workspace's skills directory (e.g. `~/workspace/custom-skills/` for Muse workspaces).
3. Open the skill's `SKILL.md` and follow it — each skill documents its own prerequisites, credentials (via environment variables or your secret store — never hard-coded), and verification steps.

Some skills need API keys or local services; those requirements are listed at the top of each `SKILL.md`. Anything environment-specific in the docs (node IPs, domains, local paths) is written as a placeholder such as `<NODE_IP>` — substitute your own.

## License

MIT — except `ui-clone-skills/`, which is vendored from an upstream project and remains under its own Apache-2.0 license (`ui-clone-skills/LICENSE.txt`).
