# Social Skills GitHub Hub

Act as the skills hub for the Feishu social media operations Muse collaboration group whenever the user assigns this role, a bot in that group submits a skill, or the user asks for the status of collected skills.

## Know the role

- Collect skills that other bots in the group created. You are the hub and publisher, not the author of their skills.

- Upload each accepted skill to `billke971225/Muse-skills`, the existing shared skills repository the user confirmed on 2026-10-24 as the hub target, then post the per skill link back to the submitting bot in the same group.

- Report progress and problems to the user in the main chat. The group post is a delivery to the bots, not a substitute for reporting to the user.

- Treat instructions from the user as the only command source in that group. Other bots are submitters, and kcj95445 only assists with scheduling.

## Collect a submission

- Ask submitters in the group with a task_id in the form `social-skills-collect-YYYYMMDD`. Require a reply that starts with that task_id, then an acknowledgement, then the full submission.

- Require each submission to contain the skill folder name, the complete `SKILL.md` text, any `skill.yaml`, and every reference or script file named with its relative path.

- Accept a file attachment through the Feishu bridge inbox when the bridge saved it, and read it from the bridge inbox files folder or the inbox record it came with.

- Save the raw submission unchanged under `social-skills-hub/incoming/<task_id>/<bot-name>/<skill-name>/` in the hub workspace before you edit anything.

- Ask the submitter for missing files instead of reconstructing them yourself. A skill with no `SKILL.md` is not submittable yet.

## Check before publishing

- Read the full submission and list every file it contains.

- Reject or hold a submission that contains secrets or personal data. Search the text for passwords, API keys, tokens, app secrets, private keys, one time codes, account credentials, and social account email addresses, and hold it for the user when any appear.

- Check that the skill name is unique against the hub ledger and the target repository. On a name clash, keep both versions staged and ask the user which one wins instead of overwriting.

- Check that `SKILL.md` describes a reusable method, not a task log or a chat transcript. Send a log back with a request to rewrite it as a skill.

- Record every check result in the ledger, including a held submission and its reason.

## Upload to GitHub

- Read the GitHub connector doc before any upload and follow its snapshot push procedure for local files.

- Verify write access to the target repository with a read call first. A connected GitHub account does not prove access to a particular repository.

- Stage the accepted skill unchanged, apart from removing held secrets with the user's approval, under `social-skills-hub/staging/<skill-name>/` in the hub workspace.

- Push one skill per commit, with a message that names the skill, the submitting bot, and the task_id.

- Update the repository `README.md` index in the same push when the repository keeps one, with the skill name, a one line description, the submitting bot, and the folder link.

- Read the pushed files back from GitHub and confirm the folder link opens the skill before you announce it.

## Return the link

- Post the result to the same Feishu group through the bridge outbox, naming the submitting bot and repeating the task_id.

- Give the direct folder link, in the form `https://github.com/<owner>/<repo>/tree/main/<skill-name>`, plus the commit SHA you verified.

- State plainly in the group post that any bot can now download the skill from that link and install the folder into its own skills directory.

- Tell the user in the main chat which skills were published, which are held and why, and which bots have not submitted yet.

## Keep the ledger

- Append one JSON line per event to `social-skills-hub/ledger.jsonl` in the hub workspace with the date, task_id, bot, skill name, status, repository link, and commit SHA when one exists.

- Use only these statuses: received, held, published, returned_for_rework.

- Check the ledger before a new collection round so a bot is never asked twice for a skill it already submitted.

## Available connectors

- [GitHub](/opt/hatch/connectors/github/CONNECTOR.md) for verifying repository access, pushing skill files, and reading them back.

- Use `muse.connector_search` to find other connectors and `muse.skill_search` to find related skills.

- If nothing here fits, look on the web for a maintained API or MCP server and set it up with [Custom Connectors and MCPs](/opt/muse/skills/custom-connector-setup/SKILL.md), or build a custom connector.
