# maps to murals

A Claude Code skill for posting sticky notes to a [Mural](https://www.mural.co/)
board to support typical product manager mapping processes — event storming,
user story mapping, opportunity solution trees, retros, and similar workshop
artefacts.

The skill lives in [`.claude/skills/mural-post/`](./.claude/skills/mural-post)
and wraps the Mural public REST API via a small Python script.

## What it does

Ask Claude to put something on a Mural board and the `mural-post` skill will
materialise it as stickies — using the standard event-storming colour
conventions where relevant (orange domain events, blue commands, yellow
aggregates, purple policies, red hotspots, …).

## Setup

Set two environment variables before using the skill:

```
MURAL_TOKEN=    # personal access token from the Mural developer portal
MURAL_ID=       # target mural board id (from the board URL)
```

## Usage

In a Claude Code session, just ask — for example:

> Run an event storm for the checkout flow and post it to Mural.

> Put these retro items on the board as stickies.

Claude will invoke the `mural-post` skill, which calls
`.claude/skills/mural-post/scripts/post_stickies.py` with a JSON array of
stickies and POSTs each one to Mural.

See [`.claude/skills/mural-post/SKILL.md`](./.claude/skills/mural-post/SKILL.md)
for the full sticky schema and colour conventions.
