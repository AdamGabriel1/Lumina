"""Testes de std/sort + `for i, x in arr`."""
import os
import pathlib
import subprocess
import sys
import tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _run(src, timeout=30):
    with tempfile.NamedTemporaryFile("w", suffix=".lm", delete=False) as f:
        f.write(src)
        path = f.name
    try:
        r1 = subprocess.run(
            [sys.executable, "-m", "lumina_cli", "build", path],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=timeout,
        )
        assert r1.returncode == 0, f"Build falhou:\n{r1.stdout}\n{r1.stderr}"
        binary = path[:-3]
        r2 = subprocess.run([binary], capture_output=True, text=True, timeout=timeout)
        return r2.stdout, r2.returncode
    finally:
        for p in (path, path[:-3] + ".ll", path[:-3]):
            if os.path.exists(p):
                os.remove(p)


def _lines(out, wanted):
    return [l.strip() for l in out.splitlines() if l.strip() in wanted]


# ============================================================
# for i, x in arr
# ============================================================
def test_forin_with_index():
    src = (
        'fn main() -> int:\n'
        '    let nums = [10, 20, 30]\n'
        '    for i, n in nums:\n'
        '        print(i, n)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "0 10" in out
    assert "1 20" in out
    assert "2 30" in out


def test_forin_with_index_sum():
    src = (
        'fn main() -> int:\n'
        '    let nums = [5, 10, 15, 20]\n'
        '    mut weighted = 0\n'
        '    for i, n in nums:\n'
        '        weighted += i * n\n'
        '    print(weighted)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    # 0*5 + 1*10 + 2*15 + 3*20 = 0 + 10 + 30 + 60 = 100
    assert "100" in out


def test_forin_index_only_still_works():
    """`for n in arr:` continua funcionando."""
    src = (
        'fn main() -> int:\n'
        '    let nums = [1, 2, 3]\n'
        '    mut total = 0\n'
        '    for n in nums:\n'
        '        total += n\n'
        '    print(total)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "6" in out


# ============================================================
# std/sort
# ============================================================
def test_sort_basic():
    src = (
        'import "std/sort"\n'
        '\n'
        'fn main() -> int:\n'
        '    mut arr = alloc(5)\n'
        '    arr[0] = 5\n'
        '    arr[1] = 2\n'
        '    arr[2] = 8\n'
        '    arr[3] = 1\n'
        '    arr[4] = 9\n'
        '    sort(arr, 5)\n'
        '    for x in arr:\n'
        '        print(x)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert _lines(out, {"1", "2", "5", "8", "9"}) == ["1", "2", "5", "8", "9"]


def test_sort_already_sorted():
    src = (
        'import "std/sort"\n'
        '\n'
        'fn main() -> int:\n'
        '    mut arr = alloc(4)\n'
        '    arr[0] = 1\n'
        '    arr[1] = 2\n'
        '    arr[2] = 3\n'
        '    arr[3] = 4\n'
        '    sort(arr, 4)\n'
        '    print(is_sorted(arr, 4))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "1" in out


def test_sort_reverse():
    src = (
        'import "std/sort"\n'
        '\n'
        'fn main() -> int:\n'
        '    mut arr = alloc(4)\n'
        '    arr[0] = 4\n'
        '    arr[1] = 3\n'
        '    arr[2] = 2\n'
        '    arr[3] = 1\n'
        '    sort(arr, 4)\n'
        '    print(is_sorted(arr, 4))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "1" in out


def test_sort_by_descending():
    src = (
        'import "std/sort"\n'
        '\n'
        'fn main() -> int:\n'
        '    mut arr = alloc(5)\n'
        '    arr[0] = 3\n'
        '    arr[1] = 1\n'
        '    arr[2] = 4\n'
        '    arr[3] = 1\n'
        '    arr[4] = 5\n'
        '    sort_by(arr, 5, fn(a: int, b: int) -> int: b - a)\n'
        '    for x in arr:\n'
        '        print(x)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    # [5, 4, 3, 1, 1] — dois uns no input
    assert _lines(out, {"5", "4", "3", "1"}) == ["5", "4", "3", "1", "1"]


def test_sort_large_uses_quicksort():
    """n > 16 usa quicksort."""
    src = (
        'import "std/sort"\n'
        '\n'
        'fn main() -> int:\n'
        '    let n = 50\n'
        '    mut arr = alloc(n)\n'
        '    mut i = 0\n'
        '    while i < n:\n'
        '        arr[i] = (n - i) * 3\n'
        '        i += 1\n'
        '    sort(arr, n)\n'
        '    print(is_sorted(arr, n))\n'
        '    print(arr[0])\n'
        '    print(arr[n - 1])\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "1" in out
    assert "3" in out       # 1*3
    assert "150" in out     # 50*3


def test_sort_with_index_iteration():
    """Combina `for i, x in arr` + `sort`."""
    src = (
        'import "std/sort"\n'
        '\n'
        'fn main() -> int:\n'
        '    mut arr = alloc(4)\n'
        '    arr[0] = 40\n'
        '    arr[1] = 10\n'
        '    arr[2] = 30\n'
        '    arr[3] = 20\n'
        '    sort(arr, 4)\n'
        '    for i, x in arr:\n'
        '        print(i, x)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "0 10" in out
    assert "1 20" in out
    assert "2 30" in out
    assert "3 40" in out


def test_sort_closure_captures():
    """Comparator é closure que captura `mult`."""
    src = (
        'import "std/sort"\n'
        '\n'
        'fn main() -> int:\n'
        '    mut arr = alloc(4)\n'
        '    arr[0] = 2\n'
        '    arr[1] = 4\n'
        '    arr[2] = 1\n'
        '    arr[3] = 3\n'
        '    let mult = 10\n'
        '    sort_by(arr, 4, fn(a: int, b: int) -> int: (b - a) * mult)\n'
        '    print(arr[0], arr[3])\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "4 1" in out