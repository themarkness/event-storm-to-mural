"""
BaseAgent: runs an LLM with access to the Mural MCP server tools.

The MCP server is started once as a stdio subprocess (McpClient).
Each agent call delegates the tool-use loop to the configured provider
(Gemini by default, Anthropic if MODEL_PROVIDER=anthropic).
"""

from __future__ import annotations

import json
import subprocess
import threading
from typing import Any

from src.config import MCP_SERVER_PATH, model_provider, mural_token
from src.providers import Provider, make_provider


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


class BaseAgent:
    """
    Wraps an LLM provider call with a system prompt and Mural MCP tools.
    Subclasses set `system_prompt` and `role_name`.

    The active provider is selected by the MODEL_PROVIDER env var:
      gemini     (default) — free tier via Google AI Studio
      anthropic            — Anthropic API
    """

    role_name: str = "Agent"
    system_prompt: str = "You are a helpful assistant."

    def __init__(self, mcp: McpClient, provider: Provider | None = None) -> None:
        self._mcp = mcp
        self._provider: Provider = provider or make_provider(model_provider())

    def run(self, user_message: str) -> str:
        """Run the agent, handling the tool-use loop. Returns final text reply."""
        return self._provider.run_conversation(
            system=self.system_prompt,
            user_message=user_message,
            tools=self._mcp.list_tools(),
            tool_executor=self._mcp.call_tool,
            role_name=self.role_name,
        )
