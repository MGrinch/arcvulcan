from xyzgl.orchestrator.policies import TeachingBudget
from xyzgl.orchestrator.phases import EvalPhase, TeachPhase
from xyzgl.orchestrator.session_loop import SessionReport, TurnRecord


def test_session_report_sanitizes_prompt_meta_before_export() -> None:
    teach = TeachPhase(
        node_id="n1",
        user_state="flow",
        budget=TeachingBudget(min_sentences=1, max_sentences=2, density="light"),
        teaching_block="Teach.",
        question="Question?",
        prompt_meta={
            "protocol_regrounded": True,
            "protocol_path": "/tmp/private/protocols/runtime.md",
            "grounding": {"grounding_dir": "/Users/misha/private/corpus", "source": "ok"},
            "backend_error": "Authorization: Bearer sk-abcdefghijklmnopqrstuvwxyz12",
            "persona_injected": True,
        },
        persona_injected=True,
    )
    evaluation = EvalPhase(
        node_id="n1",
        user_answer="answer",
        mirror_answer=None,
        evaluation="good",
        gaps="none",
        next_action="PROBE",
        next_question="next?",
        prompt_meta={
            "protocol_regrounded": False,
            "protocol_path": "C:\\secret\\protocols\\eval.md",
            "grounding": {"grounding_dir": "D:\\secret\\grounding", "source": "ok"},
            "backend_error": "cookie: session=abcdef",
            "physics": {"resonance": 0.9, "backend_path": "/tmp/private/backend"},
            "persona_active": True,
        },
    )
    turn = TurnRecord(
        turn_index=0,
        node_id="n1",
        node_title="Node",
        user_state="flow",
        teach=teach,
        mirror_answer=None,
        mirror_meta=None,
        eval=evaluation,
        telemetry=None,
        close_gate=None,
    )

    out = SessionReport(session_id="s1", seed=1, max_turns=1, turns=[turn]).to_json()
    exported_teach = out["turns"][0]["teach"]["prompt_meta"]
    exported_eval = out["turns"][0]["eval"]["prompt_meta"]

    assert exported_teach["protocol_path"] == "<abs>/runtime.md"
    assert exported_teach["grounding"]["grounding_dir"] == "<abs>/corpus"
    assert exported_teach["backend_error"] == "backend_error_redacted"
    assert exported_teach["persona_injected"] is True

    assert exported_eval["protocol_path"] == "<abs>/eval.md"
    assert exported_eval["grounding"]["grounding_dir"] == "<abs>/grounding"
    assert exported_eval["backend_error"] == "backend_error_redacted"
    assert exported_eval["persona_active"] is True
    assert exported_eval["physics"]["backend_path"] == "<abs>/backend"
