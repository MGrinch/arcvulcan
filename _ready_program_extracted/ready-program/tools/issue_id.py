#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys
from datetime import datetime

# Keep zip-distributed repos clean (avoid creating __pycache__/ during tool runs)
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True

_ISSUE_RE = re.compile(r"^ISSUE-\d{8}-\d{3}$")

def validate_issue_id(issue_id: str) -> str | None:
    """Return an error string if invalid, else None."""
    if not issue_id:
        return "missing --issue (expected ISSUE-YYYYMMDD-NNN)"
    raw = issue_id.strip()
    if not _ISSUE_RE.match(raw):
        return "invalid --issue (expected ^ISSUE-\\d{8}-\\d{3}$)"
    date_part = raw.split("-")[1]
    try:
        datetime.strptime(date_part, "%Y%m%d")
    except ValueError:
        return "invalid --issue date (expected real YYYYMMDD calendar date)"
    return None
