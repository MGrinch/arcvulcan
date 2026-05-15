from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import targeted_sweep as sweep  # noqa: E402


def _seed_supporting_sweep_children_without_explicit_seed() -> set[str]:
    source = (TOOLS_DIR / "targeted_sweep.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    missing_explicit: set[str] = set()

    class Visitor(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
            if isinstance(node.func, ast.Name) and node.func.id == "add" and len(node.args) >= 2:
                cmd = node.args[1]
                if isinstance(cmd, ast.List) and len(cmd.elts) >= 2:
                    tool_arg = cmd.elts[1]
                    if isinstance(tool_arg, ast.Constant) and isinstance(tool_arg.value, str):
                        tokens = [elt.value for elt in cmd.elts if isinstance(elt, ast.Constant) and isinstance(elt.value, str)]
                        tool_rel = tool_arg.value
                        tool_path = REPO_ROOT / tool_rel
                        supports_seed = False
                        if tool_path.is_file():
                            tool_source = tool_path.read_text(encoding="utf-8", errors="ignore")
                            supports_seed = bool(re.search(r'add_argument\([^\n]*[\"\']--seed[\"\']', tool_source))
                        if supports_seed and "--seed" not in tokens:
                            missing_explicit.add(tool_rel)
            self.generic_visit(node)

    Visitor().visit(tree)
    return missing_explicit


def test_seed_registry_covers_current_seed_aware_sweep_children() -> None:
    implied_seed_children = _seed_supporting_sweep_children_without_explicit_seed()
    uncovered = sorted(tool for tool in implied_seed_children if tool not in sweep._SEED_AWARE_CHILD_TOOLS)
    assert uncovered == []
