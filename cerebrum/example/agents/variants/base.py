"""How a heterogeneity variant reaches an agent in each locus (NeurIPS
Subtask 10, AIOS docs/HETEROGENEITY.md, "How a variant reaches each
locus").

A variant changes one or more aspects of an agent:

- ``identity``: the user id the agent tags its requests and writes with;
- ``sharing``: a writer's default sharing policy;
- ``write``: the content and metadata of every memory the agent writes;
- ``retrieval``: the agent's own retrieval config (k, threshold, token
  budget, block format);
- ``access_control``: whether the consumer applies a visibility rule of
  its own.

``apply_variant`` applies the aspects a locus has a channel for, for one
run of one agent, and restores the agent afterwards (the replicated and
native agents live across trials). It yields the aspects the locus gives
the agent no way to apply, with the reason; the trial records them as
``variants_not_applied``.
"""
import contextlib
import dataclasses
from typing import Any, Dict, Iterator, List, Optional, Tuple

WRITERS = ("profile_agent", "task_agent")
CONSUMER = "assistant_agent"
AGENTS = WRITERS + (CONSUMER,)
LOCI = ("kernel", "replicated", "native")

# Retrieval overrides a variant may give, by the library's setting name.
RETRIEVAL_KEYS = (
    "k", "relevance_threshold", "max_memory_tokens", "block_format",
)

# Why an aspect has no channel: (locus or "*", role, aspect) -> reason.
NOT_APPLIED = {
    ("kernel", "consumer", "write"):
        "write: the kernel writes the conversation itself",
    ("kernel", "consumer", "retrieval"):
        "retrieval: a chat request carries no retrieval config; the "
        "kernel applies its own",
    ("kernel", "writer", "retrieval"):
        "retrieval: the SDK search carries k only; the kernel applies "
        "its own threshold",
    ("kernel", "consumer", "access_control"):
        "access control: the kernel enforces visibility",
    ("replicated", "consumer", "access_control"):
        "access control: the library the agent links enforces "
        "visibility",
    ("native", "writer", "retrieval"):
        "retrieval: native writers do not read",
    ("*", "writer", "access_control"):
        "access control: a writer reads only its own memories",
    ("*", "consumer", "sharing"):
        "sharing: the assistant writes only its private conversation",
}


def role_of(agent_name: str) -> str:
    if agent_name in WRITERS:
        return "writer"
    if agent_name == CONSUMER:
        return "consumer"
    raise ValueError(f"unknown agent {agent_name!r}")


class Variant:
    """The reference: every hook returns its input. A variant module
    subclasses it and overrides the hooks of its ``aspects``."""

    code = "reference"
    title = "reference implementation"
    aspects: frozenset = frozenset()

    def user_id(self, user_id: Optional[str]) -> Optional[str]:
        return user_id

    def share_memory(self, reference: bool) -> bool:
        return reference

    def write(
        self, content: str, metadata: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any]]:
        return content, metadata

    def retrieval(self, role: str) -> Dict[str, Any]:
        """Overrides of the agent's retrieval settings for ``role``
        (``RETRIEVAL_KEYS``); empty for none."""
        return {}

    def access_control(self) -> bool:
        return True

    def has(self, aspect: str, role: str) -> bool:
        """Whether this variant changes ``aspect`` for an agent of
        ``role``."""
        if aspect not in self.aspects:
            return False
        if aspect == "retrieval":
            return bool(self.retrieval(role))
        return True

    def __repr__(self) -> str:
        return f"<{self.code}: {self.title}>"


class _Restore:
    """Attribute changes to undo, last first."""

    def __init__(self):
        self._undo: List[Tuple[Any, str, Any, bool]] = []

    def set(self, obj: Any, name: str, value: Any) -> None:
        had = name in vars(obj) if hasattr(obj, "__dict__") else False
        self._undo.append((obj, name, getattr(obj, name, None), had))
        setattr(obj, name, value)

    def undo(self) -> None:
        for obj, name, old, had in reversed(self._undo):
            if had:
                setattr(obj, name, old)
            else:
                try:
                    delattr(obj, name)
                except AttributeError:
                    setattr(obj, name, old)
        self._undo.clear()


def _reason(locus: str, role: str, aspect: str) -> Optional[str]:
    return NOT_APPLIED.get((locus, role, aspect)) or NOT_APPLIED.get(
        ("*", role, aspect)
    )


def _kernel_write(variant: Variant, agent: Any, restore: _Restore) -> None:
    """Kernel writers: transform the SDK requests their module sends."""
    import importlib

    module = importlib.import_module(type(agent).__module__)

    for name in ("create_memory", "update_memory"):
        current = getattr(module, name)

        def wrapped(*args, _send=current, **kwargs):
            if "content" in kwargs or "metadata" in kwargs:
                content, metadata = variant.write(
                    kwargs.get("content"), dict(kwargs.get("metadata") or {})
                )
                if kwargs.get("content") is not None:
                    kwargs["content"] = content
                if kwargs.get("metadata") is not None:
                    kwargs["metadata"] = metadata
            return _send(*args, **kwargs)

        restore.set(module, name, wrapped)


def _replicated_pipeline(variant: Variant, agent: Any, role: str,
                         restore: _Restore) -> Any:
    """The agent's pipeline with the variant's retrieval settings: a new
    ``MemoryPipeline`` over the same provider, barrier and resolver."""
    memory = agent.memory
    pipeline = memory.pipeline
    overrides = variant.retrieval(role) if variant.has(
        "retrieval", role) else {}
    if not overrides:
        return pipeline
    names = {"k": "max_injected_memories"}
    settings = dataclasses.replace(pipeline.settings, **{
        names.get(key, key): value for key, value in overrides.items()
    })
    tuned = memory.library.MemoryPipeline(
        pipeline.provider, settings,
        barrier=pipeline.barrier, resolver=pipeline.resolver,
    )
    restore.set(memory, "pipeline", tuned)
    return tuned


def _replicated_write(variant: Variant, pipeline: Any,
                      restore: _Restore) -> None:
    write, update = pipeline.write, pipeline.update

    def wrapped_write(agent_name, user_id, note, **kwargs):
        content, metadata = variant.write(
            note.content, dict(note.metadata or {})
        )
        note.content, note.metadata = content, metadata
        return write(agent_name, user_id, note, **kwargs)

    def wrapped_update(agent_name, user_id, memory_id, content=None,
                       metadata=None, **kwargs):
        new_content, new_metadata = variant.write(
            content, dict(metadata or {})
        )
        return update(
            agent_name, user_id, memory_id,
            new_content if content is not None else None,
            new_metadata if metadata is not None else None,
            **kwargs,
        )

    restore.set(pipeline, "write", wrapped_write)
    restore.set(pipeline, "update", wrapped_update)


def _native_write(variant: Variant, agent: Any, restore: _Restore) -> None:
    memory = agent.memory
    write = memory.write

    def wrapped(messages, text, agent_name, metadata):
        new_text, new_metadata = variant.write(text, dict(metadata))
        if new_text != text:
            # Mem0 extracts from the messages: they carry the new text.
            messages = [{"role": "user", "content": new_text}]
        # In place: the writer reports this dict as what it stored.
        metadata.clear()
        metadata.update(new_metadata)
        return write(messages, new_text, agent_name, metadata)

    restore.set(memory, "write", wrapped)


@contextlib.contextmanager
def apply_variant(
    variant: Optional[Variant], agent: Any, agent_name: str, locus: str,
) -> Iterator[Optional[str]]:
    """Apply ``variant`` to ``agent`` (named ``agent_name``) in
    ``locus`` for the block; yield the not-applied reasons joined with
    "; " (None when every aspect applied, or no variant)."""
    if variant is None:
        yield None
        return
    if locus not in LOCI:
        raise ValueError(f"variants apply to the {LOCI} loci, not {locus!r}")
    role = role_of(agent_name)
    restore = _Restore()
    skipped: List[str] = []

    def skip(aspect: str) -> None:
        reason = _reason(locus, role, aspect)
        if reason is None:
            raise AssertionError(
                f"no channel and no reason for {aspect} ({locus}, {role})"
            )
        skipped.append(reason)

    try:
        if variant.has("identity", role):
            restore.set(agent, "user_id", variant.user_id(agent.user_id))

        if variant.has("sharing", role):
            if role == "writer":
                restore.set(agent, "share_memory", variant.share_memory(
                    getattr(agent, "share_memory", True)
                ))
            else:
                skip("sharing")

        pipeline = None
        if locus == "replicated":
            pipeline = _replicated_pipeline(variant, agent, role, restore)
        if variant.has("retrieval", role):
            overrides = variant.retrieval(role)
            if locus == "native" and role == "consumer":
                for key, value in overrides.items():
                    restore.set(agent, key, value)
            elif locus != "replicated":
                skip("retrieval")

        if variant.has("write", role):
            if locus == "kernel":
                if role == "writer":
                    _kernel_write(variant, agent, restore)
                else:
                    skip("write")
            elif locus == "replicated":
                _replicated_write(variant, pipeline, restore)
            else:
                _native_write(variant, agent, restore)

        if variant.has("access_control", role):
            if locus == "native" and role == "consumer":
                restore.set(
                    agent, "check_visibility", variant.access_control()
                )
            else:
                skip("access_control")

        yield "; ".join(skipped) if skipped else None
    finally:
        restore.undo()
