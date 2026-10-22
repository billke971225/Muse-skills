# Daily Operations SOP

All times in the user's timezone. This is the proven cadence from the Chinese account — adapt slot times to the audience's timezone, keep the structure.

## Slot map

| Time | Job | Output |
|---|---|---|
| 07:37 | Originals batch 1 | 2–3 short posts |
| 08:37 | Replies session 1 (full) | ≥20 replies, ≤24 likes, ≤2 follows |
| 10:37 | AI news scan (AM) | 0–2 quote-posts |
| 11:37 | Originals batch 2 | 2–3 short posts |
| 12:37 | Replies session 2 (full) | ≥20 replies, ≤24 likes |
| 15:37 | Originals batch 3 | 2–3 short posts |
| 16:37 | AI news scan (PM) | 0–2 quote-posts |
| 19:37 | Originals batch 4 (evening) | 2 short posts |
| 21:37 | Replies session 3 (full) | ≥20 replies, ≤24 likes |
| 22:30 | Growth monitor | Daily report |

Daily totals: 8–10 originals, 60+ replies. Max 2 news quotes per scan, prefer zero over forcing one.

## Originals batch (each of the 4)

1. Read `hidden_files/daily_plan_YYYYMMDD.json` — take this batch's topic + mission (breakout/trust). If no plan file, pick per the 6:4 ratio (breakout first; monetization parked).
2. Write 2–3 drafts following `voice-en.md` (70–100 words, 1–2 hashtags at end).
3. **Jev gate**: every draft through `hook_tweet.json`. Publish bar: `verdict=通过`, `confidence>=0.6`, no veto `>=0.5`.
4. Passed → publish queue. Failed → human review console (keep full text + Jev verdict).
5. Mark batch done in the daily plan file.

Never invent facts in a draft. No "test"/"ignore this" ever. Long-form never goes through this flow.

## Replies session (each of the 3, full version)

1. **Canary first**: run the Jev canary. Backend down (non-zero exit / HTTP 403 / timeout) → skip drafting entirely this session, report it, end.
2. **Find targets**: check trending/hot-post sources for the English circle (see `target-accounts-en.md`). Filter: posts from the last few hours, mid-tier accounts (≤50K–100K followers) first — your reply actually gets seen there. AI coding / indie hacker / dev-tool topics first.
3. **Read the full original post** before writing anything. Skip posts already in `seen_replies.json`.
4. Pick ≥20 posts you have a real opinion on.
5. Write replies: 2–3 sentences, real opinion or tested detail, in the original's language. Per `voice-en.md` reply rules.
6. **Jev gate** on every reply.
7. Passed → auto-publish queue (`kind=reply`, id must include the original post's status id, e.g. `xreply-noon-YYYYMMDD-<status_id>` — never just the author handle, collisions cause wrong posts). Failed → human review.
8. **Likes**: like every post you replied to (≤24 total per session). Check `liked.json` first. Never like ads/giveaways/spam/bot accounts.
9. **Follows** (morning session only, ≤2/day): real active blue-check humans only. Check the account: real avatar, original posts, active.
10. **Dedup discipline**: never write to `seen_replies.json`/`liked.json` on queueing. Only append URLs after the publish runner confirms `status=published`. Items not yet published go to `pending_verify.jsonl`; reconcile them at the start of the next session.

If the session's browser work times out mid-way: save the candidate list in `hidden_files/` so a rerun resumes from candidates instead of re-scanning.

## AI news scan (AM + PM)

1. Check the news-source accounts (see `target-accounts-en.md` §4): look at their posts from the last ~12 hours (AM covers overnight, PM covers the day; skip what AM already covered).
2. Filter — all three required: (a) substantive big news (new model/feature, major policy or quota change, big event, important official statement); (b) engagement clearly above the account's normal level; (c) relevant to the AI-tools/coding-agent audience.
3. Max 2 per scan. Nothing qualifies → end silently, no filler.
4. Dedup against `quoted.json` + today's publish log.
5. Write the quote comment in your own voice (`voice-en.md`): **must carry a personal angle** — your real experience with the tool, or what it means for a normal reader. Never just restate the news + a reaction.
6. **Jev gate**, then queue as `kind=quotepost` with the original URL.

## Growth monitor (22:30)

1. Record followers + following (e.g. `163`, `423`); append `{date, followers, following}` to `hidden_files/growth_log.jsonl`; diff vs yesterday.
2. For today's published originals: views / replies / reposts / likes each. For reply posts: likes only.
3. Check mentions/notifications: like back every real user's genuine reply to you (pre-authorized). Skip ads/spam.
4. Report in one short message: follower delta (total), per-post numbers, mentions received + liked back.

## Publish queue runner (every ~10 min, separate job)

1. Fetch the queue. Empty → end silently.
2. For each item, run a real browser task against the logged-in X session:
   - **post**: publish the text verbatim (no rewriting), return the real tweet URL.
   - **reply/quote**: open the original URL first, post the reply under it. Confirm it actually landed as a reply — if the original is 404/gone, mark failed, **never** downgrade to a standalone post.
   - **quotepost**: open original → repost → quote → paste text → publish. Confirm it's a quote post with the original card, return the new URL.
   - **like**: open the post; if already liked, treat as success (idempotent). Otherwise like and confirm.
   - **follow**: open the profile; if already following, success. Otherwise follow and confirm.
3. Safety: skip (mark failed) any item with empty text or containing "test"/"ignore this". Write results back to the queue (`published`/`failed` + URL/error).

## Weekly review (do this every Monday)

- Count breakout vs trust ratio from the week's posts. Off 6:4 → adjust next week's plan.
- Which posts got real replies? Which reply sessions converted to follows? Double down on what worked, cut what didn't.
- Prune dead target accounts (no engagement in 2 weeks), add new ones you found in reply sections.
