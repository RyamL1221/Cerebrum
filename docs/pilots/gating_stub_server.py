"""Minimal SIMULATED AIOS kernel — stdlib HTTP stub for the gating pilot.

This is NOT the real AIOS kernel. It is a clearly-labeled simulated server that
implements just enough of the kernel's HTTP surface to exercise the harness's
kernel_shared_tuned path end-to-end over REAL HTTP transport (not in-process
mocking):

  GET  /memory/gating_status   -> mirrors AIOS runtime/launch.py:915 exactly
                                   (200 with the three provenance fields, or a
                                   400 "Memory manager not initialized").
  POST /query                  -> minimal llm_chat response so AssistantAgent.run
                                   produces a result and trials complete.
  POST /memory/report_reward   -> accepts the fire-and-forget reward POST.

The gating response is configurable via env vars so the same stub can serve the
matching state for any tier:
  STUB_ADAPTIVE_ENABLED   ("true"/"false", default "false")
  STUB_STATIC_ENABLED     ("true"/"false", default "false")
  STUB_STATIC_CONFIG_JSON (JSON object, default "{}")
  STUB_UNINITIALIZED      ("true" -> always return the 400 path)

Usage:
  STUB_STATIC_ENABLED=true STUB_STATIC_CONFIG_JSON='{"relevance_threshold":0.3}' \
      python3 docs/pilots/gating_stub_server.py --port 8000
"""

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def _envbool(name: str, default: bool) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes")


class StubHandler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        if self.path == "/memory/gating_status":
            # Mirror AIOS runtime/launch.py:get_memory_gating_status exactly.
            if _envbool("STUB_UNINITIALIZED", False):
                self._send_json(400, {"detail": "Memory manager not initialized"})
                return
            self._send_json(200, {
                "adaptive_policy_enabled": _envbool("STUB_ADAPTIVE_ENABLED", False),
                "static_thresholds_enabled": _envbool("STUB_STATIC_ENABLED", False),
                "static_thresholds_config": json.loads(
                    os.environ.get("STUB_STATIC_CONFIG_JSON", "{}")
                ),
            })
            return
        self._send_json(404, {"detail": f"not found: {self.path}"})

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw or b"{}")
        except ValueError:
            body = {}

        if self.path == "/query":
            self._handle_query(body)
            return
        if self.path == "/memory/report_reward":
            self._send_json(200, {"success": True})
            return
        # Any other POST (e.g. memory ops routed through /query variants) gets
        # a benign OK.
        self._send_json(200, {"response": {}})

    def _handle_query(self, body: dict) -> None:
        """Minimal JSON-LLM stub.

        The SDK reads ``response["response"]["response_message"]``. When the
        caller supplies a ``response_format`` json_schema (as the synthetic-data
        generator and judge do), we synthesize a JSON object satisfying that
        schema by property name and return it as a JSON *string* (the caller
        does ``json.loads`` on it). Otherwise we return a plain prose message
        (the AssistantAgent path). ``token_usage`` is an optional top-level
        sibling of ``response``.
        """
        query_data = body.get("query_data") or {}
        response_format = query_data.get("response_format") or {}
        schema = (
            (response_format.get("json_schema") or {}).get("schema") or {}
        )
        props = schema.get("properties") or {}

        if props:
            message = json.dumps(self._synthesize_from_schema(props))
        else:
            message = (
                "[simulated assistant] Based on your profile and task context, "
                "here is a focused, grounded recommendation."
            )

        self._send_json(200, {
            "response": {
                "response_message": message,
                "tool_calls": None,
                "finished": True,
            },
            "token_usage": {
                "prompt_tokens": 42,
                "completion_tokens": 21,
                "total_tokens": 63,
            },
        })

    # Realistic values keyed by the property names the harness's schemas use.
    _NAMED_VALUES = {
        "user_name": "Jordan Ellis",
        "preferred_tools": ["Visual Studio Code", "Git", "Docker"],
        "preferred_language": "Python",
        "response_style": "detailed",
        "current_project": "AtlasDB — Distributed Query Engine",
        "active_experiment": "Benchmarking join-order optimization on skewed data",
        "goals": ["Cut p99 query latency below 200ms",
                  "Ship the cost-based optimizer"],
        "blockers": ["Flaky integration tests on the sharding layer"],
        "next_steps": ["Add histogram stats to the planner",
                       "Wire the optimizer into the executor"],
        "query": "Given where I am, what should I prioritize next?",
        "actions": ["Prioritize the optimizer", "Stabilize the sharding tests",
                    "Profile the p99 latency path"],
    }

    def _synthesize_from_schema(self, props: dict) -> dict:
        """Build a JSON object satisfying a flat json-schema 'properties' map."""
        out: dict = {}
        for name, spec in props.items():
            if name in self._NAMED_VALUES:
                out[name] = self._NAMED_VALUES[name]
                continue
            # Fallback by declared type
            t = (spec or {}).get("type")
            if t == "array":
                out[name] = ["item-a", "item-b"]
            elif t == "integer":
                out[name] = 3
            elif t == "number":
                out[name] = 3.0
            elif t == "boolean":
                out[name] = True
            else:
                out[name] = f"simulated_{name}"
        return out

    def log_message(self, fmt, *args):  # keep the pilot console readable
        return


def main():
    parser = argparse.ArgumentParser(description="Simulated AIOS gating stub.")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), StubHandler)
    print(f"[stub] SIMULATED AIOS server listening on 127.0.0.1:{args.port}")
    print(f"[stub] gating: adaptive={_envbool('STUB_ADAPTIVE_ENABLED', False)} "
          f"static={_envbool('STUB_STATIC_ENABLED', False)} "
          f"config={os.environ.get('STUB_STATIC_CONFIG_JSON', '{}')} "
          f"uninitialized={_envbool('STUB_UNINITIALIZED', False)}")
    server.serve_forever()


if __name__ == "__main__":
    main()
