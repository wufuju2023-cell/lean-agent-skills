"""NN - topic
===========

<2-4 sentences: what this is and why the learner should care.>

The rules, with runnable examples:

    <example 1>        -> <result>
    <example 2>        -> <result>

<The one trap people hit.>
<The second trap.>

Part A: replace every bare ??? with your answer (as code, not a string).
Part B: implement the two functions.

The file does not run until every ??? is gone - Python points at the first
blank you left. Run:  python3 NN_topic.py
"""

# ==========================================================================
# Part A - predict the output
# ==========================================================================
CASES = [
    ("len([1, 2, 3])",        lambda: len([1, 2, 3])),
    ('"ab" + "c"',            lambda: "ab" + "c"),
]

# Fill each ??? with your answer (as code: 3, [1, 2], None, ValueError).
# The file cannot run until every blank is filled.
ANSWERS = [
    ???,  # 1
    ???,  # 2
]


# ==========================================================================
# Part B - implement these
# ==========================================================================
def total(items):
    """total([1, 2, 3]) -> 6; total([]) -> 0."""
    raise NotImplementedError("total")


def longest(items):
    """longest(["ab", "c", "def"]) -> "def"."""
    raise NotImplementedError("longest")


# --------------------------------------------------------------------------
# harness - do not edit
# --------------------------------------------------------------------------
def _eq(got, want):
    assert got == want, f"\n       got  {got!r}\n       want {want!r}"


def _run(part_b):
    assert len(CASES) == len(ANSWERS), "ANSWERS must have one entry per case"
    bad = 0
    print("Part A - predict the output\n")
    for i, ((label, fn), want) in enumerate(zip(CASES, ANSWERS), 1):
        try:
            got = fn()
        except Exception as e:  # noqa: BLE001
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
        except Exception as e:  # noqa: BLE001
            print(f"    ERROR {label}: {type(e).__name__}: {e}")
            bad += 1
        else:
            print(f"    ok    {label}")

    total_checks = len(CASES) + len(part_b)
    print(f"\n{total_checks - bad}/{total_checks} passed")
    if bad:
        raise SystemExit(1)


def _t_total():
    _eq(total([1, 2, 3]), 6)
    _eq(total([]), 0)


def _t_longest():
    _eq(longest(["ab", "c", "def"]), "def")
    _eq(longest(["x"]), "x")


if __name__ == "__main__":
    _run([
        ("total sums and handles []", _t_total),
        ("longest picks the longest", _t_longest),
    ])
