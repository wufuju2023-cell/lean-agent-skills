#!/usr/bin/env python3
"""Check a directory of Test-harness exercises.

A starter is a fill-in worksheet: it contains bare `???` blanks and therefore
does not compile until the learner fills them. The solution twin must always
compile and report N/N passed.

For every NN_*.py starter:

  * blanks (`???` in the source)  -> expected, reported as "work left"
  * otherwise it must exit nonzero with work left (or be "solved")
  * a solution twin must exist and report N/N with exit 0
  * when the starter runs, both twins must agree on the number of checks

Files without `???` and without a "k/k passed" line are reference material
(cheatsheets) and are skipped.

Use --strict while authoring a new track: then a starter that already passes
is an error, because the exercise was shipped solved.

Usage:
    python3 check_exercises.py [--strict] [DIR]     # default: .
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

SCORE = re.compile(r"^(\d+)/(\d+) passed$", re.MULTILINE)
TIMEOUT = 120


def _run(path: Path):
    """Return (passed, total, returncode, output). (None, None) if no score."""
    try:
        p = subprocess.run(
            [sys.executable, str(path)],
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return None, None, -1, "TIMEOUT"
    m = SCORE.search(p.stdout)
    if not m:
        return None, None, p.returncode, p.stdout + p.stderr
    return int(m.group(1)), int(m.group(2)), p.returncode, p.stdout


def main(argv: list[str]) -> int:
    strict = "--strict" in argv
    args = [a for a in argv if a != "--strict"]
    root = Path(args[1] if len(args) > 1 else ".").resolve()
    if not root.is_dir():
        print(f"not a directory: {root}")
        return 2

    starters = sorted(p for p in root.glob("*.py") if not p.stem.endswith("_solution"))

    problems: list[str] = []
    rows: list[tuple[str, str, str, str]] = []

    for st in starters:
        src = st.read_text(encoding="utf-8")
        blanks = "???" in src
        passed, total, rc, out = _run(st)
        twin = st.with_name(st.stem + "_solution.py")

        if total is None and not blanks:
            rows.append((st.name, "reference", "-", "skipped (no harness)"))
            continue

        if not twin.exists():
            problems.append(f"{st.name}: no solution twin ({twin.name})")
            rows.append(
                (st.name, "exercise", "blanks" if blanks else f"{passed}/{total}",
                 "MISSING SOLUTION")
            )
            continue

        if total is None:
            # bare ??? blanks: the file is not supposed to compile yet
            if rc == 0:
                problems.append(f"{st.name}: contains ??? but ran successfully")
            if "SyntaxError" not in out:
                problems.append(
                    f"{st.name}: expected a SyntaxError from the blanks, got rc={rc}"
                )
            rows.append((st.name, "exercise", "blanks", "work left (???)"))
            expected_total = None
        else:
            if rc != 0 and passed < total:
                status = "ok (work left)"
            elif rc == 0 and passed == total:
                status = "SHOULD FAIL" if strict else "solved"
                if strict:
                    problems.append(
                        f"{st.name}: starter already passes {passed}/{total}"
                    )
            else:
                status = "ODD"
                problems.append(f"{st.name}: inconsistent rc={rc} with {passed}/{total}")
            rows.append((st.name, "exercise", f"{passed}/{total}", status))
            expected_total = total

        s_passed, s_total, s_rc, _s_out = _run(twin)
        if s_total is None:
            problems.append(f"{twin.name}: no harness output")
            rows.append((twin.name, "solution", "-", "NO HARNESS"))
            continue

        s_ok = s_rc == 0 and s_passed == s_total
        rows.append(
            (twin.name, "solution", f"{s_passed}/{s_total}", "ok" if s_ok else "FAILS")
        )
        if not s_ok:
            problems.append(
                f"{twin.name}: expected 0 failures, got rc={s_rc} "
                f"and {s_passed}/{s_total}"
            )
        if expected_total is not None and expected_total != s_total:
            problems.append(f"{st.name}: {expected_total} checks but twin has {s_total}")

    width = max((len(r[0]) for r in rows), default=10)
    print(f"{'file':<{width}}  {'role':<9} {'score':<9} status")
    print("-" * (width + 34))
    for name, role, score, status in rows:
        print(f"{name:<{width}}  {role:<9} {score:<9} {status}")

    if problems:
        print("\nproblems:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("\nall exercises behave as expected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
