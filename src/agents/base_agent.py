"""
BaseAgent: runs a Claude model with access to the Mural MCP server tools.

The agent loop:
  1. Send system prompt + user message to Claude
  2. If Claude calls a Mural tool, execute it via the MCP server subprocess
  3. Feed the tool result back, repeat until Claude stops calling tools
  4. Return the final text response
"""

from __future__ import annotations

import json
import subprocess
import threading
from pathlib import Path
from typing import Any

import anthropic

from src.config import MCP_SERVER_PATH, anthropic_api_key, mural_token

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 4096


class McpClient:
    """
    Minimal stdio MCP client.
    Starts the MCP server as a subprocess and communicates via JSON-RPC over stdin/stdout.
    """

    def __init__(self) -> None:
        if not MCP_SERVER_PATH.exists():
            raise FileNotFoundError(
                f"MCP server not built. Run `npm run build` in mural-mcp/. "
                f"Expected: {MCP_SERVER_PATH}"
            )
        env = {"MURAL_TOKEN": mural_token(), "PATH": "/usr/local/bin:/usr/bin:/bin"}
        self._proc = subprocess.Popen(
            ["node", str(MCP_SERVER_PATH)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
            bufsize=1,
        )
        self._id = 0
        self._lock = threading.Lock()
        self._tools: list[dict[str, Any]] | None = None

        # Log server stderr in background so it doesn't block
        threading.Thread(target=self._drain_stderr, daemon=True).start()

        self._initialize()

    def _drain_stderr(self) -> None:
        assert self._proc.stderr
        for line in self._proc.stderr:
            pass  # swallow; set to print(line) for debugging

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def _send(self, method: str, params: dict[str, Any]) -> Any:
        request = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
            "params": params,
        }
        with self._lock:
            assert self._proc.stdin
            self._proc.stdin.write(json.dumps(request) + "\n")
            self._proc.stdin.flush()
            assert self._proc.stdout
            line = self._proc.stdout.readline()

        response = json.loads(line)
        if "error" in response:
            raise RuntimeError(f"MCP error: {response['error']}")
        return response.get("result")

    def _initialize(self) -> None:
        self._send(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "event-storm-to-mural", "version": "1.0.0"},
            },
        )

    def list_tools(self) -> list[dict[str, Any]]:
        if self._tools is None:
            result = self._send("tools/list", {})
            self._tools = result.get("tools", [])
        return self._tools

    def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        result = self._send("tools/call", {"name": name, "arguments": arguments})
        content = result.get("content", [])
        texts = [c["text"] for c in content if c.get("type") == "text"]
        return "\n".join(texts)

    def close(self) -> None:
        self._proc.terminate()


def _mcp_tools_as_anthropic(mcp_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert MCP tool descriptors to the shape Anthropic SDK expects."""
    return [
        {
            "name": t["name"],
            "description": t.get("description", ""),
            "input_schema": t.get("inputSchema", {"type": "object", "properties": {}}),
        }
        for t in mcp_tools
    ]


class BaseAgent:
    """
    Wraps a Claude call with a system prompt and MCP Mural tools.
    Subclasses set `system_prompt` and `role_name`.
    """

    role_name: str = "Agent"
    system_prompt: str = "You are a helpful assistant."

    def __init__(self, mcp: McpClient) -> None:
        self._mcp = mcp
        self._client = anthropic.Anthropic(api_key=anthropic_api_key())

    def run(self, user_message: str) -> str:
        """
        Run the agent on a user message. Handles the tool-use loop automatically.
        Returns the final text reply from the model.
        """
        tools = _mcp_tools_as_anthropic(self._mcp.list_tools())
        messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]

        print(f"[{self.role_name}] thinking...")

        while True:
            response = self._client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=self.system_prompt,
                tools=tools,  # type: ignore[arg-type]
                messages=messages,  # type: ignore[arg-type]
            )

            # Accumulate assistant response
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                # Extract final text
                for block in response.content:
                    if hasattr(block, "text"):
                        return block.text
                return ""

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        print(f"[{self.role_name}] calling {block.name}({json.dumps(block.input)[:120]}...)")
                        result_text = self._mcp.call_tool(block.name, block.input)
                        print(f"[{self.role_name}] → {result_text[:120]}")
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result_text,
                            }
                        )

                messages.append({"role": "user", "content": tool_results})
                continue

            # Unexpected stop reason — return whatever text we have
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text
            return ""
