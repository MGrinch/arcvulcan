import argparse
import json
import sys

from .config import XYZGLConfig
from .router import route_turn
from .session import SessionState


def _validated_turn_index(value: int, parser: argparse.ArgumentParser) -> int:
    value = int(value)
    if value < 0:
        parser.error("--turn-index must be >= 0")
    return value


def _build_cfg(args: argparse.Namespace) -> XYZGLConfig:
    env_cfg = XYZGLConfig.from_env()
    grounding_max_snippets = args.grounding_max_snippets if args.grounding_max_snippets is not None else env_cfg.grounding_max_snippets
    grounding_max_chars = args.grounding_max_chars if args.grounding_max_chars is not None else env_cfg.grounding_max_chars
    protocol_reground_every = args.protocol_reground_every if args.protocol_reground_every is not None else env_cfg.protocol_reground_every
    return XYZGLConfig(
        tutor_backend=args.tutor_backend or env_cfg.tutor_backend,
        mirror_backend=args.mirror_backend or env_cfg.mirror_backend,
        enable_mirror=args.enable_mirror or env_cfg.enable_mirror,
        tutor_model=args.tutor_model or env_cfg.tutor_model,
        mirror_model=args.mirror_model or env_cfg.mirror_model,
        ollama_host=args.ollama_host or env_cfg.ollama_host,
        allow_remote_ollama=env_cfg.allow_remote_ollama,
        protocol_path=args.protocol_path or env_cfg.protocol_path,
        protocol_reground_every=max(0, int(protocol_reground_every)),
        grounding_mode=args.grounding_mode or env_cfg.grounding_mode,
        grounding_dir=args.grounding_dir or env_cfg.grounding_dir,
        grounding_max_snippets=max(0, int(grounding_max_snippets)),
        grounding_max_chars=max(0, int(grounding_max_chars)),
        enforce_determinism=env_cfg.enforce_determinism,
        max_chars_in=env_cfg.max_chars_in,
        max_chars_out=env_cfg.max_chars_out,
        llm_backend=args.tutor_backend or env_cfg.llm_backend,
    )


def main() -> int:
    p = argparse.ArgumentParser(prog="xyzgl")
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--turn-index", type=int, default=0)
    p.add_argument("--interactive", action="store_true", help="Read lines from stdin until 'exit'.")

    # Backends
    p.add_argument("--tutor-backend", default=None, help="stub | gemini")
    p.add_argument("--mirror-backend", default=None, help="stub | ollama")
    p.add_argument("--enable-mirror", action="store_true")
    p.add_argument("--tutor-model", default=None, help="e.g. gemini-2.5-flash")
    p.add_argument("--mirror-model", default=None, help="e.g. gwen2.5:7b")
    p.add_argument("--ollama-host", default=None, help="default http://localhost:11434")

    # Protocol + grounding
    p.add_argument("--protocol-path", default=None, help="default STABLE/ROLE_PROTOCOL.md")
    p.add_argument("--protocol-reground-every", type=int, default=None, help="N; 0 disables periodic regrounding")
    p.add_argument("--grounding-mode", default=None, help="off | local")
    p.add_argument("--grounding-dir", default=None, help="default curriculum")
    p.add_argument("--grounding-max-snippets", type=int, default=None)
    p.add_argument("--grounding-max-chars", type=int, default=None)

    p.add_argument("text", nargs="*", help="User text (non-interactive mode)")
    args = p.parse_args()
    args.turn_index = _validated_turn_index(args.turn_index, p)

    cfg = _build_cfg(args)

    if args.interactive:
        state = SessionState.new(turn_index=args.turn_index)
        while True:
            line = sys.stdin.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            if line.lower() in {"exit", "quit"}:
                break
            out = route_turn(line, seed=args.seed, cfg=cfg, turn_index=state.turn_index)
            print(json.dumps(out, indent=2, ensure_ascii=False))
            sys.stdout.flush()
            state = state.next_turn()
        return 0

    user_text = " ".join(args.text)
    out = route_turn(user_text, seed=args.seed, cfg=cfg, turn_index=args.turn_index)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
