

# UI Clone Skills（网站动效复刻）

上游：`voidmatcha/ui-clone-skills`（Apache-2.0，见 `LICENSE.txt`），完整 skill 树在 `skills/` 下，
子 skill 之间用相对路径互相引用，不要挪动目录结构。

## 三个子 skill，按需进入

| 子 skill | 位置 | 什么时候用 |
|---|---|---|
| `ui-capture` | `skills/ui-capture/SKILL.md` | 只要"先把证据抓下来"：截图、滚动状态、hover/click 行为、视差、过渡录像。不建站、不修 bug。 |
| `ui-reverse-engineering` | `skills/ui-reverse-engineering/SKILL.md` | **主流程**：给一个线上 URL，输出 React + Tailwind 复刻版。先读它的 SKILL.md 再动手，它规定了输入、门禁和完成标准。 |
| `visual-debug` | `skills/visual-debug/SKILL.md` | 复刻版和原站长得不一样时：用 AE/SSIM、像素、computed-style、transition diff 定位并修。 |

（上游还有个 `benchmark/`，是维护者自己的回归测试，按你的要求没装。）

## 环境适配说明（一组已验证的参考配置）

- `agent-browser` 0.38.1：`~/.local/bin/agent-browser`（npm 全局装的，加 PATH 即可用）。
- Python 工具链：在本 skill 目录建一个 `venv/` 并 editable 安装 `ui_clone`
  （`venv/bin/python -m ui_clone.pipeline <url> <component> <session> status` 可跑）。
- `ffmpeg`：系统自带 `/usr/bin/ffmpeg`。
- `dssim` / ImageMagick：没装（dssim 要 cargo 编译，太重，先跳过）；像素对比先用 Playwright
  截图 + Python PIL/numpy（venv 里有 scikit-image）顶上，真需要再装。
- 上游流程默认用 `agent-browser` 做浏览器抓取；也可以用自己环境里已有的 Playwright
 （Firefox/Chromium）代替，方法论（抓什么证据、
  按什么顺序、门禁是什么）照 SKILL.md 走，只换执行工具。
- 像素对比：需要 `dssim` / ImageMagick 时再按需装；简单对比先用 Playwright 截图 + 肉眼/脚本 diff。

## 快速开始

用户给一个 URL（或指定某个区块）→ 读 `skills/ui-reverse-engineering/SKILL.md` →
按它的"First action"建 `tmp/ref/<component>/` 工作区 → 抓取 → 解码 →
生成 → 验证（pipeline verify PASS 才算完，build 通过不算完）。

## Operating Rules

1. 输入必须是线上可访问的 URL；拿不到 URL 先问用户要，不要猜。
2. 复刻的是公开页面的 DOM/CSS/动效参数（用户可见的公开信息），不要执行下载下来的 JS bundle，
   不要把抓到的任何 credential/密钥写进产物。
3. 动效参数从 CSS 和 JS bundle 里**量**出来（easing、duration、trigger 时机），不要凭截图猜。
4. 完成标准看各 SKILL.md 里的 completion criteria；没过 verify 不许说"做完了"。
## Available connectors

Use `muse.connector_search` to find the current connector docs before following
recovered instructions.
