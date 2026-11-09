import os
import json
from typing import Optional

from cerebrum.llm.apis import llm_chat
from cerebrum.memory.apis import list_memories
from cerebrum.config.config_manager import config
from cerebrum.example.agents.shared_memory_utils import (
    V2_LIST_LIMIT,
    listed_rows,
    require_user_id,
)

aios_kernel_url = config.get_kernel_url()


class AssistantAgent:
    """A personalized assistant agent that helps users with queries.

    Issues plain llm_chat calls. The kernel handles all memory operations:
    - auto_extract stores conversation turns as memories automatically
    - auto_inject retrieves and injects relevant memories into context

    Benchmark v2 (AIOS docs/BENCHMARK_V2.md) sets ``session``, the
    current session the block's ages count from, and ``probe_id``, the
    probe being answered. Each goes with the request when set
    (``session``, and ``probe_id`` as ``provenance_event``), and the
    kernel stamps both on the conversation turn it stores, as the
    replicated and native assistants stamp their own. Both default to
    None, and the request is then sent as before.
    """

    def __init__(self, agent_name: str, llms: list | None = None):
        self.agent_name = agent_name
        self.config = self.load_config()
        self.messages = []
        self.rounds = 0
        self.llms = llms  # Optional model override, e.g. [{"name": "qwen2.5:7b", "backend": "ollama"}]
        self.session: Optional[int] = None
        self.probe_id: Optional[str] = None

    def load_config(self) -> dict:
        """Load agent configuration from config.json in the agent's directory."""
        script_path = os.path.abspath(__file__)
        script_dir = os.path.dirname(script_path)
        config_file = os.path.join(script_dir, "config.json")

        with open(config_file, "r") as f:
            config = json.load(f)
        return config

    def run(self, task_input: str) -> dict:
        """Process user query and return a result dictionary.

        Args:
            task_input: The user's query string.

        Returns:
            A dict with agent_name, result, and rounds.
        """
        try:
            # Build system instruction from config description
            system_instruction = "".join(self.config.get("description", []))
            self.messages.append({"role": "system", "content": system_instruction})

            # Append user query
            self.messages.append({"role": "user", "content": task_input})

            # The current session and the probe's id (benchmark v2) go
            # with the request only when set, so a request without them
            # is sent as before.
            session = getattr(self, "session", None)
            probe_id = getattr(self, "probe_id", None)
            extra = {}
            if session is not None:
                extra["session"] = session
            if probe_id is not None:
                extra["provenance_event"] = probe_id

            # Call LLM — kernel handles memory injection and extraction
            response = llm_chat(
                agent_name=self.agent_name,
                messages=self.messages,
                base_url=aios_kernel_url,
                llms=self.llms,
                user_id=getattr(self, "user_id", None),
                **extra,
            )

            result_text = response["response"]["response_message"] if response else ""
            self.messages.append({"role": "assistant", "content": result_text})
            self.rounds += 1

            result = {
                "agent_name": self.agent_name,
                "result": result_text,
                "rounds": self.rounds,
            }
            diagnostics = response.get("injection_diagnostics") if response else None
            if diagnostics is not None:
                result["injection_diagnostics"] = diagnostics
            # The kernel's token usage and model-call timing of this call.
            for key in ("token_usage", "llm_timing", "decoding"):
                if response and response.get(key) is not None:
                    result[key] = response[key]
            return result

        except Exception as e:
            return {
                "agent_name": self.agent_name,
                "result": f"Error: {e}",
                "rounds": self.rounds,
            }

    def list_own_rows(self, user_id: Optional[str] = None) -> list:
        """The conversation rows the kernel stored for this agent and
        ``user_id`` (default: its ``user_id``) as ``{memory_id, content,
        metadata}``, through the owner-only listing, up to
        ``V2_LIST_LIMIT``. Raises ``WriterError`` when the listing
        fails."""
        uid = require_user_id(user_id or getattr(self, "user_id", None))
        return listed_rows(list_memories(
            agent_name=self.agent_name, user_id=uid,
            base_url=aios_kernel_url, k=V2_LIST_LIMIT,
        ))
