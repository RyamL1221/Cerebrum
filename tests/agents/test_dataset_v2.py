"""Loading benchmark v2 datasets (NeurIPS Subtask 14, AIOS
docs/BENCHMARK_V2.md, "File"): the version, the run-scoped v2 user, the
script hash, and v1 unchanged."""
import json

import pytest

from benchmarks.shared_memory import dataset, synth_v2
from benchmarks.shared_memory.models import V2UserData


@pytest.fixture(scope="module")
def v2(tmp_path_factory):
    path = tmp_path_factory.mktemp("v2") / "users_v2_t.jsonl"
    synth_v2.generate(path, n=4)
    return dataset.load(str(path))


def test_a_v2_file_loads_as_version_2(v2):
    assert v2.version == 2 and len(v2) == 4
    assert dataset.load("pilot_v1").version == 1
    described = v2.describe()
    assert set(described) == {"name", "file", "sha256", "users", "seed",
                              "model", "date"}
    assert described["seed"] == 20261108


def test_user_v2_has_the_v1_user_id_and_the_final_state(v2):
    user = v2.user_v2(2, "run9")
    assert isinstance(user, V2UserData)
    record = v2.users[2]
    name = record["final"]["profile"]["user_name"]
    assert user.user_id == f"{name.lower().replace(' ', '_')}_run9_t2"
    assert user.profile.model_dump() == record["final"]["profile"]
    assert user.follow_up_query == record["base"]["follow_up_query"]
    assert [p["type"] for p in user.probes][-1] == "integration"
    assert len(user.sessions) == 6
    with pytest.raises(ValueError):
        dataset.load("pilot_v1").user_v2(0, "r")


def test_the_input_hash_covers_the_script(v2):
    a = v2.user_v2(0, "r1")
    b = v2.user_v2(0, "r2")  # another run id, the same script
    assert dataset.v2_input_sha256(a) == dataset.v2_input_sha256(b)
    changed = a.model_copy(deep=True)
    changed.sessions[2]["events"][0]["utterance"] += " Really."
    assert dataset.v2_input_sha256(changed) != dataset.v2_input_sha256(a)
    changed = a.model_copy(deep=True)
    changed.probes[0]["question"] = "Something else?"
    assert dataset.v2_input_sha256(changed) != dataset.v2_input_sha256(a)


def test_the_named_v2_datasets_resolve_to_one_file():
    assert dataset.NAMED["users_v2"] == ("users_v2.jsonl", None)
    assert dataset.NAMED["pilot_v2"] == ("users_v2.jsonl", 30)
    if not (dataset.DATA_DIR / "users_v2.jsonl").exists():
        pytest.skip("users_v2.jsonl is not generated yet")
    full, pilot = dataset.load("users_v2"), dataset.load("pilot_v2")
    assert (len(full), len(pilot)) == (150, 30)
    assert pilot.users == full.users[:30]
    assert pilot.sha256 == full.sha256
    header = json.loads((dataset.DATA_DIR / "users_v2.jsonl")
                        .read_text().splitlines()[0])
    assert header["seed"] == 20261108 and header["format_version"] == 2


def test_v1_loading_is_unchanged():
    pilot = dataset.load("pilot_v1")
    data = pilot.trial_data(0, "r")
    assert data.user_id.endswith("_r_t0")
    assert dataset.trial_input_sha256(data)
