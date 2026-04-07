#!/usr/bin/env python3
"""Post sticky notes to a Mural board.

Reads a JSON array of stickies from stdin and POSTs each one to the Mural
public REST API. Each sticky must have `text`, `color`, `x`, `y`; `width` and
`height` are optional and default to 200.

Env vars:
    MURAL_TOKEN  — Mural personal access token
    MURAL_ID     — target mural board ID
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
import urllib.error

API = "https://app.mural.co/api/public/v1"


def post_sticky(mural_id: str, token: str, sticky: dict) -> dict:
    body = {
        "text": sticky["text"],
        "x": sticky["x"],
        "y": sticky["y"],
        "width": sticky.get("width", 200),
        "height": sticky.get("height", 200),
        "shape": sticky.get("shape", "rectangle"),
        "style": {
            "backgroundColor": sticky["color"],
            "fontSize": 14,
            "textAlign": "center",
        },
    }
    req = urllib.request.Request(
        f"{API}/murals/{mural_id}/widgets/sticky-note",
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode() or "{}")


def main() -> int:
    token = os.environ.get("MURAL_TOKEN")
    mural_id = os.environ.get("MURAL_ID")
    if not token or not mural_id:
        print("MURAL_TOKEN and MURAL_ID must be set", file=sys.stderr)
        return 2

    try:
        stickies = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"Invalid JSON on stdin: {e}", file=sys.stderr)
        return 2

    if not isinstance(stickies, list):
        print("Expected a JSON array of stickies", file=sys.stderr)
        return 2

    created = 0
    for i, sticky in enumerate(stickies):
        try:
            result = post_sticky(mural_id, token, sticky)
            value = result.get("value", result)
            print(f"{i}: {value.get('id', '?')}  {sticky.get('text', '')[:60]}")
            created += 1
        except urllib.error.HTTPError as e:
            print(f"{i}: HTTP {e.code} {e.read().decode()}", file=sys.stderr)
            return 1
        except Exception as e:  # noqa: BLE001
            print(f"{i}: {e}", file=sys.stderr)
            return 1

    print(f"Created {created}/{len(stickies)} stickies", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
