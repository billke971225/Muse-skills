

# Jev decisions

Jev is TypeSafe's decision model. It never writes prose: you send a state plus
typed questions, it returns calibrated answers (choice / noul / score) in
~0.1–0.5 s. This is the local adaptation of the ideas in
`~/workspace/vendor/hermes-jev-skills` and `~/workspace/vendor/typesafe-skills`
(their plugin hooks target Hermes/Claude Code/Codex, which this agent does
not run — the API itself is what is used here).

## Calling it

```bash
python3 <skills-dir>/jev-decision/jev_client.py ask \
  --state '<the situation as text>' \
  --questions '{"pick": {"type": "choice", "instructions": "Which skill fits this request?", "criteria": {"gmail": "email work", "calendar": "scheduling", "none": "no skill needed"}}}'
```

The key lives in `~/.config/jev/api_key` (0600 file, never echoed). No key →
`{"status": "fail_open"}`: proceed with your own judgment, never block.

## When to ask Jev

- **Skill selection**: an ambiguous request where 2+ skills could fit. State =
  the request, one `choice` question over skill names + `none`.
- **Triage**: is this message urgent / what kind is it / does a person need to
  see it. One `choice` + one `noul`.
- **Escalation check**: `noul` — "should I ask the user before acting?"
- **Rerank**: which of N retrieved candidates actually answers the question.

## Rules

- One narrow judgment per question; ask independent questions together.
- Redact before sending: the client masks emails, phones, and tokens. Never
  send secrets, credentials, or anything from `private` contexts — use
  fail-open instead.
- Jev advises; it never decides to act. Destructive / irreversible actions
  still need the user's own go-ahead.
- Treat `fail_open` as "Jev unavailable" and carry on normally.
- Never print, log, or paste the API key. Key management: user registers at
  console.typesafe.ai; the key file is written once and never read back
  into chat.

## API reference

- Endpoint: `POST https://api.typesafe.ai/v1/systemone`
- Auth: `Authorization: Bearer <key>`; model `"jev-latest"`
- Docs: https://docs.typesafe.ai/api.md (live source of truth)
## Available connectors

Use `muse.connector_search` to find the current connector docs before following
recovered instructions.
