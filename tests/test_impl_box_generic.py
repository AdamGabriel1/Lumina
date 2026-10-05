import os, pathlib, subprocess, sys, tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _run(src, timeout=30):
    with tempfile.NamedTemporaryFile("w", suffix=".lm", delete=False) as f:
        f.write(src); path = f.name
    try:
        r1 = subprocess.run([sys.executable, "-m", "lumina_cli", "build", path],
                            capture_output=True, text=True, cwd=REPO_ROOT, timeout=timeout)
        assert r1.returncode == 0, f"Build falhou:\n{r1.stdout}\n{r1.stderr}"
        r2 = subprocess.run([path[:-3]], capture_output=True, text=True, timeout=timeout)
        return r2.stdout
    finally:
        for p in (path, path[:-3] + ".ll", path[:-3]):
            if os.path.exists(p): os.remove(p)


def test_impl_trait_for_box_int():
    src = (
        'struct Box<T>:\n'
        '    data: T\n'
        '\n'
        'trait Getter:\n'
        '    fn get() -> int\n'
        '\n'
        'impl Getter for Box<int>:\n'
        '    fn get() -> int:\n'
        '        return self.data\n'
        '\n'
        'fn main() -> int:\n'
        '    mut b: Box<int>\n'
        '    b.data = 42\n'
        '    print(b.get())\n'
        '    return 0\n'
    )
    assert "42" in _run(src)


def test_two_specializations_distinct():
    """Duas especializações com corpos diferentes coexistem."""
    src = (
        'struct Box<T>:\n'
        '    data: T\n'
        '\n'
        'trait Kind:\n'
        '    fn kind() -> int\n'
        '\n'
        'impl Kind for Box<int>:\n'
        '    fn kind() -> int:\n'
        '        return 1\n'
        '\n'
        'impl Kind for Box<str>:\n'
        '    fn kind() -> int:\n'
        '        return 2\n'
        '\n'
        'fn main() -> int:\n'
        '    mut bi: Box<int>\n'
        '    bi.data = 10\n'
        '    mut bs: Box<str>\n'
        '    bs.data = "hi"\n'
        '    print(bi.kind())\n'
        '    print(bs.kind())\n'
        '    return 0\n'
    )
    out = _run(src)
    assert "1" in out
    assert "2" in out


def test_generic_impl_still_works_as_fallback():
    """`impl Box<T>:` (com type param) continua registrando base."""
    src = (
        'struct Box<T>:\n'
        '    data: T\n'
        '\n'
        'impl Box<T>:\n'
        '    fn get() -> int:\n'
        '        return self.data\n'
        '\n'
        'fn main() -> int:\n'
        '    mut b: Box<int>\n'
        '    b.data = 99\n'
        '    print(b.get())\n'
        '    return 0\n'
    )
    assert "99" in _run(src)
