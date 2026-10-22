# Long-form Workflow

X long posts (tutorials, deep dives). The account has X Premium so long posts are available.

## The workflow (fixed order — do not shortcut)

1. **Assistant writes the first draft.** From the user's real materials: screenshots, steps they actually did, numbers they measured. Write it in the account's voice (`voice-en.md`).
2. **User reviews the draft.** They correct facts, cut fluff, add missing details.
3. **Polish with Gemini/Antigravity** (`agy` CLI) — polish only, using the reviewed draft as the base. **Never let the AI write a long post from a template from scratch** — templates invent persona stories, fabricated history, and fake credentials. This was a hard-learned rule.
4. **Images**: header image 1200×675 rendered from HTML/CSS (a diagram of the tech flow — one glance at the article should explain the architecture). Body images: real screenshots, placed where referenced. No stock photos.
5. **Fact pass** before scheduling: every number, date, price, name, and claim re-verified against its source. No absolute safety/security claims — write personal experience as personal experience ("this is what I've seen so far"), not guarantees.
6. **Schedule**: long posts go out a day apart (e.g. Tue 10:00 and Wed 10:00). Don't stack them.

## Structure

- **Title**: experience + content + number hook ("I built X in Y hours — here's the full breakdown"). Designed, not flat — but the angle must stay true to the facts.
- **Opening**: result first — the numbers up top, then why you wrote this.
- **Body**: numbered sections. Each: what to do → where to click → what you'll see → what to avoid.
- **Closer**: punchy line + a hook (a real question for the comments).
- **Length**: 2500–3500 words for tutorials (excluding code blocks and image markers).

## Style rules for long posts

- Practitioner voice throughout: "I did this, here's what happened." Never teacher voice.
- Every step must be actionable: which button, what to type, what appears. Vague steps get cut.
- Cut anything you didn't personally verify. If a detail is uncertain, leave it out rather than guessing.
- Short sentences, colloquial, no AI smell (same banned list as `voice-en.md`).

## Follow-up: short posts that drive traffic to the long post

After a long post goes live, prepare 3 short posts per long post in advance: one ~2 hours after, one ~1 day after, one ~2 days after. Each highlights one angle from the long post and links it. Write them only after you have the real published URL — never use placeholder links.
