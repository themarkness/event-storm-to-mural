---
name: mural-post
description: Post sticky notes to a Mural board for typical product manager processes (event storming, user story mapping, opportunity solution trees, retros). Use whenever the user asks to put something on a Mural board, create stickies, or run a PM workshop artefact in Mural.
---

# Mural Post

A minimal skill that posts sticky notes to a Mural board via the Mural public REST API. Use it when the user wants to materialise product-manager workshop output (event storms, story maps, retros, etc.) on a Mural board.

## Required environment

- `MURAL_TOKEN` — Mural personal access token (developer portal → API → personal token)
- `MURAL_ID` — target mural board ID (in URL after `/m/.../`)

If either is missing, ask the user to set them before posting.

## How to post

Use the bundled `post_stickies.py` script. It accepts a JSON array of stickies on stdin and POSTs each one to Mural. Run it via `python3 scripts/post_stickies.py` from this skill directory.

```bash
python3 scripts/post_stickies.py <<'JSON'
[
  {"text": "Order placed", "color": "#FF8C00", "x": 0,   "y": 0},
  {"text": "Payment taken", "color": "#FF8C00", "x": 240, "y": 0}
]
JSON
```

Each sticky object supports: `text`, `color` (hex), `x`, `y`, optional `width`/`height` (default 200).

The script prints the created sticky id per line, or an error and exits non-zero.

## Colour conventions (event storming)

Use these hex colours so the board reads correctly:

| Element       | Hex       |
|---------------|-----------|
| Domain Event  | `#FF8C00` |
| Command       | `#1E88E5` |
| Aggregate     | `#FFD600` |
| Policy        | `#9C27B0` |
| Read Model    | `#C8E6C9` |
| Actor         | `#FFF9C4` |
| Hotspot       | `#E53935` |

For story mapping use yellow `#FFF9C4` for activities, blue `#90CAF9` for tasks, green `#C8E6C9` for releases. For retros: green `#C8E6C9` (went well), red `#E53935` (problems), yellow `#FFF59D` (actions).

## Layout guidance

- Stickies are 200×200 by default. Space them by 240px on x for a row, 240px on y for a column.
- Event-storm timelines: events on `y=0` (the spine), commands at `y=-150`, aggregates at `y=0` aligned x with their event, policies at `y=+150`, hotspots at `y=+250`.
- Story maps: activities top row, tasks below grouped by activity, release rows further down.

## Workflow

1. Confirm `MURAL_TOKEN` and `MURAL_ID` are set.
2. Translate the user's intent into a list of `{text, color, x, y}` stickies, applying the layout guidance above.
3. Pipe the JSON to `scripts/post_stickies.py`.
4. Report which stickies were created and the board URL: `https://app.mural.co/t/<workspace>/m/<workspace>/<mural_id>`.

Keep batches under ~50 stickies per call to stay friendly to Mural rate limits.
