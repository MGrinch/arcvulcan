# issue_id

Shared helper for validating `--issue` IDs across tools.

## Contract

Valid issue IDs must match:

- `^ISSUE-\d{8}-\d{3}$`

Example: `ISSUE-20260201-001`

## Usage

This module is imported by tools (no standalone CLI).

