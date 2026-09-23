# arcvulcan — what the project does

The tutor chooses a welding topic, teaches and asks a question, then uses your answer to decide whether to probe further or move on.

## A welding tutor that follows your reasoning

**Working code.** Tutor prototype on master; default replies are simulated. Live teaching and learning benefit were not tested.

![The tutor chooses a welding topic, teaches and asks a question, then uses your answer to decide whether to probe further or move on.](overview.svg)

[Open the full-size picture](overview.svg) · [Editable diagram source](overview.mmd)

1. ArcVulcan is a welding-tutor project, not merely its public landing page. A fuller implementation is preserved on the master branch.
2. The session code chooses a topic, produces teaching and a question, and collects the learner’s real reply.
3. An optional helper predicts an answer for comparison; it is not the learner and does not supply evidence that the learner understands.
4. Follow-up questions stay on the topic until the programmed rule allows moving on. Required-word checks and heuristic progress values are software decisions, not validated proof of mastery.

**The questions in the picture:**

- **Probe further or move on?** Compare the reply with the topic’s required ideas.

[Shape and color key](STYLE.md) · [Source evidence and review](DESIGN-REVIEW.md) · [What was checked](VERIFICATION.md)
