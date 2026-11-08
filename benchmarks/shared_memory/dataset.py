"""The fixed benchmark users (Subtask 9).

``data/users_v1.jsonl`` holds 150 synthetic users (profile, task context,
plausible actions, follow-up query), generated once with ``synth.py``'s
prompts and GPT-4o, with a seed. The first line is a header record (the
generation seed, model, date, prompts' hash); each further line is one
user with its ``index``. A run with ``--dataset users_v1`` (or
``pilot_v1``, the first 30 users) scores user ``i`` as trial ``i``, so
every cell scores the same users and two cells pair by trial index.
``--dataset random`` keeps per-trial generation; it is never used for
reported results. Never edit a dataset file; make a new version.

    python -m benchmarks.shared_memory.dataset generate \\
        --out benchmarks/shared_memory/data/users_v1.jsonl \\
        --n 150 --seed 20261104 --model azure/gpt-4o
    python -m benchmarks.shared_memory.dataset check users_v1
"""
import argparse
import hashlib
import inspect
import json
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import List, Optional
from unittest.mock import patch

from benchmarks.shared_memory import synth
from benchmarks.shared_memory.models import (
    SyntheticProfile,
    SyntheticTaskContext,
    SyntheticTrialData,
    V2UserData,
    _harness_commit,
)

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent / "data"
# Named datasets: (file, number of leading users).
NAMED = {
    "users_v1": ("users_v1.jsonl", None),
    "pilot_v1": ("users_v1.jsonl", 30),
    # Benchmark v2 (AIOS docs/BENCHMARK_V2.md): the same 150 base users
    # with a scripted history each; pilot_v2 is the first 30.
    "users_v2": ("users_v2.jsonl", None),
    "pilot_v2": ("users_v2.jsonl", 30),
}
RANDOM = "random"
PROFILE_RETRIES = 5
QUERY_RETRIES = 3


@dataclass
class Dataset:
    """A loaded dataset: its name, header record and users."""

    name: str
    path: Path
    header: dict
    users: List[dict]
    sha256: str

    def __len__(self) -> int:
        return len(self.users)

    def trial_data(self, index: int, run_id: str) -> SyntheticTrialData:
        """User ``index`` as trial data, with the run-scoped user id
        the generator uses (``{name}_{run_id}_t{index}``)."""
        user = self.users[index]
        if user["index"] != index:
            raise ValueError(f"{self.path}: user {index} out of order")
        profile = SyntheticProfile(**user["profile"])
        base = profile.user_name.lower().replace(" ", "_")
        return SyntheticTrialData(
            profile=profile,
            task_context=SyntheticTaskContext(**user["task_context"]),
            follow_up_query=user["follow_up_query"],
            plausible_actions=user["plausible_actions"],
            user_id=f"{base}_{run_id}_t{index}",
        )

    @property
    def version(self) -> int:
        """The file's format: 1 (``users_v1``) or 2 (benchmark v2)."""
        return int(self.header.get("format_version", 1))

    def user_v2(self, index: int, run_id: str) -> V2UserData:
        """Benchmark v2 user ``index`` with the run-scoped user id the
        v1 users get (``{name}_{run_id}_t{index}``)."""
        if self.version != 2:
            raise ValueError(f"{self.name} is not a benchmark v2 dataset")
        user = self.users[index]
        if user["index"] != index:
            raise ValueError(f"{self.path}: user {index} out of order")
        final = user["final"]
        profile = SyntheticProfile(**final["profile"])
        base = profile.user_name.lower().replace(" ", "_")
        return V2UserData(
            index=index,
            user_id=f"{base}_{run_id}_t{index}",
            profile=profile,
            task_context=SyntheticTaskContext(**final["task_context"]),
            follow_up_query=user["base"]["follow_up_query"],
            plausible_actions=user["base"].get("plausible_actions", []),
            sessions=user["sessions"],
            probes=user["probes"],
        )

    def describe(self) -> dict:
        """What results files record about the dataset."""
        return {
            "name": self.name,
            "file": self.path.name,
            "sha256": self.sha256,
            "users": len(self.users),
            "seed": self.header.get("seed"),
            "model": self.header.get("model"),
            "date": self.header.get("date"),
        }


def load(spec: str) -> Optional[Dataset]:
    """A named dataset or a path; None for ``random``."""
    if spec == RANDOM:
        return None
    if spec in NAMED:
        filename, limit = NAMED[spec]
        path, name = DATA_DIR / filename, spec
    else:
        path, limit = Path(spec), None
        name = path.stem
    raw = path.read_bytes()
    lines = [json.loads(line) for line in raw.decode("utf-8").splitlines()
             if line.strip()]
    header, users = lines[0], lines[1:]
    if header.get("type") != "header":
        raise ValueError(f"{path}: the first record is not a header")
    if [u["index"] for u in users] != list(range(len(users))):
        raise ValueError(f"{path}: user indexes are not 0..n-1")
    if limit is not None:
        users = users[:limit]
    return Dataset(name, path, header, users,
                   hashlib.sha256(raw).hexdigest())


def v2_input_sha256(user: "V2UserData") -> str:
    """A hash of a v2 user's whole script, what the trial gives the
    agents: every session with its events and utterances, and every
    probe (not the run-scoped user id)."""
    text = json.dumps({"sessions": user.sessions, "probes": user.probes},
                      sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def trial_input_sha256(trial_data: SyntheticTrialData) -> str:
    """A hash of what the trial gives the agents: the two writers'
    inputs and the follow-up query (not the run-scoped user id)."""
    inputs = {
        "profile_input": json.dumps(trial_data.profile.model_dump()),
        "task_input": json.dumps(trial_data.task_context.model_dump()),
        "query": trial_data.follow_up_query,
    }
    text = json.dumps(inputs, sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def prompts_sha256() -> str:
    """A hash of the generator's source (its prompts and schemas)."""
    source = inspect.getsource(synth.SyntheticDataGenerator)
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


class _SeededLLM:
    """Stands in for the kernel calls ``synth.py`` makes: the same
    messages and response format, sent to LiteLLM directly with a seed
    (the kernel's chat API carries no seed)."""

    def __init__(self, model: str):
        self.model = model
        self.seed = 0
        self.calls = 0

    def __call__(self, agent_name=None, messages=None, base_url=None,
                 response_format=None, llms=None, **_):
        import litellm

        kwargs = {"model": self.model, "messages": messages,
                  "seed": self.seed}
        if response_format is not None:
            kwargs["response_format"] = response_format
        response = litellm.completion(**kwargs)
        self.calls += 1
        return {"response": {
            "response_message": response.choices[0].message.content,
        }}


def generate_user(generator, llm: _SeededLLM, index: int, seed: int,
                  names: set) -> tuple:
    """One user, as ``generate_trial_data`` builds it, plus notes. A
    profile whose name is already taken, or a query that names a
    profile or task literal, is generated again with the next seed."""
    notes = {}
    for attempt in range(PROFILE_RETRIES + 1):
        llm.seed = seed + index + 100_000 * attempt
        profile = generator.generate_profile(index)
        if profile.user_name.strip().lower() not in names:
            break
    else:
        notes["duplicate_name"] = True
    notes["profile_attempts"] = attempt + 1
    task_context = generator.generate_task_context(index, profile)
    actions = generator.generate_plausible_actions(profile, task_context)
    for attempt in range(QUERY_RETRIES + 1):
        llm.seed = seed + index + 100_000 * attempt
        query = generator.generate_vague_query(profile, task_context)
        if synth._validate_vague_query(query, profile, task_context):
            break
    else:
        notes["query_names_a_literal"] = True
    return SyntheticTrialData(
        profile=profile, task_context=task_context,
        follow_up_query=query, plausible_actions=actions,
    ), notes


def generate(out: Path, n: int, seed: int, model: str) -> dict:
    """Write ``n`` users to ``out``; return the header. Resumable: users
    already in ``<out>.partial.jsonl`` are kept."""
    partial = out.with_name(out.name + ".partial.jsonl")
    done = []
    if partial.exists():
        done = [json.loads(line) for line in partial.read_text().splitlines()
                if line.strip()]
    llm = _SeededLLM(model)
    generator = synth.SyntheticDataGenerator(llms=None, run_id="dataset")
    names = {u["profile"]["user_name"].strip().lower() for u in done}
    with patch.object(synth, "llm_chat_with_json_output", llm), \
            patch.object(synth, "llm_chat", llm), \
            open(partial, "a") as handle:
        for index in range(len(done), n):
            data, notes = generate_user(generator, llm, index, seed, names)
            names.add(data.profile.user_name.strip().lower())
            record = {
                "type": "user", "index": index,
                "profile": data.profile.model_dump(),
                "task_context": data.task_context.model_dump(),
                "plausible_actions": data.plausible_actions,
                "follow_up_query": data.follow_up_query,
                "generation": notes,
            }
            handle.write(json.dumps(record) + "\n")
            handle.flush()
            done.append(record)
            logger.info("user %d: %s", index, data.profile.user_name)
    import litellm

    header = {
        "type": "header",
        "dataset": out.stem,
        "users": n,
        "seed": seed,
        "model": model,
        "date": date.today().isoformat(),
        "generator": "benchmarks/shared_memory/synth.py "
                     "SyntheticDataGenerator, LiteLLM direct with seed",
        "generator_sha256": prompts_sha256(),
        "harness_commit": _harness_commit(),
        "litellm_version": getattr(litellm, "__version__", None)
        or _litellm_version(),
        "pilot": {"pilot_v1": 30},
        "seed_rule": "seed + index + 100000 * attempt per call",
    }
    with open(out, "w") as handle:
        for record in [header] + done[:n]:
            handle.write(json.dumps(record) + "\n")
    partial.unlink()
    return header


def _litellm_version() -> Optional[str]:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("litellm")
    except PackageNotFoundError:
        return None


def summary(dataset: Dataset) -> dict:
    """Counts a reviewer checks before a dataset is used."""
    names = [u["profile"]["user_name"] for u in dataset.users]
    languages = {u["profile"]["preferred_language"] for u in dataset.users}
    return {
        **dataset.describe(),
        "distinct_names": len({n.lower() for n in names}),
        "distinct_languages": len(languages),
        "duplicate_name_notes": sum(
            1 for u in dataset.users
            if u.get("generation", {}).get("duplicate_name")
        ),
        "query_literal_notes": sum(
            1 for u in dataset.users
            if u.get("generation", {}).get("query_names_a_literal")
        ),
        "no_blockers": sum(
            1 for u in dataset.users if not u["task_context"]["blockers"]
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate")
    gen.add_argument("--out", type=Path, required=True)
    gen.add_argument("--n", type=int, default=150)
    gen.add_argument("--seed", type=int, required=True)
    gen.add_argument("--model", default="azure/gpt-4o")
    check = sub.add_parser("check")
    check.add_argument("dataset")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    if args.command == "generate":
        print(json.dumps(generate(args.out, args.n, args.seed, args.model),
                         indent=2))
    else:
        print(json.dumps(summary(load(args.dataset)), indent=2))


if __name__ == "__main__":
    main()
