---
name: Test-harness
description: Build self-contained Python exercise files that teach a topic from zero and grade themselves — lesson docstring, a "predict the output" quiz (CASES/ANSWERS), "implement it" tasks with asserts, one harness that prints ok/TODO/FAIL and exits nonzero, plus a _solution twin. Use when writing or reviewing beginner exercises, when a learner wants practice files with solutions, or when turning a lesson into a runnable .py. Triggers: test harness, exercise, 练习题, 自测, predict the output, solution twin, autograde, teaching python, python exercise, 学习脚本, 批改, 从零学.
---

# Test-harness: self-grading exercise files

A repeatable recipe for exercise files a human can learn from without a teacher:
the file explains the idea, asks for a prediction, asks for code, and then
grades itself. One command, no dependencies, no test framework.

## 0. When to use it

Use this when the deliverable is **practice material**, not production tests:

- "write me exercises to learn X, with solutions";
- a lesson that should be runnable rather than read;
- converting notes into drills;
- checking that a learner's edit actually does what the lesson claims.

Do **not** use it for a real project's test suite (use pytest), and do not put
network, GPU or long-running work in Part A cases.

## 1. The contract

Every exercise file obeys these rules:

| Rule | Why |
| --- | --- |
| One topic per file, named `NN_topic.py` (`01`…`07`) | ordered track, obvious next step |
| Fully self-contained: stdlib only, no imports between files | it still works if the learner moves one file |
| `python3 NN_topic.py` runs the whole thing from any cwd | zero setup |
| Exit code **0** iff everything passed, **1** otherwise | any runner or CI can check it |
| Blanks are a **bare `???`**, never `"???"` | the learner replaces one token, no quote surgery |
| A starter with blanks does not compile | `???` is not valid syntax; Python points at the first blank |
| Lesson first, tasks second | never a bare exercise sheet |
| Exact comparison (`==` on values, `is` on exception classes) | "looks right" is not feedback |
| A `_solution.py` twin next to every exercise | learner can unblock without asking |

The unit of work is a **track**: `00` cheatsheet (no tasks, just a map),
`01`–`06` one concept each, `07` boss round that integrates them. Eight files
is a good size; each should take 10–20 minutes.

## 2. Anatomy of one file

```
"""NN - topic
==========

<lesson: what it is, why it matters, 5-15 short paragraphs,
 runnable examples inline, the 2-3 traps called out>

Part A: predict the exact output.
Part B: implement the functions below.
"""

# ---- Part A: quiz -------------------------------------------------------
CASES = [("label = source text", lambda: <expression>), ...]
ANSWERS = [???, ...]            # one per case; replace each ??? with an answer

# ---- Part B: code -------------------------------------------------------
def task(args):
    """task(example) -> expected"""
    raise NotImplementedError("task")

# ---- harness: never edited ---------------------------------------------
def _eq(got, want): ...
def _run(part_b): ...
if __name__ == "__main__":
    _run([("label", _t_task), ...])
```

## 3. Part A: predict the output

Prediction is the teaching device: a learner who guesses `'3'` for `f"{1+1}"`
has learned something the moment the harness disagrees.

Rules:

1. `CASES` is a list of `(label, zero-arg callable)`. The **label is the source
   text** the learner reads; it must be answerable without running anything.
2. `ANSWERS` has exactly one entry per case, and each blank is a **bare
   `???`**, never the string `"???"`:

   ```python
   ANSWERS = [
       ???,  # 1   -> 3
       ???,  # 2   -> ValueError
   ]
   ```

   The learner replaces the three characters with an expression: `3`,
   `[1, 2]`, `None`, `ValueError`. Because `???` is not valid Python, the
   starter does not compile until every blank is filled. That is deliberate:
   one token to replace, no quote surgery, and Python stops at the first blank
   left. If the blank were `"???"`, replacing only the `?` characters would
   leave `"ValueError"` - a string, which never equals the class.
3. Compare **values**, not truthiness: `got == want`. For strings that means
   spaces and quotes matter, which is the point in formatting/`repr` lessons.
4. For an error-recognition quiz, compare **classes**: `got is want`, where
   `want` is `ValueError`, `None` (no error), etc.
5. Each case must be deterministic: no `random`, no `time`, no cwd-relative
   files, no network. If the lesson is about files, build them with
   `tempfile` inside the test, never in the case.
6. Print `got` on failure (and `want` after the guess). Never print the answer
   in the label — that is the quiz.

Two case styles:

```python
CASES = [
    ('f"{1 + 1}"',            lambda: f"{1 + 1}"),          # value == value
    ('int("x")',              lambda: int("x")),            # error == class
]
ANSWERS = ["2", ValueError]
```

## 4. Part B: implement (or fix)

Two genres, both useful:

- **implement** — the stub `raise NotImplementedError("task")`. The harness
  catches it and prints `TODO`, so an untouched file reports progress instead
  of a wall of red.
- **fix** — the function is present but buggy. The learner runs it, reads the
  real `FAIL/ERROR <Type>: <message>`, and repairs it. Best for error-family
  lessons; never mix more than one bug per function.

Rules for the checks:

- 2–3 asserts per task, always including one edge case (`[]`, `0`, `""`, a
  negative number).
- Build fresh data **inside** each test function; never share a mutable list
  between checks.
- `_eq` should print `repr`, so `'  ab'` versus `' ab'` is visible.
- Do not assert on `type(...) is int` unless the lesson is about types — and
  then say so.

## 5. The harness (copy verbatim)

```python
def _eq(got, want):
    assert got == want, f"\n       got  {got!r}\n       want {want!r}"


def _run(part_b):
    assert len(CASES) == len(ANSWERS), "ANSWERS must have one entry per case"
    bad = 0
    print("Part A - predict the output\n")
    for i, ((label, fn), want) in enumerate(zip(CASES, ANSWERS), 1):
        try:
            got = fn()
        except Exception as e:            # noqa: BLE001
            print(f"{i:2}. ERROR {label}: {type(e).__name__}: {e}")
            bad += 1
            continue
        ok = got == want
        print(f"{i:2}. {'ok  ' if ok else 'FAIL'}  {label:<26} -> {got!r}")
        if not ok:
            print(f"       want {want!r}")
        bad += 0 if ok else 1

    print("\nPart B - implement\n")
    for label, fn in part_b:
        try:
            fn()
        except NotImplementedError:
            print(f"    TODO  {label}")
            bad += 1
        except AssertionError as e:
            print(f"    FAIL  {label}{e}")
            bad += 1
        except Exception as e:            # noqa: BLE001
            print(f"    ERROR {label}: {type(e).__name__}: {e}")
            bad += 1
        else:
            print(f"    ok    {label}")

    total = len(CASES) + len(part_b)
    print(f"\n{total - bad}/{total} passed")
    if bad:
        raise SystemExit(1)
```

Why each piece:

- There is no `TODO` branch in Part A: a bare `???` cannot reach the harness,
  because the file does not compile while any blank is left. Python's
  `SyntaxError` is the "not answered yet" reporter.
- `except NotImplementedError` comes **before** `except AssertionError`
  (otherwise `TODO` becomes `FAIL`) — Part B still uses stubs, so it *does*
  need a TODO path.
- Catching `Exception` in Part A and printing `type(e).__name__` is what lets a
  `SyntaxError` case work, and it tells the learner what actually fired.
- `raise SystemExit(1)` at the end (not inside the loop) gives one clean status.
- `assert len(CASES) == len(ANSWERS)` kills the classic silent truncation when
  someone adds a case and forgets an answer.

## 6. The solution twin

`NN_topic_solution.py` is a copy with two changes only:

1. `ANSWERS` filled in, each with a short comment saying *why*;
2. Part B implemented.

Keep the harness byte-identical so the two reports are comparable. Never import
the solution from the exercise, and never delete cases from one twin. When a
test changes, change both and rerun both.

For a **fix-the-bug** exercise the starter's Part B is the buggy code (not a
stub) and the solution's is the repaired code; add a comment at the top of the
solution naming the exception each bug produced.

## 7. Difficulty curve for a track

| File | Content | Part A | Part B |
| --- | --- | --- | --- |
| `00_cheatsheet.py` | map of the topic, prints a table, no tasks | — | — |
| `01_basics.py` | literals, the mental model | 8–10 cases | 3 tasks |
| `02…06` | one operator/method family each | 10 cases | 3 tasks |
| `07_boss.py` | integrates everything | 8–10 recap | 4–5 tasks |

Part A should contain at least two cases the learner will get wrong. That is
the value of the file. Put the trap in the lesson text too, so the failure is a
reminder rather than a surprise.

## 8. Pitfalls

- **`zip(CASES, ANSWERS)` truncates silently** — keep the length assert.
- **Shared mutable state** — a test that appends to a module-level list makes
  the next test depend on order. Build data inside the test.
- **Floats** — `0.1 + 0.2 == 0.3` is `False`. Compare formatted strings
  (`f"{x:.2f}"`) or use a tolerance.
- **Labels containing f-strings** — the label is itself a string; escape its
  quotes correctly and run the file, because a broken label is a `SyntaxError`
  in the harness, not in the case.
- **Spoilers** — a label like `'f"{1+1}" -> 2'` destroys the quiz.
- **Filesystem cases** — use `tempfile.TemporaryDirectory()`; never write into
  the repo and never depend on cwd.
- **`open()` without `with`** — leaks handles in tests and teaches the wrong
  habit in file lessons.
- **Over-broad `except`** in learner-facing example code — the harness may catch
  broadly, but the code being taught must not (that is a lesson of its own).
- **A starter that crashes for the wrong reason** — blanks are *supposed* to
  produce `SyntaxError`, but a typo in `CASES`, a mis-escaped label, or a
  bad class name in `ANSWERS` produces a different traceback. Run the starter
  once and read the message: it should mention the first `???` line.
- **Quoting the blank** — `ANSWERS = ["???"]` makes the learner produce
  `"ValueError"` (a string) by deleting only the question marks. Write `???`
  bare; see §3.
- **Nondeterminism** — dict order is insertion-ordered since 3.7, but set
  iteration is not; sort before printing or comparing.

## 9. Verification ritual (mandatory)

```bash
cd <track-dir>
grep -n '"???"' *.py || echo "no quoted blanks"     # must print the second line
python3 -m py_compile *_solution.py                 # solutions parse
for f in *_solution.py; do python3 "$f" >/dev/null; echo "$f -> $?"; done  # 0
python3 <starter>.py 2>&1 | tail -3                 # SyntaxError points at ???
python3 ~/.config/opencode/skills/Test-harness/assets/check_exercises.py .
```

Expected shape:

- starter with blanks: `SyntaxError`, exit 1, reported as `work left (???)`;
- once filled: `0/N passed` with TODOs for Part B, or its documented partial;
- solution: `N/N passed`, exit 0;
- same `N` in both twins;
- `check_exercises.py` prints a table and exits 0.

`assets/check_exercises.py` automates the loop, recognises blank worksheets
(no score + `???` in the source), checks the twins' totals match, and skips
cheatsheets that have no harness.

## 10. Reference implementations on this machine

Live examples of the pattern (read one before writing a new track):

- `~/文档/learn-python/Exercise/try-except/` — `try/except/else/finally`,
  custom exceptions, EAFP/retry, a context manager.
- `~/文档/learn-python/Exercise/Errors/` — one exception family per file,
  Part A is "name the class", Part B is "fix the crash".
- `~/文档/learn-python/Exercise/f-string/` — output-prediction track with
  exact `repr` comparison.
- `~/文档/learn-python/Exercise/List/` — the track built from this skill's
  template (`01`…`07` plus cheatsheet).

## 11. Definition of done

- [ ] lesson docstring reads standalone, no "see the slides";
- [ ] cheatsheet file exists and runs (`00`);
- [ ] every exercise has `CASES` + `ANSWERS` and 3+ tasks;
- [ ] every blank is a bare `???` (grep for `"???"` returns nothing);
- [ ] starter fails with a `SyntaxError` naming the first blank;
- [ ] solution reports `N/N` and exits 0;
- [ ] counts match between twins;
- [ ] `py_compile` clean, no `SyntaxWarning`;
- [ ] no `input()`, no network, no absolute paths, no shared mutable state;
- [ ] the two traps you care about appear both in the lesson and in Part A.
