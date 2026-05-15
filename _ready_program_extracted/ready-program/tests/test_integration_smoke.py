from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.validate_schemas import _validate
from xyzgl.config import XYZGLConfig
from xyzgl.knowledge.embeddings import text_to_vector
from xyzgl.knowledge.lithosphere import Lithosphere
from xyzgl.persona import build_persona_instruction, persona_from_config
from xyzgl.router import route_turn

pytestmark = pytest.mark.integration


EVENT_ID = "EVT-0123456789ab"
ISSUE_ID = "ISSUE-20260313-219"
CREATED_AT = "2026-03-13T00:00:00Z"


def _make_event(payload: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": "witness_event@1",
        "event_id": EVENT_ID,
        "issue_id": ISSUE_ID,
        "created_at": CREATED_AT,
        "payload": payload,
    }


def _assert_schema_valid(doc: dict[str, object], schema_name: str) -> None:
    errors = _validate(doc, schema_name)
    assert not errors, f"schema validation failed for {schema_name}: {errors}"


def _assert_physics_block(physics: dict[str, object]) -> None:
    for key in ("mastery", "resonance", "text_similarity", "mastery_delta"):
        assert key in physics, f"missing physics key: {key}"
        assert isinstance(physics[key], (int, float)), f"physics[{key!r}] must be numeric"

    mastery = float(physics["mastery"])
    resonance = float(physics["resonance"])
    text_similarity = float(physics["text_similarity"])

    assert 0.0 <= mastery <= 1.0
    assert -1.0 <= resonance <= 1.0
    assert 0.0 <= text_similarity <= 1.0


def _build_turn_report(turn_result: dict[str, object]) -> dict[str, object]:
    return _make_event({"turn_result": turn_result})


def _build_session_report(turn_result: dict[str, object]) -> dict[str, object]:
    prompt_meta = dict(turn_result.get("prompt_meta", {}))
    teach_meta = dict(prompt_meta)
    eval_meta = dict(prompt_meta)

    teach_meta.setdefault("persona_injected", bool(prompt_meta.get("persona_injected", prompt_meta.get("persona_active", False))))
    teach_meta.setdefault("persona_active", bool(prompt_meta.get("persona_active", False)))
    eval_meta.setdefault("persona_injected", bool(prompt_meta.get("persona_injected", prompt_meta.get("persona_active", False))))
    eval_meta.setdefault("persona_active", bool(prompt_meta.get("persona_active", False)))

    physics = dict(turn_result.get("physics", {}))
    session_report = {
        "schema_version": "session_report@1",
        "session_id": "integration-smoke",
        "seed": turn_result.get("seed"),
        "max_turns": 1,
        "turns": [
            {
                "turn_index": int(turn_result.get("turn_index", 0)),
                "node_id": "integration-node",
                "node_title": "Integration Node",
                "user_state": "active",
                "teach": {
                    "teaching_block": turn_result.get("reply", ""),
                    "question": "What is the next welding check?",
                    "prompt_meta": teach_meta,
                },
                "mirror": {
                    "answer": None,
                    "meta": None,
                },
                "eval": {
                    "user_answer": turn_result.get("input", ""),
                    "mirror_answer": None,
                    "evaluation": "Smoke-test evaluation.",
                    "gaps": "Unknown in smoke test.",
                    "next_action": "continue",
                    "next_question": "What comes next?",
                    "prompt_meta": eval_meta,
                },
                "resonance": physics.get("resonance"),
                "mastery": physics.get("mastery"),
                "text_similarity": physics.get("text_similarity"),
                "mastery_delta": physics.get("mastery_delta"),
            }
        ],
    }
    return _make_event({"session_report": session_report})


def test_integration_smoke() -> None:
    cfg = XYZGLConfig(
        tutor_backend="stub",
        mirror_backend="stub",
        enable_mirror=False,
        lithosphere_enabled=True,
        persona_enabled=True,
        lithosphere_seed=42,
    )

    out_a = route_turn("test input", cfg=cfg, seed=42)
    out_b = route_turn("test input", cfg=cfg, seed=42)

    assert isinstance(out_a, dict)
    assert isinstance(out_b, dict)
    assert "physics" in out_a, "physics block missing when lithosphere is enabled"
    _assert_physics_block(dict(out_a["physics"]))
    assert dict(out_a["physics"]) == dict(out_b["physics"]), "physics must be deterministic for same seed + input"

    prompt_meta = dict(out_a.get("prompt_meta", {}))
    assert prompt_meta.get("persona_active") is True, "persona_active must be true when persona is enabled"

    vector = text_to_vector("test input", dim=cfg.lithosphere_embed_dim)
    litho = Lithosphere(
        embed_dim=cfg.lithosphere_embed_dim,
        grains=cfg.lithosphere_grains,
        seed=cfg.lithosphere_seed,
    )
    entry = litho.get_or_create("integration-node", vector, "test input")
    resonance = litho.compute_resonance("integration-node", vector)

    assert entry.node_id == "integration-node"
    assert math.isfinite(resonance)
    assert -1.0 <= resonance <= 1.0

    persona_cfg = persona_from_config(cfg)
    assert persona_cfg is not None, "persona_from_config should return a config when persona is enabled"
    instruction = build_persona_instruction(
        persona_cfg,
        mastery=float(out_a["physics"]["mastery"]),
        resonance=float(out_a["physics"]["resonance"]),
    )
    assert isinstance(instruction, str)
    assert instruction.strip()
    assert "PERSONA:" in instruction

    turn_report = _build_turn_report(out_a)
    session_report = _build_session_report(out_a)
    _assert_schema_valid(turn_report, "turn_report.schema.json")
    _assert_schema_valid(session_report, "session_report.schema.json")
