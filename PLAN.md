# Event Storm to Mural — Implementation Plan

## Goal
Multi-agent event storming: agents with domain roles read input docs and collaboratively
populate a Mural board with event-storm stickies (domain events, commands, aggregates, policies, hotspots).

## Lean Slicing Strategy

### Slice 1 — One agent, one sticky (walking skeleton)
**Goal:** Prove the full path works end-to-end.

```
input text → Document Analyst agent → Claude API → Mural REST API → orange sticky on board
```

Files:
- `src/main.py` — CLI: `python -m src.main --input examples/sample.txt --mural-id <id>`
- `src/agents/base_agent.py` — calls Claude, returns structured JSON
- `src/agents/document_analyst.py` — extracts domain events from text
- `src/mural/client.py` — thin Mural REST wrapper (create_sticky, create_area, get_widgets)
- `src/config.py` — env vars (MURAL_TOKEN, MURAL_ID, ANTHROPIC_API_KEY)
- `.env.example`, `pyproject.toml`, `examples/sample.txt`

Agent output schema (used by all agents):
```json
{
  "stickies": [
    { "text": "Order Placed", "color": "#FF8C00", "type": "domain_event", "x": 100, "y": 100 }
  ]
}
```

Acceptance: running `python -m src.main` posts one orange sticky to the Mural board.

---

### Slice 2 — Five agents, all event storm colours
Add agents that each read the same input and post their specialist stickies.

Agent roles and sticky colours:
| Agent             | Role                              | Sticky Colour | Type           |
|-------------------|-----------------------------------|---------------|----------------|
| DocumentAnalyst   | Finds domain events               | Orange #FF8C00 | domain_event  |
| ProductManager    | Identifies commands / user intent | Blue   #1E88E5 | command       |
| TechnicalLead     | Spots aggregates / bounded contexts| Yellow #FFD600 | aggregate     |
| BusinessAnalyst   | Defines policies / business rules | Purple #9C27B0 | policy        |
| CustomerSupport   | Flags pain points / hotspots      | Red    #E53935 | hotspot       |

Files added:
- `src/agents/product_manager.py`
- `src/agents/technical_lead.py`
- `src/agents/business_analyst.py`
- `src/agents/customer_support.py`
- `src/pipeline.py` — runs agents sequentially, collects stickies, posts in one batch

Agents run sequentially (not in parallel) so each can optionally read what prior
agents already posted (read-before-write loop).

---

### Slice 3 — Board layout with swim lanes (areas)
Create a structured board with one Mural Area per agent role, stickies placed inside their lane.

```
|  Events  |  Commands  |  Aggregates  |  Policies  |  Hotspots  |
|  (orange) |   (blue)   |   (yellow)   |  (purple)  |   (red)    |
```

Files added:
- `src/mural/layout.py` — calculates x/y positions, creates areas via Mural API

Mural API calls:
- `POST /murals/{id}/widgets/area` — create swim lane areas
- `POST /murals/{id}/widgets/sticky-note` — place stickies inside areas (parentId)

---

### Slice 4 — Agents see each other's output (collaborative loop)
After all agents post, a Facilitator agent reads all stickies back from the board and
writes a narrative summary sticky (white) + identifies missing pieces.

```
get_widgets() → Facilitator prompt → summary sticky + "what's missing?" stickies
```

Files added:
- `src/agents/facilitator.py`
- `src/mural/client.py` updated with `get_stickies(mural_id)`

---

### Slice 5 — Multiple input types
Add input adapters so agents can ingest different formats.

Files added:
- `src/inputs/loader.py` — detects format, returns plain text
- `src/inputs/pdf_adapter.py` — extracts text from PDF
- `src/inputs/json_adapter.py` — flattens JSON/support ticket structure

---

## Architecture Overview

```
src/
├── main.py              # CLI entry point
├── config.py            # env var loading
├── pipeline.py          # orchestrates agents, manages board layout
├── agents/
│   ├── base_agent.py    # BaseAgent: calls Claude, parses structured JSON
│   ├── document_analyst.py
│   ├── product_manager.py
│   ├── technical_lead.py
│   ├── business_analyst.py
│   ├── customer_support.py
│   └── facilitator.py
├── mural/
│   ├── client.py        # Mural REST API wrapper
│   └── layout.py        # board layout / position calculation
└── inputs/
    ├── loader.py
    ├── pdf_adapter.py
    └── json_adapter.py
examples/
└── sample.txt
```

---

## Mural MCP Server Note

The available community MCP server (`cogell/mural-mcp`) only exposes workspace
read tools — it does NOT support creating stickies. So:

- **Slice 1-4**: Use Mural REST API directly (`https://app.mural.co/api/public/v1/`)
- **Slice 5+**: Wrap the REST client as MCP tools so Claude Code itself can call Mural
  natively. This means writing a small `mural-mcp/index.ts` tool server.

---

## Tech Stack

- **Python 3.11+** with `uv` for package management
- **anthropic** SDK — `claude-sonnet-4-6` for all agents
- **httpx** — async HTTP for Mural REST calls
- **pydantic** — agent output validation
- **python-dotenv** — env config

---

## Mural API Auth

Requires a Mural **Bearer token** (personal access token or OAuth).
Set `MURAL_TOKEN=<token>` in `.env`.
No OAuth flow needed for single-user CLI use.

---

## What We Build in Slice 1 (immediate next step)

1. `pyproject.toml` with deps
2. `.env.example`
3. `src/config.py`
4. `src/mural/client.py` — `create_sticky(mural_id, text, color, x, y)`
5. `src/agents/base_agent.py` — `run(prompt, system) -> dict`
6. `src/agents/document_analyst.py` — system prompt + output schema
7. `src/main.py` — glue: load file, call agent, post sticky
8. `examples/sample.txt` — a realistic order-processing support doc
9. Commit + push
