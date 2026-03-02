"""
LLM provider abstraction.

Each provider implements run_conversation(system, user_message, tools, tool_executor)
and handles its own tool-use loop. BaseAgent calls whichever provider is configured.

Supported providers:
  gemini    — Google Gemini via google-genai SDK (default, free tier available)
  anthropic — Anthropic Claude via anthropic SDK
"""

from __future__ import annotations

import json
from typing import Any, Callable, Protocol


ToolExecutor = Callable[[str, dict[str, Any]], str]
McpTool = dict[str, Any]  # as returned by McpClient.list_tools()


class Provider(Protocol):
    def run_conversation(
        self,
        system: str,
        user_message: str,
        tools: list[McpTool],
        tool_executor: ToolExecutor,
        role_name: str = "Agent",
    ) -> str: ...


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------

GEMINI_MODEL = "gemini-2.0-flash"


class GeminiProvider:
    def __init__(self, api_key: str) -> None:
        from google import genai  # type: ignore[import-untyped]
        self._client = genai.Client(api_key=api_key)

    def run_conversation(
        self,
        system: str,
        user_message: str,
        tools: list[McpTool],
        tool_executor: ToolExecutor,
        role_name: str = "Agent",
    ) -> str:
        from google import genai  # type: ignore[import-untyped]
        from google.genai import types  # type: ignore[import-untyped]

        gemini_tools = _mcp_tools_as_gemini(tools)

        # Gemini takes contents as a list; we build it up as the conversation grows
        contents: list[Any] = [types.Content(role="user", parts=[types.Part(text=user_message)])]

        print(f"[{role_name}] thinking...")

        while True:
            response = self._client.models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    tools=gemini_tools,
                ),
            )

            candidate = response.candidates[0]
            model_parts = candidate.content.parts

            # Append model turn to history
            contents.append(types.Content(role="model", parts=model_parts))

            # Check for tool calls
            function_calls = [p for p in model_parts if hasattr(p, "function_call") and p.function_call.name]

            if not function_calls:
                # No tool calls — extract text and return
                for part in model_parts:
                    if hasattr(part, "text") and part.text:
                        return part.text
                return ""

            # Execute each tool call and collect responses
            response_parts = []
            for part in function_calls:
                fc = part.function_call
                args = dict(fc.args) if fc.args else {}
                print(f"[{role_name}] calling {fc.name}({json.dumps(args)[:120]}...)")
                result_text = tool_executor(fc.name, args)
                print(f"[{role_name}] → {result_text[:120]}")
                response_parts.append(
                    types.Part(
                        function_response=types.FunctionResponse(
                            name=fc.name,
                            response={"result": result_text},
                        )
                    )
                )

            contents.append(types.Content(role="user", parts=response_parts))


def _mcp_tools_as_gemini(mcp_tools: list[McpTool]) -> list[Any]:
    """Convert MCP tool descriptors to Gemini Tool objects."""
    from google.genai import types  # type: ignore[import-untyped]

    declarations = []
    for t in mcp_tools:
        schema = t.get("inputSchema", {})
        declarations.append(
            types.FunctionDeclaration(
                name=t["name"],
                description=t.get("description", ""),
                parameters=schema,
            )
        )
    return [types.Tool(function_declarations=declarations)]


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------

ANTHROPIC_MODEL = "claude-sonnet-4-6"
ANTHROPIC_MAX_TOKENS = 4096


class AnthropicProvider:
    def __init__(self, api_key: str) -> None:
        import anthropic  # type: ignore[import-untyped]
        self._client = anthropic.Anthropic(api_key=api_key)

    def run_conversation(
        self,
        system: str,
        user_message: str,
        tools: list[McpTool],
        tool_executor: ToolExecutor,
        role_name: str = "Agent",
    ) -> str:
        import anthropic  # type: ignore[import-untyped]

        anthropic_tools = _mcp_tools_as_anthropic(tools)
        messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]

        print(f"[{role_name}] thinking...")

        while True:
            response = self._client.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=ANTHROPIC_MAX_TOKENS,
                system=system,
                tools=anthropic_tools,  # type: ignore[arg-type]
                messages=messages,       # type: ignore[arg-type]
            )

            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                for block in response.content:
                    if hasattr(block, "text"):
                        return block.text
                return ""

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        print(f"[{role_name}] calling {block.name}({json.dumps(block.input)[:120]}...)")
                        result_text = tool_executor(block.name, block.input)
                        print(f"[{role_name}] → {result_text[:120]}")
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result_text,
                            }
                        )
                messages.append({"role": "user", "content": tool_results})
                continue

            for block in response.content:
                if hasattr(block, "text"):
                    return block.text
            return ""


def _mcp_tools_as_anthropic(mcp_tools: list[McpTool]) -> list[dict[str, Any]]:
    return [
        {
            "name": t["name"],
            "description": t.get("description", ""),
            "input_schema": t.get("inputSchema", {"type": "object", "properties": {}}),
        }
        for t in mcp_tools
    ]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def make_provider(provider_name: str) -> Provider:
    """Create a provider from its name. Reads API keys from config."""
    from src.config import anthropic_api_key, gemini_api_key

    if provider_name == "gemini":
        return GeminiProvider(api_key=gemini_api_key())
    if provider_name == "anthropic":
        return AnthropicProvider(api_key=anthropic_api_key())
    raise ValueError(
        f"Unknown MODEL_PROVIDER {provider_name!r}. "
        f"Valid options: 'gemini', 'anthropic'."
    )
