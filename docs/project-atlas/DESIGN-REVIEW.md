# What these pictures are based on

Read against `gh-pages` at `b7e67d20948d293005a97140bf98e4e33969ba10` on 23 September 2026. The previous pictures focused too heavily on repository mechanics; these replacements follow the project's work and useful results.

Fresh reading challenged what the project actually does, what is only intended, what it remembers, and which claimed results are supported. Separate agents reviewed selected weak claims. The evidence links below pin the source used; an archived member is named separately because GitHub cannot browse inside its ZIP.

## A welding tutor that follows your reasoning

**Mistaken assumption challenged:** Because the default branch has a landing page, the project itself is only a website.

**What rereading changed:** Branch inspection found preserved implementation on master. This view uses pinned product code rather than HTML structure or unsupported marketing claims.

**Still uncertain:** The current master snapshot has not been executed here. Real-model readiness, certification alignment and learning benefit are unverified.

| Evidence | Source | What it supports |
| --- | --- | --- |
| E1 | [MGrinch/arcvulcan@de128d8ec2af7c69cf6ea38fb8d69745a5eee149:_ready_program_extracted/ready-program/NORTH_STAR.md](https://github.com/MGrinch/arcvulcan/blob/de128d8ec2af7c69cf6ea38fb8d69745a5eee149/_ready_program_extracted/ready-program/NORTH_STAR.md) | Describes Ontario welding tutor purpose and roles; explicitly states default deterministic tutor stub and intended real-backend replacement. |
| E2 | [MGrinch/arcvulcan@de128d8ec2af7c69cf6ea38fb8d69745a5eee149:_ready_program_extracted/ready-program/xyzgl/orchestrator/session_loop.py](https://github.com/MGrinch/arcvulcan/blob/de128d8ec2af7c69cf6ea38fb8d69745a5eee149/_ready_program_extracted/ready-program/xyzgl/orchestrator/session_loop.py) | Actual session selects topics, teaches, optionally predicts, receives real answers, probes, checks required keywords and records topic updates. |
| E3 | [MGrinch/arcvulcan@de128d8ec2af7c69cf6ea38fb8d69745a5eee149:_ready_program_extracted/ready-program/documentation/orchestrator/ai_session_loop.md](https://github.com/MGrinch/arcvulcan/blob/de128d8ec2af7c69cf6ea38fb8d69745a5eee149/_ready_program_extracted/ready-program/documentation/orchestrator/ai_session_loop.md) | Describes teaching, optional prediction, real user reply and evaluation; actual source is used where older docs differ. |

### Connections

| From → to | What passes or happens | Source |
| --- | --- | --- |
| Your current skill map → Choose a welding topic | Topic progress | E2 |
| Choose a welding topic → Explain and ask | The topic to teach | E2 |
| Explain and ask → Your actual answer | Teaching and a question | E2 |
| Explain and ask → Predict a possible answer | The same question | E2 |
| Predict a possible answer → Probe further or move on? | Optional predicted answer | E2, E3 |
| Your actual answer → Probe further or move on? | The real answer | E2 |
| Probe further or move on? → Ask a focused follow-up | More reasoning needed | E2, E3 |
| Ask a focused follow-up → Your actual answer | A focused next question | E2 |
| Probe further or move on? → Your current skill map | Updated topic progress | E2 |
| Probe further or move on? → A record of the lesson | Teaching and decision history | E2 |

## Verification and rollback

Every source input has its SHA-256 and source commit in [model.json](model.json). The diagram check covers source references, relationships, standalone SVG, layout and the documentation diff. It does not establish live operation or product effectiveness.

Revert this documentation commit to restore the previous pictures. Do not reset shared history.
