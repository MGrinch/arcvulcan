# Project Atlas — diagram standard

Research completed 23 September 2026. Scope: repository documentation, with one consistent visual language across the selected GitHub projects.

## Reader outcome

Within a minute, Misha can identify what the project contains, where a task starts, what transforms or stores information, and where the result goes. A diagram is an overview of meaningful responsibilities, not a drawing of every file. Detailed inventories and evidence accompany the overview.

## Research and decisions

- [C4 notation](https://c4model.com/diagrams/notation): state scope, identify element responsibilities, label directional connections, explain visual notation.
- [C4 review checklist](https://c4model.com/diagrams/checklist): review element meaning, relationship direction and consistency.
- [C4 diagram levels](https://c4model.com/diagrams): choose only useful levels; do not force every repository into four diagrams.
- [GitHub diagram support](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/creating-diagrams): Markdown can display Mermaid. Use its established flowchart subset for editable source.
- [Mermaid theming](https://mermaid.js.org/config/theming.html): keep an explicit shared theme and role classes rather than relying on changing defaults.
- [W3C use of color](https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html): pair colors with text and shape; color alone never carries a distinction.

These sources guide the design. The following palette and limits are project decisions, not claims that C4 mandates them.

## Shared visual language

White canvas, dark navy text (#172033), generous spacing, clear title and short subtitle. Prefer a top-to-bottom flow; use left-to-right only where it shortens the reading path. Target 5–12 responsibility groups; split a dense interaction into a second view if necessary. Never shrink text to fit a giant graph.

| Role | Fill | Border | Meaning also written in label |
| --- | --- | --- | --- |
| Person / entry | #E0F2FE | #0369A1 | Person, interface, or entrypoint |
| Processing | #EDE9FE | #6D28D9 | Logic, transformation, service |
| Data / artifact | #DCFCE7 | #15803D | Stored input, state, output |
| Rules / checks | #FEF3C7 | #B45309 | Policy, validation, tests |
| External / reference | #F1F5F9 | #475569 | Outside this repository or reference material |

Use rounded boxes for entrypoints, rectangles for logic and documents, cylinders only for actual stores. Every node states a responsibility. Every arrow has a concrete verb and a direction. Solid arrows mean an implemented relationship or directly documented content relationship. Dashed arrows mean a planned or inferred relationship and must say which. Layout-only positioning never invents a connection. Static dependency, runtime data flow, human workflow and document organization are explicitly distinguished.

## Per-repository order of work

1. Freeze default-branch commit, visibility, tree, and relevant repository instructions. Work in isolated task-owned copies.
2. Inspect README and tree, then follow entrypoints, imports, producers/consumers, storage and tests. Do not execute project scripts.
3. Write a brief naming audience, actual project kind, node responsibilities, each intended arrow, evidence, scope and exclusions.
4. Attack the weakest assumptions: does the implementation exist; does an arrow describe a real connection; is a name only a historical plan; is the default branch correct; does an external dependency actually run; have duplicate/generated files been mistaken for components?
5. Read the specific source that could disprove each important assumption. Record the finding and resolution. Revise the brief before drawing.
6. Generate an editable diagram plus a stable rendered preview. Add an evidence table and a concise accessible description. Preserve names and distinctions already used by the project.
7. Verify syntax/rendering, label readability, arrow meaning, evidence links and document-only diff. An overview does not prove runtime health.
8. Commit only the reviewed documentation. Refresh the remote head before publication, push without force, then read back published files and record the commit.

## Delivery and stop conditions

Each selected writable repository gets `docs/project-atlas/README.md`, editable diagram source, rendered preview, and `DESIGN-REVIEW.md` containing the original brief, challenges, evidence and revised instructions. Add a short discoverability link to the existing root README when safe. Empty or document-only repositories receive an honest content map instead of invented runtime architecture.

Stop a repository on access failure, conflicting changes, protected-branch rejection, secret exposure, or insufficient evidence for an asserted connection. Resolve gaps by reading more source or by narrowing/labelling the claim; do not silently guess. Completion requires publication readback for every selected repository, with any exceptions explicitly accounted for.

Rollback: each publication is one documentation-only commit; revert that commit to remove this addition while retaining later changes. Never reset or force-push a user's branch.

## Skill adaptation

The repo-docs skill supplies behavior-first reading, two evidence passes, and Confirmed / Inferred / Planned / Unknown distinctions. This request is specifically a diagram package, so its larger guide scaffold and agent-routing edits are out of scope. Verification targets this diagram package rather than claiming its full-guide validator passed.
