

# X Growth Playbook

Run one X account like a real person who ships. Everything here was proven on a Chinese account (@Ke971225Bill, "木木") that grew with this exact system — this skill adapts it for an English-language account.

## The one insight that matters

**The growth engine is replies, not posts.** Measured evidence (2026-10-03): 13 substantive replies → 18 likes → 13 mentions → +38 followers. For accounts under ~1000 followers, ~80% of effort goes into other people's reply sections. Posts build credibility; replies build the audience.

## 1. Account setup

See `references/account-setup.md`. In short:

- **Avatar**: real person's photo, clear face, casual. No AI-generated faces.
- **Bio**: identity + value + hook, under 160 chars. Template in the reference.
- **Pinned tweet**: best long-form post, or a "who I am + what I post" intro.
- **Blue check**: worth it — Blue replies rank higher and get seen.

## 2. Voice (non-negotiable)

See `references/voice-en.md` for the full English voice guide. The core rules:

- **First-reaction body**: lead with your gut reaction, not commentary. Structure: event in one line → "so what does this mean for me / what do I do" → land on an action, opportunity, or concrete question.
- **Sound like a person, not a press release.** Never: "excited to announce", "we believe", "game-changer", "delve", "furthermore", "it's important to note".
- **Only say what you actually tested.** Real numbers, specific details. Never invent dates, stats, prices, or names.
- **End short posts with a hook**: a concrete question, a pick-a-side, or a deliberately half-finished take. Never end with a flat statement.

## 3. Daily cadence

See `references/daily-ops.md` for the full SOP. The skeleton:

| Slot (user TZ) | Job | Volume |
|---|---|---|
| 07:37 | Originals batch 1 | 2–3 short posts |
| 08:37 | Replies session 1 | ≥20 substantive replies |
| 10:37 | AI news scan | Quote-post only if real big news |
| 11:37 | Originals batch 2 | 2–3 short posts |
| 12:37 | Replies session 2 | ≥20 substantive replies |
| 15:37 | Originals batch 3 | 2–3 short posts |
| 16:37 | AI news scan | Quote-post only if real big news |
| 19:37 | Originals batch 4 (evening) | 2 short posts |
| 21:37 | Replies session 3 | ≥20 substantive replies |
| 22:30 | Growth monitor | Followers, post stats, mention likes |

Totals per day: 8–10 originals, 60+ replies, max 2 news quotes. Never force a post to fill a slot.

## 4. Quality gate (Jev)

Every draft — original, reply, or quote — passes Jev before publishing:

```bash
echo '{"tweet_text":"<DRAFT>","has_image":false}' > /tmp/jev_state.json
python3 ~/workspace/skills/typesafe/bin/jev_judge.py \
  --state /tmp/jev_state.json \
  --questions ~/workspace/skills/typesafe/references/hooks/hook_tweet.json
```

**Publish bar**: `verdict=通过` AND `confidence>=0.6` AND no veto `>=0.5`.

**Open every batch with a canary** (backend may be down):

```bash
echo '{"tweet_text":"canary"}' > /tmp/jev_canary.json
timeout 60 python3 ~/workspace/skills/typesafe/bin/jev_judge.py \
  --state /tmp/jev_canary.json \
  --questions ~/workspace/skills/typesafe/references/hooks/hook_tweet.json
```

Non-zero exit, HTTP 403, or timeout → Jev backend is down: skip drafting entirely that session, report it, do not queue anything. The gate is fail-closed.

## 5. Routing rules (who can auto-publish)

- **Replies**: Jev-passed → auto-publish (user pre-authorized). Failed → human review console.
- **Originals**: Jev-passed → auto-publish queue (user pre-authorized); user may also require manual approval for originals — ask once, then follow it.
- **Likes**: auto-execute (pre-authorized). Only like real content, never ads/giveaways/spam.
- **Follows**: auto-execute within daily cap (≤2/day, real active blue-check humans first).
- **Quote-posts**: Jev-passed → auto-publish; failed → human review.
- Never publish anything containing "test" / "ignore this". Never downgrade a failed reply/quote to a standalone post.

## 6. Content missions (6:4)

Every post has a mission. Ratio: ~60% **breakout** (broad-reach topics that get you discovered), ~40% **trust** (professional depth that makes you worth following). Monetization content is parked until the account has real traction.

Breakout topics (English circle edition): AI tool hot takes, coding-agent workflows, indie-hacker revenue/build-in-public, dev-tool discoveries, counter-intuitive takes, ask-the-audience questions, real screenshots with numbers.

## 7. Reply craft (the actual growth lever)

- Read the full original post before replying. Never reply blind.
- 2–3 sentences, with a real opinion or tested detail. No "Great post!", no "Thanks for sharing!", no one-liners.
- Reply in the language of the original post.
- Prefer mid-tier accounts (≤50K–100K followers): your reply actually gets seen.
- Like every post you replied to (≤24 likes/session).

## 8. Long-form

See `references/longform.md`. Key rules:

- **Assistant writes the first draft**, user reviews, then polish with Gemini/Antigravity. Never let an AI write it from a template from scratch (templates invent persona stories).
- Structure: result first (numbers up top) → numbered points → colloquial explanation per point → punchy closer → hook.
- One header image (1200×675, HTML/CSS-rendered diagram of the tech flow). Schedule long-forms a day apart.

## 9. Target accounts

See `references/target-accounts-en.md` for the English-circle list: AI coding people (@simonw, @bcherny, @amasad, @rauchg, @swyx, @trq212), indie hackers (@levelsio, @marclou, @tdinh_me, @dvassallo, @dannypostmaa), and who to avoid (mega-accounts where replies drown, pure repost bots, giveaway accounts).

## 10. Ops infrastructure notes

- **Login sessions**: keep X logged in via a clean IP (account-type services always use the clean route). One account can be logged in on multiple browsers/devices simultaneously.
- **Publish pipeline**: drafts go into a VPS publish queue (`/publish` endpoint); a queue runner (every ~10 min) posts them through the logged-in browser. Posting, replying, quote-posting, liking, and following each need a real browser task that confirms the action actually landed (URL returned for posts).
- **Dedup**: track every replied/liked/quoted URL in `seen_replies.json` / `liked.json` / `quoted.json`; check before queueing, only record after confirmed published.
- **Daily plan file**: `hidden_files/daily_plan_YYYYMMDD.json` tracks which batch picked which topic — read before drafting so batches don't repeat.

## Failure modes learned the hard way

- Browser tasks time out mid-session: keep candidates in `hidden_files/` so a rerun resumes instead of restarting.
- Never present an empty search / blocked page as "no content" — record it as unverified.
- Stats discipline: dates, numbers, prices, names all verified from a source, never from memory. Screenshots and real data beat adjectives.
- Do not claim recovery/scheduling you can't verify. A schedule existing is not proof it ran.
## Available connectors

Use `muse.connector_search` to find the current connector docs before following
recovered instructions.
