# Event Storm to Mural — Implementation Plan

## Goal
Multiple AI agents with domain roles collaboratively event storm a process from
input docs. Every agent can read and respond to every other agent's stickies.
Output is a left-to-right timeline on a Mural board via a purpose-built MCP server.

---

## Event Storming Elements

Standard colour conventions. Each agent *owns* their type but all others *review* it.

| Element       | Colour       | Hex       | Owner             | y-offset from spine |
|---------------|--------------|-----------|-------------------|----------------------|
| Actors        | Light yellow | `#FFF9C4` | Product Manager   | -250                 |
| Read Models   | Green        | `#C8E6C9` | Business Analyst  | -150                 |
| Commands      | Blue         | `#1E88E5` | Product Manager   | -150 (right of RM)   |
| Aggregates    | Yellow       | `#FFD600` | Technical Lead    | 0 (between cmd/evt)  |
| Domain Events | Orange       | `#FF8C00` | Document Analyst  | 0 (spine, x=time)    |
| Policies      | Purple       | `#9C27B0` | Business Analyst  | +150                 |
| Hotspots      | Red          | `#E53935` | Customer Support  | +250                 |

Timeline layout (no swim lanes — stickies float on a shared canvas):

```
y=-250  [Actor]──────────────────────────────────────────────
y=-150  [Read Model][Command]────────────────────────────────
y=0     ──────────[Aggregate]──[Event]──[Aggregate]──[Event]─  ← time axis
y=+150  ─────────────────────[Policy]────────────────────────
y=+250  ─────────────────────[Hotspot]───────────────────────
                              x increases →
```

Commands, aggregates, read models, actors, policies and hotspots are x-anchored
to the event they relate to. The orchestrator calculates all positions.

---

## Collaboration Model

Two phases per run:

### Phase 1 — Diverge (each agent reads the input)
Agents run sequentially. Each agent reads the source docs and posts their
specialist stickies. They cannot yet see what others posted.

Order: DocumentAnalyst → ProductManager → TechnicalLead → BusinessAnalyst →
       CustomerSupport

### Phase 2 — Converge (each agent reads the full board)
Each agent gets the full list of current stickies via `mural_get_stickies` and
is prompted to respond as a reviewer:
- **Confirm** — add a small ✓ sticky (same colour, 40×40) above the target
- **Challenge** — add a small red ? sticky with a brief reason above the target
- **Add** — post additional stickies they missed in Phase 1

This means the PM reviews the tech lead's aggregates, the BA reviews the PM's
commands, the customer support reviews everyone's events, etc.

Reviewing agent order mirrors Phase 1 but each agent sees all Phase 1 output.

---

## Mural MCP Server

`cogell/mural-mcp` only exposes workspace read tools — not suitable.
We build our own minimal MCP server upfront in `mural-mcp/`.

**Why MCP rather than direct REST calls:**
- Agents can call Mural tools natively as Claude tool-use — they decide *what*
  and *where* to post, not just return JSON for the orchestrator to interpret
- The MCP server is a reusable standalone artefact for other projects
- Reads are as important as writes: agents call `mural_get_stickies` themselves
  during Phase 2 without the orchestrator having to mediate

**Tools exposed by `mural-mcp`:**

```
mural_create_sticky(mural_id, text, color, x, y, width?, height?, shape?)
  → { id, x, y, text, color }

mural_get_stickies(mural_id)
  → [{ id, text, color, x, y, width, height }]

mural_create_area(mural_id, title, x, y, width, height)   ← added in Slice 3
  → { id }
```

The MCP server is a small TypeScript/Node.js process. The Python orchestrator
spawns it as a stdio MCP subprocess and passes the tools to each Claude call.

---

## Lean Slicing Strategy

### Slice 1 — Walking skeleton: one agent, one sticky

```
sample.txt → DocumentAnalyst (Claude + mural MCP tools) → mural_create_sticky → board
```

Agents call Mural tools directly via Claude tool-use. No JSON parsing in Python.

Files:
```
mural-mcp/
├── package.json
├── tsconfig.json
└── src/index.ts          # MCP server: mural_create_sticky + mural_get_stickies

src/
├── main.py               # CLI: --input --mural-id
├── config.py             # env vars
├── agents/
│   ├── base_agent.py     # runs Claude with MCP tools, handles tool-use loop
│   └── document_analyst.py  # system prompt + role definition
└── pipeline.py           # Phase 1 runner (one agent for now)

.env.example
pyproject.toml
examples/sample.txt       # realistic order-processing process description
```

Acceptance: `python -m src.main --input examples/sample.txt --mural-id <id>`
posts at least one orange domain event sticky to the board.

---

### Slice 2 — All five agents, Phase 1 complete

Add the remaining four agents. Each reads the same input, calls Mural tools,
posts their stickies at correct y-offsets.

Files added:
- `src/agents/product_manager.py`
- `src/agents/technical_lead.py`
- `src/agents/business_analyst.py`
- `src/agents/customer_support.py`
- `src/layout.py` — x/y position calculator (assigns x by temporal order, y by type)

The orchestrator collects agent outputs and calls `layout.assign_positions(stickies)`
before posting, so stickies don't pile on top of each other.

---

### Slice 3 — Phase 2: collaborative review

Add the review loop. After all Phase 1 stickies are posted, each agent:
1. Calls `mural_get_stickies` to see the current board
2. Is prompted with their reviewer persona
3. Posts confirm/challenge/addition stickies near the originals

Files added:
- `src/agents/reviewer_mixin.py` — shared review prompt + response schema
- `mural-mcp/src/index.ts` updated — `mural_create_area` added (optional, for later)
- `src/pipeline.py` updated — Phase 2 loop

Confirm stickies are the same colour as the original at 50% opacity approximated
by a lighter hex. Challenge stickies are red `#E53935` with a "?" prefix.

---

### Slice 4 — Facilitator synthesis

A Facilitator agent runs after Phase 2. It reads the full board, identifies
clusters of hotspots/challenges, and posts:
- A white summary sticky at the start of the board
- Pink `#FCE4EC` "unresolved" stickies for items with >1 challenge and no confirm

Files added:
- `src/agents/facilitator.py`
- `src/pipeline.py` updated — Phase 3 (synthesis)

---

### Slice 5 — Multiple input formats

Files added:
- `src/inputs/loader.py` — dispatch by extension
- `src/inputs/pdf_adapter.py` — PDF → plain text (pypdf)
- `src/inputs/json_adapter.py` — support ticket JSON → plain text
- `src/inputs/md_adapter.py` — strips markdown to clean prose

---

## Repository Structure (full)

```
event-storm-to-mural/
├── mural-mcp/
│   ├── package.json
│   ├── tsconfig.json
│   └── src/
│       └── index.ts        # MCP server (TypeScript, stdio transport)
├── src/
│   ├── main.py
│   ├── config.py
│   ├── pipeline.py
│   ├── layout.py
│   ├── agents/
│   │   ├── base_agent.py
│   │   ├── reviewer_mixin.py
│   │   ├── document_analyst.py
│   │   ├── product_manager.py
│   │   ├── technical_lead.py
│   │   ├── business_analyst.py
│   │   ├── customer_support.py
│   │   └── facilitator.py
│   └── inputs/
│       ├── loader.py
│       ├── pdf_adapter.py
│       ├── json_adapter.py
│       └── md_adapter.py
├── examples/
│   └── sample.txt
├── .env.example
├── pyproject.toml
└── PLAN.md
```

---

## Tech Stack

| Layer         | Choice                                  | Why                                      |
|---------------|-----------------------------------------|------------------------------------------|
| Agents        | Python + `anthropic` SDK                | Clean tool-use loop, async support       |
| Model         | `claude-sonnet-4-6`                     | Strong structured output, fast enough    |
| MCP server    | TypeScript + `@modelcontextprotocol/sdk`| Standard MCP tooling, same as ecosystem  |
| Mural API     | Called inside MCP server via `fetch`    | Keeps REST knowledge in one place        |
| Validation    | `pydantic` (Python side)                | Agent output schemas                     |
| Package mgmt  | `uv` (Python), `npm` (MCP server)       | Fast, modern                             |

---

## Environment Variables

```
ANTHROPIC_API_KEY=
MURAL_TOKEN=           # personal access token from Mural developer portal
MURAL_ID=              # target mural board ID
```

No OAuth flow needed for single-user CLI. Mural personal access token is sufficient.

---

## Slice 1 — Immediate build checklist

1. `mural-mcp/` — minimal MCP server with `mural_create_sticky` and `mural_get_stickies`
2. `pyproject.toml` with `anthropic`, `httpx`, `pydantic`, `python-dotenv`
3. `src/config.py`
4. `src/agents/base_agent.py` — spawns MCP server, runs Claude tool-use loop
5. `src/agents/document_analyst.py` — system prompt focused on domain events
6. `src/main.py` — load file, run agent, done
7. `examples/sample.txt` — realistic order-processing process narrative
8. Commit + push
