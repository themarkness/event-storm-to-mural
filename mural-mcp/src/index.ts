#!/usr/bin/env node
/**
 * Mural MCP Server
 *
 * Exposes two tools:
 *   mural_create_sticky  — create a sticky note on a Mural board
 *   mural_get_stickies   — read all sticky notes from a Mural board
 *
 * Transport: stdio (for use as a subprocess MCP server)
 *
 * Required env vars:
 *   MURAL_TOKEN  — Mural personal access token
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

const MURAL_API = "https://app.mural.co/api/public/v1";

function token(): string {
  const t = process.env.MURAL_TOKEN;
  if (!t) throw new Error("MURAL_TOKEN env var is required");
  return t;
}

async function muralFetch(
  path: string,
  options: RequestInit = {}
): Promise<unknown> {
  const url = `${MURAL_API}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      Authorization: `Bearer ${token()}`,
      ...(options.headers ?? {}),
    },
  });

  const text = await res.text();
  if (!res.ok) {
    throw new Error(`Mural API ${res.status} at ${path}: ${text}`);
  }
  return text ? JSON.parse(text) : null;
}

// ---------------------------------------------------------------------------
// Tool handlers
// ---------------------------------------------------------------------------

async function createSticky(args: {
  mural_id: string;
  text: string;
  color: string;
  x: number;
  y: number;
  width?: number;
  height?: number;
  shape?: string;
}): Promise<unknown> {
  const body = {
    text: args.text,
    x: args.x,
    y: args.y,
    width: args.width ?? 200,
    height: args.height ?? 200,
    shape: args.shape ?? "rectangle",
    style: {
      backgroundColor: args.color,
      fontSize: 14,
      textAlign: "center",
    },
  };

  const result = await muralFetch(
    `/murals/${args.mural_id}/widgets/sticky-note`,
    {
      method: "POST",
      body: JSON.stringify(body),
    }
  );

  // Return a clean summary so agents don't drown in Mural's full response
  const w = (result as { value?: { id?: string; x?: number; y?: number } })
    ?.value ?? result as { id?: string; x?: number; y?: number };
  return { id: w?.id, x: w?.x, y: w?.y, text: args.text, color: args.color };
}

async function getStickies(args: { mural_id: string }): Promise<unknown> {
  const result = await muralFetch(`/murals/${args.mural_id}/widgets`);
  const widgets = (
    result as {
      value?: Array<{ type?: string; id?: string; text?: string; style?: { backgroundColor?: string }; x?: number; y?: number; width?: number; height?: number }>;
    }
  )?.value ?? [];

  // Filter to sticky notes only and return clean fields
  return widgets
    .filter((w) => w.type === "sticky note" || w.type === "stickynote")
    .map((w) => ({
      id: w.id,
      text: w.text ?? "",
      color: w.style?.backgroundColor ?? "",
      x: w.x ?? 0,
      y: w.y ?? 0,
      width: w.width ?? 200,
      height: w.height ?? 200,
    }));
}

// ---------------------------------------------------------------------------
// Server setup
// ---------------------------------------------------------------------------

const server = new Server(
  { name: "mural-mcp", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "mural_create_sticky",
      description:
        "Create a sticky note on a Mural board. Returns the created sticky's id and position.",
      inputSchema: {
        type: "object",
        properties: {
          mural_id: { type: "string", description: "The Mural board ID" },
          text: { type: "string", description: "Text content of the sticky note" },
          color: {
            type: "string",
            description:
              "Background colour as a hex string, e.g. '#FF8C00'. Use event-storming conventions: orange=#FF8C00 (domain event), blue=#1E88E5 (command), yellow=#FFD600 (aggregate), purple=#9C27B0 (policy), green=#43A047 (read model), red=#E53935 (hotspot), lightyellow=#FFF9C4 (actor).",
          },
          x: { type: "number", description: "Horizontal position in pixels" },
          y: { type: "number", description: "Vertical position in pixels" },
          width: { type: "number", description: "Width in pixels (default 200)" },
          height: { type: "number", description: "Height in pixels (default 200)" },
          shape: {
            type: "string",
            enum: ["rectangle", "circle"],
            description: "Shape of the sticky (default rectangle)",
          },
        },
        required: ["mural_id", "text", "color", "x", "y"],
      },
    },
    {
      name: "mural_get_stickies",
      description:
        "Read all sticky notes from a Mural board. Returns id, text, color, x, y for each.",
      inputSchema: {
        type: "object",
        properties: {
          mural_id: { type: "string", description: "The Mural board ID" },
        },
        required: ["mural_id"],
      },
    },
  ],
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    let result: unknown;

    if (name === "mural_create_sticky") {
      result = await createSticky(
        args as Parameters<typeof createSticky>[0]
      );
    } else if (name === "mural_get_stickies") {
      result = await getStickies(args as Parameters<typeof getStickies>[0]);
    } else {
      throw new Error(`Unknown tool: ${name}`);
    }

    return {
      content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
    };
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return {
      content: [{ type: "text", text: `Error: ${message}` }],
      isError: true,
    };
  }
});

// ---------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  // MCP servers must not write to stdout except via the protocol
  process.stderr.write("mural-mcp server started\n");
}

main().catch((err) => {
  process.stderr.write(`Fatal: ${err}\n`);
  process.exit(1);
});
