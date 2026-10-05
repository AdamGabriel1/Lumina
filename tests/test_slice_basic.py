"""Smoke tests para slices `[T]` (v0.8.0)."""
import os, pathlib, subprocess, sys, tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _run(src, timeout=30):
    with tempfile.NamedTemporaryFile("w", suffix=".lm", delete=False) as f:
        f.write(src); path = f.name
    try:
        r1 = subprocess.run(
            [sys.executable, "-m", "lumina_cli", "build", path],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=timeout,
        )
        assert r1.returncode == 0, f"Build falhou:\n{r1.stdout}\n{r1.stderr}"
        r2 = subprocess.run([path[:-3]], capture_output=True, text=True, timeout=timeout)
        return r2.stdout, r2.returncode
    finally:
        for p in (path, path[:-3] + ".ll", path[:-3]):
            if os.path.exists(p):
                os.remove(p)


def test_slice_len():
    out, rc = _run(
        'fn main() -> int:\n'
        '    let v = [1, 2, 3, 4, 5]\n'
        '    let s = v[1..4]\n'
        '    print(len(s))\n'
        '    return 0\n'
    )
    assert "3" in out, f"out={out!r}"


def test_slice_iter():
    out, rc = _run(
        'fn main() -> int:\n'
        '    let v = [10, 20, 30]\n'
        '    let s = v[..]\n'
        '    for x in s:\n'
        '        print(x)\n'
        '    return 0\n'
    )
    assert "10" in out and "20" in out and "30" in out


def test_slice_index():
    out, rc = _run(
        'fn main() -> int:\n'
        '    let v = [10, 20, 30]\n'
        '    let s = v[..]\n'
        '    print(s[1])\n'
        '    return 0\n'
    )
    assert "20" in out


def test_slice_fn_param():
    out, rc = _run(
        'fn total(s: [int]) -> int:\n'
        '    mut t = 0\n'
        '    for x in s:\n'
        '        t += x\n'
        '    return t\n'
        '\n'
        'fn main() -> int:\n'
        '    let v = [1, 2, 3]\n'
        '    print(total(v[..]))\n'
        '    return 0\n'
    )
    assert "6" in out


def test_slice_data_and_len_fields():
    out, rc = _run(
        'fn main() -> int:\n'
        '    let v = [10, 20, 30]\n'
        '    let s = v[..]\n'
        '    print(s.len)\n'
        '    return 0\n'
    )
    assert "3" in out
