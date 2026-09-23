# arcvulcan — diagram brief and adversarial review

Inspected default branch: `gh-pages`. Source baseline: `fdc952370dac56878f813cd4a6be927bcbabef0e`. Review date: 2026-09-23.

Review method: an explicit adversarial self-review followed by targeted source inspection. This is not represented as an independent reviewer verdict.

The brief and review were written before rendering. Shared design instructions are in [STYLE.md](STYLE.md).

## Overview — initial brief

Create a basic map for Misha showing the major responsibilities and how a task or piece of information moves between them. Candidate view: **Static landing-page composition**.

The default gh-pages branch is one static HTML landing page describing the ArcVulcan project.

Proposed responsibility groups: Landing page — index.html, Page sections — Project explanation, Embedded CSS — Layout and appearance, Navigation links — Linked destinations.

### Challenge the weakest assumption

**Challenge:** Could this picture imply more implementation, automation, authority, or runtime certainty than the repository proves?

**Finding after targeted reading:** The current default branch contains only index.html. Marketing descriptions of a tutor do not demonstrate the tutor implementation on this branch.

**Revised creation instructions:** Draw the landing page as static HTML and CSS. Do not infer the full tutoring system from advertised features or older branches.

### Connection review

Every relationship below has a named supporting file or the complete tree. Source relationships establish static architecture; documented agent steps establish a workflow contract. Neither proves a running service.

| From → to | Intended meaning | Evidence |
| --- | --- | --- |
| Landing page → Page sections | contains static markup | [index.html](https://github.com/MGrinch/arcvulcan/blob/fdc952370dac56878f813cd4a6be927bcbabef0e/index.html) |
| Embedded CSS → Landing page | styles page elements | [index.html](https://github.com/MGrinch/arcvulcan/blob/fdc952370dac56878f813cd4a6be927bcbabef0e/index.html) |
| Landing page → Navigation links | offers navigation | [index.html](https://github.com/MGrinch/arcvulcan/blob/fdc952370dac56878f813cd4a6be927bcbabef0e/index.html) |

### Final scope and residual uncertainty

Other branches and deployed-site availability are not asserted.

The overview groups related files. It does not assert that every internal function call is drawn. Runtime health and user acceptance of the visual remain unverified by source inspection.

## Evidence traversal

Pass 1: freeze branch and commit; inspect the tracked tree, project entrypoints and instructions; classify the repository.

Pass 2: inspect the source/contract behind disputed connections; inspect ZIP members where present; revise the diagram model. Hashes below make those exact inputs recoverable.

| Evidence input | SHA-256 |
| --- | --- |
| [index.html](https://github.com/MGrinch/arcvulcan/blob/fdc952370dac56878f813cd4a6be927bcbabef0e/index.html) | `557ed3ae334bea4b7ea880d9f0042fd912d86a7ead6b4ad8872e8db82d86e68f` |

## Repository coverage

All tracked top-level surfaces were inventoried. The responsibility diagrams focus on the workflows stated above; the counts below preserve visibility of supporting and historical material without inventing runtime edges. ZIP member inventories appear separately when relevant.

| Surface | Tracked files |
| --- | ---: |
| `(root files)` | 1 |

## Publication and rollback

The authorized publication is a documentation-only commit on the verified default branch. Refresh the remote head before push and verify the published bytes afterward. Revert that single commit to remove the atlas; never force-push or reset shared history.

Repository instructions and existing full guides are not rewritten. This package adapts repo-docs evidence and review rules to the requested diagram deliverable; it does not claim the full-guide validator passed.
