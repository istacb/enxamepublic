"""Reject new Ruff violations while legacy lint cleanup is tracked separately."""
import json
from pathlib import Path
import sys


def main() -> int:
    path = Path(sys.argv[1])
    allowed = int(sys.argv[2])
    issues = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(issues, list):
        raise ValueError("Ruff must produce a JSON array")
    count = len(issues)
    print(f"Ruff debt: {count} violations (baseline ceiling: {allowed})")
    if count > allowed:
        print(f"ERROR: {count - allowed} new lint violations over the upstream baseline")
        return 1
    print("PASS: Ruff violations did not increase")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
