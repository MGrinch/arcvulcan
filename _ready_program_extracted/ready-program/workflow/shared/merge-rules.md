# Merge Rules

- Window `16` precompiles outputs from windows `1` through `7`.
- Window `17` precompiles outputs from windows `8` through `15`.
- Window `18` merges outputs from windows `16` and `17`.
- Merge round `N` consumes round `N` from each upstream window.
- If an upstream window has already exhausted its queue before round `N`, the merger may synthesize a no-op package for that upstream.
- If an upstream window is not finished but has not produced round `N` yet, the merge is not ready.
- Apply packages in upstream window order.
- Do not silently overwrite overlapping files from different non-noop packages. Resolve the overlap intentionally or stop and report it.
- When multiple packages touch the same contract, favor the change that best preserves truthful artifacts, fail-closed semantics, and the current cold-stop state.
- The merged package should include the union of upstream package files plus any extra conflict-resolution files you changed.
