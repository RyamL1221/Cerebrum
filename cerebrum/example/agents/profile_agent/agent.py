import os
import json
import logging

from cerebrum.llm.apis import llm_chat_with_json_output, parse_json_reply
from cerebrum.memory.apis import create_memory, update_memory, search_memories
from cerebrum.config.config_manager import config

from cerebrum.example.agents.shared_memory_utils import (
    Extraction,
    FIELD_STRUCTURED,
    extract_validated,
    structured,
    build_memory_metadata,
    FIELD_SHARING_POLICY,
    MEMORY_TYPE_PROFILE,
    POLICY_PRIVATE,
    POLICY_SHARED,
)

aios_kernel_url = config.get_kernel_url()

logger = logging.getLogger(__name__)


class ProfileAgent:
    """Agent that extracts and stores user profile attributes.

    Analyzes user input to identify stable attributes such as name,
    preferred tools, preferred programming language, and response style.
    Uses llm_chat_with_json_output for structured extraction and
    upserts profile memories via the kernel memory layer.
    """

    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.config = self.load_config()
        self.messages = []
        self.rounds = 0
        # The kernel's token usage of the last extraction call.
        self.token_usage = None

    def load_config(self) -> dict:
        """Load agent configuration from config.json in the agent's directory."""
        script_path = os.path.abspath(__file__)
        script_dir = os.path.dirname(script_path)
        config_file = os.path.join(script_dir, "config.json")

        with open(config_file, "r") as f:
            config = json.load(f)
        return config

    def extract(self, task_input: str) -> Extraction:
        """The validated extraction, after up to ``WRITER_RETRIES``
        retries (``shared_memory_utils.extract_validated``)."""
        return extract_validated(
            MEMORY_TYPE_PROFILE,
            lambda: self._extract_profile(task_input),
            lambda: self.token_usage,
        )

    def run(self, task_input: str) -> dict:
        """Extract, validate, and store the profile from input.

        A writer whose extraction does not validate after its retries
        stores nothing and returns ``writer_failed`` True.

        Args:
            task_input: User input text to extract the profile from.

        Returns:
            Dict with agent_name, result, rounds, the token usage of
            each extraction call, and the extraction report
            (``writer_failed``, ``writer_retries``, ``writer_problems``).
        """
        extraction = None
        try:
            extraction = self.extract(task_input)
            self.rounds += 1
            report = extraction.report()
            if extraction.failed:
                logger.warning(
                    "ProfileAgent: extraction failed after %d retries: %s",
                    extraction.retries, extraction.problems,
                )
                return {
                    "agent_name": self.agent_name,
                    "result": f"Writer failed: {extraction.problems}",
                    "rounds": self.rounds,
                    "token_usage": self.token_usage,
                    **report,
                }

            # Upsert using the explicit request-scoped user_id only
            user_id = getattr(self, 'user_id', None)
            if not user_id or not str(user_id).strip():
                logger.warning(
                    "Skipping memory write: no explicit user_id provided "
                    "to ProfileAgent"
                )
                return {
                    "agent_name": self.agent_name,
                    "result": (
                        "Extracted profile (memory write skipped — no "
                        f"user_id): {extraction.text}"
                    ),
                    "rounds": self.rounds,
                    "token_usage": self.token_usage,
                    **report,
                }
            user_id = str(user_id).strip()
            memory_ids = self._upsert_profile_memory(user_id, extraction)
            return {
                "agent_name": self.agent_name,
                "result": (
                    f"Stored profile for {user_id}: {extraction.text} "
                    f"Memory IDs: {memory_ids}"
                ),
                "rounds": self.rounds,
                "token_usage": self.token_usage,
                **report,
            }

        except Exception as e:
            return {
                "agent_name": self.agent_name,
                "result": f"Error: {e}",
                "rounds": self.rounds,
                "token_usage": self.token_usage,
                **(extraction.report() if extraction else {}),
            }

    def _extract_profile(self, task_input: str) -> dict:
        """Use llm_chat_with_json_output to extract structured profile.

        Args:
            task_input: Raw user input text.

        Returns:
            Dict with keys: user_name, preferred_tools,
            preferred_language, response_style.
        """
        self.token_usage = None
        system_instruction = "".join(self.config.get("description", []))
        self.messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": task_input},
        ]

        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "user_profile",
                "schema": {
                    "type": "object",
                    "properties": {
                        "user_name": {"type": "string"},
                        "preferred_tools": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "preferred_language": {"type": "string"},
                        "response_style": {"type": "string"},
                    },
                    "required": [
                        "user_name",
                        "preferred_tools",
                        "preferred_language",
                        "response_style",
                    ],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        }

        response = llm_chat_with_json_output(
            agent_name=self.agent_name,
            messages=self.messages,
            base_url=aios_kernel_url,
            llms=getattr(self, 'llms', None),
            response_format=response_format,
        )

        self.token_usage = response.get("token_usage")
        return parse_json_reply(response["response"]["response_message"])

    def _upsert_profile_memory(self, user_id: str, extraction: Extraction) -> list:
        """Search for existing profile memories, update or create.

        Args:
            user_id: Identifier for the user this memory pertains to.
            extraction: The validated extraction to store.

        Returns:
            List of memory IDs that were created or updated.
        """
        memory_ids = []
        if isinstance(extraction, dict):  # already-validated fields
            extraction = Extraction(MEMORY_TYPE_PROFILE, fields=extraction)
        content = extraction.text
        fields_json = structured(extraction.fields)

        # Search for existing profile memories
        search_response = search_memories(
            agent_name=self.agent_name,
            query=f"profile {user_id}",
            base_url=aios_kernel_url,
            user_id=user_id,
        )

        existing_results = []
        if search_response and isinstance(search_response, dict):
            resp = search_response.get("response", {})
            if resp and isinstance(resp, dict):
                existing_results = resp.get("search_results", []) or []

        # Filter for profile-type memories owned by this agent
        matching = [
            r for r in existing_results
            if r.get("metadata", {}).get("memory_type") == MEMORY_TYPE_PROFILE
        ]

        if matching:
            # Update existing profile memory
            for mem in matching:
                memory_id = mem.get("memory_id", mem.get("id", ""))
                if memory_id:
                    update_memory(
                        agent_name=self.agent_name,
                        memory_id=memory_id,
                        content=content,
                        metadata={
                            "user_id": user_id,
                            FIELD_STRUCTURED: fields_json,
                        },
                        base_url=aios_kernel_url,
                    )
                    memory_ids.append(memory_id)
        else:
            # Create new profile memory
            metadata = build_memory_metadata(
                owner_agent=self.agent_name,
                user_id=user_id,
                memory_type=MEMORY_TYPE_PROFILE,
                sharing_policy=POLICY_SHARED if getattr(self, 'share_memory', False) else POLICY_PRIVATE,
                **{FIELD_STRUCTURED: fields_json},
            )
            create_response = create_memory(
                agent_name=self.agent_name,
                content=content,
                metadata=metadata,
                base_url=aios_kernel_url,
            )
            if create_response and isinstance(create_response, dict):
                resp = create_response.get("response", {})
                if resp and isinstance(resp, dict):
                    mid = resp.get("memory_id", "")
                    if mid:
                        memory_ids.append(mid)

        return memory_ids

    def share_memory(self, memory_id: str) -> None:
        """Phase 2: Mark a profile memory as shared.

        Sets the sharing_policy metadata to "shared" on an already-stored
        memory so that other agents can discover it via search_memories.

        Args:
            memory_id: ID of the memory to share.
        """
        update_memory(
            agent_name=self.agent_name,
            memory_id=memory_id,
            metadata={FIELD_SHARING_POLICY: POLICY_SHARED},
            base_url=aios_kernel_url,
        )

    def revoke_sharing(self, memory_id: str) -> None:
        """Phase 2: Revoke sharing on a profile memory.

        Sets the sharing_policy metadata back to "private" so that the
        memory is no longer visible to other agents.

        Args:
            memory_id: ID of the memory to make private.
        """
        update_memory(
            agent_name=self.agent_name,
            memory_id=memory_id,
            metadata={FIELD_SHARING_POLICY: POLICY_PRIVATE},
            base_url=aios_kernel_url,
        )
