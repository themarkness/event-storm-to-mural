# Event Storm to Mural

Multi-agent event storming that turns input documents into a collaborative
event storm on a [Mural](https://www.mural.co/) board.

Five role-based AI agents (Document Analyst, Product Manager, Technical Lead,
Business Analyst, Customer Support) read your source material, then post and
review each other's stickies on a shared Mural canvas using the standard event
storming colour conventions.

## How it works

1. **Diverge** — each agent reads the input docs and posts their specialist
   stickies (domain events, commands, aggregates, policies, hotspots, …) at the
   correct y-offset from the timeline spine.
2. **Converge** — each agent fetches the full board and reviews everyone
   else's work, adding confirm / challenge / addition stickies.
3. **Synthesise** — a Facilitator agent summarises clusters and flags
   unresolved hotspots.

Stickies are written to Mural via a small purpose-built MCP server in
[`mural-mcp/`](./mural-mcp), which the Python orchestrator spawns as a stdio
subprocess and exposes to Claude as native tool-use.

See [`PLAN.md`](./PLAN.md) for the full design, element colours, layout rules,
and lean delivery slices.

## Repository layout

```
mural-mcp/      TypeScript MCP server (mural_create_sticky, mural_get_stickies)
src/            Python orchestrator and agents
examples/       Sample input documents
PLAN.md         Detailed design and implementation plan
```

## Setup

Requires Python 3.11+, [`uv`](https://github.com/astral-sh/uv), and Node.js
for the MCP server.

```bash
uv sync
(cd mural-mcp && npm install && npm run build)
cp .env.example .env   # then fill in the values
```

Environment variables:

```
ANTHROPIC_API_KEY=
MURAL_TOKEN=     # personal access token from the Mural developer portal
MURAL_ID=        # target mural board id
```

## Usage

```bash
uv run python -m src.main --input examples/sample.txt --mural-id <mural-id>
```

The agents will populate the specified Mural board with a left-to-right event
storm timeline.

## Tech stack

- Python + `anthropic` SDK for the agent loop
- `claude-sonnet-4-6` as the model
- TypeScript + `@modelcontextprotocol/sdk` for the Mural MCP server
- Mural REST API called from inside the MCP server
