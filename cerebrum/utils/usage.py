"""Token usage of the LLM and embedding calls a memory backend makes.

A backend such as Mem0 calls its own LLM and embedder, so neither the
kernel's LLM adapter nor the agent sees those calls. The code that calls
the backend sets a trial tag (``tagged``); Mem0's LLM is routed through
LiteLLM, whose success callback (``LiteLLMUsageLogger``) records each
call under the tag current when it was made, and ``count_embeddings``
does the same for the Ollama embedding client. ``ACCUMULATOR`` holds the
records per tag until ``take`` returns them.

The same code runs in the kernel (kernel conditions, read through
``GET /memory/cost``) and in the harness process (native conditions,
where the agents hold the backend client). The tag is the trial's
user_id, which is unique per trial.
"""
import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Dict, Iterator, List, Optional

BACKEND_EXTRACTION = "backend_extraction"
EMBEDDING = "embedding"

_tag: ContextVar[Optional[str]] = ContextVar("backend_usage_tag", default=None)


@contextmanager
def tagged(trial_tag: Optional[str]) -> Iterator[None]:
    """Attribute the backend calls made inside the block to ``trial_tag``.
    A falsy tag leaves the current one in place."""
    if not trial_tag:
        yield
        return
    token = _tag.set(trial_tag)
    try:
        yield
    finally:
        _tag.reset(token)


def current_tag() -> Optional[str]:
    return _tag.get()


class UsageAccumulator:
    """Per-tag usage records, safe across threads.

    LiteLLM runs success callbacks on a background thread, so a call can
    have returned before its record exists. ``begin`` marks a call in
    flight and ``take`` waits for a tag's calls to finish.
    """

    def __init__(self) -> None:
        self._records: Dict[str, List[dict]] = {}
        self._pending: Dict[str, set] = {}
        self._changed = threading.Condition()

    def begin(self, tag: str, call_id: str) -> None:
        with self._changed:
            self._pending.setdefault(tag, set()).add(call_id)

    def end(self, tag: str, call_id: str) -> None:
        with self._changed:
            self._pending.get(tag, set()).discard(call_id)
            self._changed.notify_all()

    def record(
        self, tag: str, purpose: str, model: str,
        prompt_tokens: Optional[int], completion_tokens: Optional[int],
        call_id: Optional[str] = None,
    ) -> None:
        with self._changed:
            self._records.setdefault(tag, []).append({
                "trial_tag": tag,
                "purpose": purpose,
                "model": model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            })
            if call_id is not None:
                self._pending.get(tag, set()).discard(call_id)
            self._changed.notify_all()

    def take(self, tag: str, wait: float = 5.0) -> List[dict]:
        """Remove and return a tag's records, after waiting up to
        ``wait`` seconds for its calls in flight."""
        deadline = time.monotonic() + wait
        with self._changed:
            while self._pending.get(tag):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._changed.wait(remaining)
            self._pending.pop(tag, None)
            return self._records.pop(tag, [])


ACCUMULATOR = UsageAccumulator()


def _litellm_model(kwargs: Dict[str, Any]) -> str:
    model = kwargs.get("model") or ""
    provider = kwargs.get("custom_llm_provider")
    if provider and not model.startswith(f"{provider}/"):
        return f"{provider}/{model}"
    return model


def _logger_class():
    from litellm.integrations.custom_logger import CustomLogger

    class LiteLLMUsageLogger(CustomLogger):
        """Records every LiteLLM call made under a trial tag. Calls made
        with no tag (the kernel's own assistant calls) are ignored."""

        def __init__(self, accumulator: UsageAccumulator):
            super().__init__()
            self.accumulator = accumulator

        def log_pre_api_call(self, model, messages, kwargs):
            tag = current_tag()
            call_id = kwargs.get("litellm_call_id")
            if tag and call_id:
                self.accumulator.begin(tag, call_id)

        def log_success_event(self, kwargs, response_obj, start_time,
                              end_time):
            tag = current_tag()
            if not tag:
                return
            usage = getattr(response_obj, "usage", None)
            self.accumulator.record(
                tag, BACKEND_EXTRACTION, _litellm_model(kwargs),
                getattr(usage, "prompt_tokens", None),
                getattr(usage, "completion_tokens", None),
                call_id=kwargs.get("litellm_call_id"),
            )

        def log_failure_event(self, kwargs, response_obj, start_time,
                              end_time):
            tag = current_tag()
            call_id = kwargs.get("litellm_call_id")
            if tag and call_id:
                self.accumulator.end(tag, call_id)

    return LiteLLMUsageLogger


_install_lock = threading.Lock()


def install_litellm_logger(accumulator: UsageAccumulator = ACCUMULATOR):
    """Register the usage logger with LiteLLM once per process."""
    import litellm

    with _install_lock:
        for callback in litellm.callbacks:
            if getattr(callback, "accumulator", None) is accumulator:
                return callback
        callback = _logger_class()(accumulator)
        litellm.callbacks.append(callback)
        return callback


def litellm_model_name(provider: str, model: str) -> str:
    """LiteLLM's ``<provider>/<model>`` for a ``memory.backend_llm``
    provider name."""
    prefixes = {"azure_openai": "azure", "azure": "azure",
                "ollama": "ollama", "openai": "openai"}
    if provider not in prefixes:
        raise ValueError(f"no LiteLLM route for provider {provider!r}")
    return f"{prefixes[provider]}/{model}"


def mem0_llm_config(backend_llm: dict) -> dict:
    """Mem0's ``llm`` config for the pinned internal LLM
    (``memory.backend_llm``): Mem0's ``litellm`` provider, so each call
    reaches LiteLLM's callbacks and is counted per trial. LiteLLM reads
    the credentials from the environment (``AZURE_API_*``). The kernel's
    Mem0 provider (with ``infer``), the replicated and the native agents
    all configure Mem0 with this."""
    provider = backend_llm.get("provider")
    model = backend_llm.get("model")
    if not provider or not model:
        raise ValueError("memory.backend_llm needs a provider and a model")
    if provider not in ("azure_openai", "ollama"):
        raise ValueError(f"unsupported backend_llm provider {provider!r}")
    return {"provider": "litellm", "config": {
        "model": litellm_model_name(provider, model),
        "temperature": backend_llm.get("temperature", 0.1),
    }}


def count_embeddings(client: Any, model: str,
                     accumulator: UsageAccumulator = ACCUMULATOR) -> Any:
    """Wrap an Ollama ``Client``'s ``embed`` so each call made under a
    trial tag records its input tokens (Ollama's ``prompt_eval_count``).
    Idempotent; returns the client."""
    if getattr(client, "_usage_counted", False):
        return client
    embed = client.embed

    def counted_embed(*args, **kwargs):
        response = embed(*args, **kwargs)
        tag = current_tag()
        if tag:
            tokens = getattr(response, "prompt_eval_count", None)
            if tokens is None and isinstance(response, dict):
                tokens = response.get("prompt_eval_count")
            accumulator.record(tag, EMBEDDING, f"ollama/{model}", tokens, 0)
        return response

    client.embed = counted_embed
    client._usage_counted = True
    return client


def summarize(records: List[dict], purpose: str) -> Dict[str, Any]:
    """Totals of one purpose's records: calls, prompt / completion /
    total tokens and the models seen."""
    rows = [r for r in records if r.get("purpose") == purpose]
    prompt = sum(r.get("prompt_tokens") or 0 for r in rows)
    completion = sum(r.get("completion_tokens") or 0 for r in rows)
    return {
        "calls": len(rows),
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": prompt + completion,
        "models": sorted({r.get("model") or "" for r in rows} - {""}),
    }
