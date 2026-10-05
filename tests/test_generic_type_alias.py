import os, pathlib, subprocess, sys, tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _run(src, timeout=30):
    with tempfile.NamedTemporaryFile("w", suffix=".lm", delete=False) as f:
        f.write(src); path = f.name
    try:
        r1 = subprocess.run([sys.executable, "-m", "lumina_cli", "build", path],
                            capture_output=True, text=True, cwd=REPO_ROOT, timeout=timeout)
        assert r1.returncode == 0, f"Build falhou:\n{r1.stdout}\n{r1.stderr}"
        binary = path[:-3]
        r2 = subprocess.run([binary], capture_output=True, text=True, timeout=timeout)
        return r2.stdout
    finally:
        for p in (path, path[:-3] + ".ll", path[:-3]):
            if os.path.exists(p): os.remove(p)


def test_generic_alias_simple():
    src = (
        'struct Box<T>:\n'
        '    data: T\n'
        '\n'
        'type BI = Box<int>\n'
        '\n'
        'fn main() -> int:\n'
        '    mut b: BI\n'
        '    b.data = 42\n'
        '    print(b.data)\n'
        '    return 0\n'
    )
    assert "42" in _run(src)


def test_generic_alias_with_params():
    src = (
        'struct Pair<A, B>:\n'
        '    a: A\n'
        '    b: B\n'
        '\n'
        'type IPair<B> = Pair<int, B>\n'
        '\n'
        'fn main() -> int:\n'
        '    mut p: IPair<str>\n'
        '    p.a = 10\n'
        '    p.b = "hi"\n'
        '    print(p.a)\n'
        '    print(p.b)\n'
        '    return 0\n'
    )
    out = _run(src)
    assert "10" in out
    assert "hi" in out


def test_generic_alias_chained():
    src = (
        'struct Box<T>:\n'
        '    data: T\n'
        '\n'
        'type BI = Box<int>\n'
        'type Alias2 = BI\n'
        '\n'
        'fn main() -> int:\n'
        '    mut b: Alias2\n'
        '    b.data = 99\n'
        '    print(b.data)\n'
        '    return 0\n'
    )
    assert "99" in _run(src)


def test_generic_alias_inside_fn_sig():
    src = (
        'struct Box<T>:\n'
        '    data: T\n'
        '\n'
        'type BI = Box<int>\n'
        '\n'
        'fn get(b: BI) -> int:\n'
        '    return b.data\n'
        '\n'
        'fn main() -> int:\n'
        '    mut b: Box<int>\n'
        '    b.data = 7\n'
        '    print(get(b))\n'
        '    return 0\n'
    )
    assert "7" in _run(src)
