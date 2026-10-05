"""Escape analysis: alloc(N) com N constante e sem escape vira alloca."""
import pathlib, subprocess, sys, tempfile
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

def _build_ir(src):
    with tempfile.NamedTemporaryFile("w", suffix=".lm", delete=False) as f:
        f.write(src)
        path = f.name
    try:
        r = subprocess.run(
            [sys.executable, "-m", "lumina_cli", "build", path],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=30,
        )
        assert r.returncode == 0, r.stdout + r.stderr
        with open(path[:-3] + ".ll") as irf:
            return irf.read()
    finally:
        for p in (path, path[:-3] + ".ll", path[:-3]):
            if __import__("os").path.exists(p):
                __import__("os").remove(p)

def test_alloc_const_no_escape_uses_alloca():
    ir = _build_ir(
        'fn main() -> int:\n'
        '    let buf = alloc(10)\n'
        '    buf[0] = 1\n'
        '    print(buf[0])\n'
        '    return 0\n'
    )
    assert "alloca" in ir
    assert "GC_malloc" not in ir or ir.count("call i8* @GC_malloc") == 0

def test_alloc_const_escapes_uses_gc():
    ir = _build_ir(
        'fn make() -> ptr:\n'
        '    let buf = alloc(10)\n'
        '    return buf\n'
        '\n'
        'fn main() -> int:\n'
        '    return 0\n'
    )
    assert "GC_malloc" in ir

def test_alloc_nonconst_uses_gc():
    ir = _build_ir(
        'fn size() -> int:\n'
        '    return 10\n'
        '\n'
        'fn main() -> int:\n'
        '    let n = size()\n'
        '    let buf = alloc(n)\n'
        '    return 0\n'
    )
    assert "GC_malloc" in ir

def test_freed_var_uses_gc():
    """`free(x)` impede stack allocation (senão crasharia)."""
    ir = _build_ir(
        'fn main() -> int:\n'
        '    let buf = alloc(10)\n'
        '    buf[0] = 1\n'
        '    free(buf)\n'
        '    return 0\n'
    )
    assert "GC_malloc" in ir
