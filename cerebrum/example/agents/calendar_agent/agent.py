"""The calendar writer of benchmark v2 (AIOS docs/BENCHMARK_V2.md).

``CalendarAgent`` stores the user's scheduling facts (a team-sync room,
a weekly one-on-one, a conference talk) as ``calendar`` memories, one
row per scripted event, and deletes its own rows of a fact the user
revokes. It runs benchmark v2 sessions only
(``shared_memory_utils.run_v2_session``) and calls no LLM: any other
input fails the writer with a clear reason. Like the profile and task
writers, it makes every kernel memory call through this module's SDK
names, so the harness's create_memory capture and the variants' write
wrapper reach it.
"""
import json
import logging
import os
from typing import Optional

from cerebrum.config.config_manager import config
# Called by these module names, with keyword content= and metadata=.
# update_memory is unused here but present, as in the other writers'
# modules, because the variants' write wrapper (variants/base.py,
# _kernel_write) wraps both create_memory and update_memory.
from cerebrum.memory.apis import (  # noqa: F401
    create_memory,
    delete_memory,
    list_memories,
    update_memory,
)
from cerebrum.example.agents.shared_memory_utils import (
    MEMORY_TYPE_CALENDAR,
    V2_LIST_LIMIT,
    Extraction,
    listed_rows,
    parse_v2_session,
    require_user_id,
    run_v2_session,
)

aios_kernel_url = config.get_kernel_url()

logger = logging.getLogger(__name__)

V2_ONLY = "calendar_agent writes benchmark v2 sessions only"


class CalendarAgent:
    """Writes the user's calendar facts through the kernel memory layer.

    Attributes the deployment (the harness) sets: ``user_id``,
    ``share_memory`` (True: non-private events are shared),
    ``delete_on_revoke`` (True; False is the ``no_delete`` control),
    ``extra_metadata`` (the provenance added to every write) and
    ``llms`` (unused: no LLM call).
    """

    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.config = self.load_config()
        self.messages = []
        self.rounds = 0
        self.token_usage = None
        self.user_id: Optional[str] = None
        self.llms: Optional[list] = None
        self.share_memory = True
        self.delete_on_revoke = True
        self.extra_metadata: dict = {}

    def load_config(self) -> dict:
        """Load agent configuration from config.json in the agent's
        directory."""
        config_file = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "config.json"
        )
        with open(config_file, "r") as f:
            return json.load(f)

    def extract(self, task_input: str) -> Extraction:
        """No extraction: a failed ``Extraction`` naming why. The native
        and replicated calendar writers extract through this class, so a
        non-v2 input fails them with the same reason."""
        return Extraction(MEMORY_TYPE_CALENDAR, problems=[V2_ONLY])

    def run(self, task_input: str) -> dict:
        """Run one benchmark v2 session (``{"v2_session": ...}``); any
        other input stores nothing and returns ``writer_failed`` True."""
        session = parse_v2_session(task_input)
        if session is not None:
            return run_v2_session(
                self, session, MEMORY_TYPE_CALENDAR,
                write=self._v2_create, list_rows=self._v2_list,
                delete=self._v2_delete,
            )
        extraction = self.extract(task_input)
        logger.warning("CalendarAgent: %s", V2_ONLY)
        return {
            "agent_name": self.agent_name,
            "result": f"Writer failed: {V2_ONLY}",
            "rounds": self.rounds,
            "token_usage": None,
            "error": V2_ONLY,
            **extraction.report(),
        }

    def _v2_create(self, content: str, metadata: dict) -> dict:
        return create_memory(
            agent_name=self.agent_name, content=content,
            metadata=metadata, base_url=aios_kernel_url,
        )

    def _v2_list(self, user_id: str) -> dict:
        return list_memories(
            agent_name=self.agent_name, user_id=user_id,
            base_url=aios_kernel_url, k=V2_LIST_LIMIT,
        )

    def _v2_delete(self, user_id: str, memory_id: str) -> dict:
        return delete_memory(
            agent_name=self.agent_name, memory_id=memory_id,
            base_url=aios_kernel_url, user_id=user_id,
        )

    def list_own_rows(self, user_id: Optional[str] = None) -> list:
        """The rows this agent owns for ``user_id`` (default: its
        ``user_id``) as ``{memory_id, content, metadata}``, up to
        ``V2_LIST_LIMIT``, by the call a revoke lists with. Raises
        ``WriterError`` when the listing fails."""
        uid = require_user_id(user_id or self.user_id)
        return listed_rows(self._v2_list(uid))
