SAFETY_PREFIX = "Safety first: "

def tutor_reply(user_text: str, *, seed: int | None = None) -> str:
    """Return a compact welding-tutor response.

    This is intentionally simple. Expand it with real curriculum logic later.
    """
    # Note: keep the `seed` parameter for forward-compatibility, but do not mutate global RNG state.
    _ = seed

    user_text = (user_text or "").strip()
    if not user_text:
        return SAFETY_PREFIX + "Tell me what you're working on (process, joint, position)."

    # Minimal pattern-based guidance (placeholder)
    keywords = user_text.lower()
    if "tack" in keywords and ("uneven" in keywords or "gap" in keywords):
        return (
            SAFETY_PREFIX
            + "Stop and correct fit-up before welding. Grind/trim so the joint is even, "
            + "then re-tack with consistent spacing. Uneven edges create weak toes and defects."
        )

    return (
        SAFETY_PREFIX
        + "I hear you. Share: material thickness, process (SMAW/MIG/TIG), and what defect you see."
    )
