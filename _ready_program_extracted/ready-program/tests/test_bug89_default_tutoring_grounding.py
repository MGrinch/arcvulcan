from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from xyzgl.config import XYZGLConfig
from xyzgl.grounding.prompting import build_grounding
from xyzgl.knowledge.graph import default_graph
from xyzgl.orchestrator.policies import teaching_budget
from xyzgl.orchestrator.tutor_phases import run_teach_phase


def _teach_for(node_id: str, *, grounding: bool = False):
    graph = default_graph()
    node = graph.get(node_id)
    assert node is not None
    cfg = XYZGLConfig(
        tutor_backend="stub",
        mirror_backend="stub",
        llm_backend="stub",
        enforce_determinism=True,
        grounding_mode="local" if grounding else "off",
        grounding_dir="curriculum",
    )
    return run_teach_phase(
        cfg=cfg,
        seed=7,
        turn_index=0,
        node_id=node.node_id,
        node_title=node.title,
        node_summary=node.summary,
        user_state="frustrated",
        budget=teaching_budget("frustrated"),
    )


def test_default_stub_teach_blocks_are_topic_specific_for_distinct_nodes() -> None:
    pos = _teach_for("pos_1f_vs_2f")
    arc = _teach_for("smaw_basic_arc")

    assert pos.teaching_block != arc.teaching_block
    assert "1f" in pos.teaching_block.lower()
    assert "2f" in pos.teaching_block.lower()
    assert "gravity" in pos.teaching_block.lower()
    assert "arc" in arc.teaching_block.lower()
    assert "spatter" in arc.teaching_block.lower()


def test_grounded_arc_teach_block_cites_arc_control_source() -> None:
    arc = _teach_for("smaw_basic_arc", grounding=True)

    assert "[src:demo_arc_control:0]" in arc.teaching_block
    assert "undercut" in arc.teaching_block.lower() or "arc" in arc.teaching_block.lower()


def test_build_grounding_drops_weak_unrelated_matches() -> None:
    text, meta = build_grounding(REPO_ROOT / "curriculum", "Explain 2F vs 1F in welding", max_snippets=6, max_chars=3000)

    assert text == ""
    assert meta["snippets"] == []
