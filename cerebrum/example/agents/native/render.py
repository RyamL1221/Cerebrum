"""Render a writer's extracted JSON as one natural-language memory.

The native writers store this text (docs/NATIVE_USAGE.md in AIOS, "Memory
text"). Real extractions do not always follow the schema, so known
aliases are mapped, a single nested object is unwrapped and unknown keys
are kept as sentences.
"""

ALIASES = {
    "profile": {
        "name": ("user_name", "username", "name"),
        "tools": ("preferred_tools", "tools"),
        "language": ("preferred_language", "language"),
        "style": ("response_style", "response_type", "style"),
    },
    "task_context": {
        "project": ("current_project", "project_name", "project"),
        "experiment": ("active_experiment", "experiment_name", "experiment"),
        "goals": ("goals",),
        "blockers": ("blockers",),
        "next_steps": ("next_steps", "next_actions"),
    },
}

TEMPLATES = {
    "profile": [
        ("name", "My name is {}."),
        ("tools", "I prefer to use {}."),
        ("language", "My preferred programming language is {}."),
        ("style", "I like {} responses."),
    ],
    "task_context": [
        ("project", "I'm working on {}."),
        ("experiment", "My current experiment is {}."),
        ("goals", "My goals are: {}."),
        ("blockers", "My blockers are: {}."),
        ("next_steps", "My next steps are: {}."),
    ],
}


def _text(value) -> str:
    if isinstance(value, (list, tuple)):
        return "; ".join(_text(v) for v in value)
    return str(value).strip()


def normalize(memory_type: str, data: dict) -> dict:
    """Map a writer's keys to the renderer's fields. A single key holding
    an object is unwrapped first; unknown keys are kept as they are."""
    if len(data) == 1 and isinstance(next(iter(data.values())), dict):
        data = next(iter(data.values()))
    fields, used = {}, set()
    for field, keys in ALIASES[memory_type].items():
        for key in keys:
            if data.get(key) not in (None, "", []):
                fields[field] = data[key]
                used.add(key)
                break
    extra = {k: v for k, v in data.items() if k not in used}
    return {"fields": fields, "extra": extra}


def render(memory_type: str, data: dict) -> str:
    parts = normalize(memory_type, data)
    sentences = [
        template.format(_text(parts["fields"][field]))
        for field, template in TEMPLATES[memory_type]
        if field in parts["fields"]
    ]
    sentences += [
        f"{key.replace('_', ' ').capitalize()}: {_text(value)}."
        for key, value in parts["extra"].items()
    ]
    return " ".join(sentences)
