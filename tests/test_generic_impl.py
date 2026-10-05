"""Testes de `impl Box<T>:` — métodos em structs genéricas.

O `<T>` é descartado para o nome do tipo (`struct_name = "Box"`), então
todos os métodos ficam registrados como `Box_metodo`. Chamadas via
`Box<int>`, `Box<str>`, etc. resolvem pelo nome base.
"""
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
# Uso básico
# ============================================================
def test_impl_generic_get_int():
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
        '    b.data = 42\n'
        '    print(b.get())\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "42" in out


def test_impl_generic_get_str():
    src = (
        'struct Box<T>:\n'
        '    data: T\n'
        '\n'
        'impl Box<T>:\n'
        '    fn get() -> str:\n'
        '        return self.data\n'
        '\n'
        'fn main() -> int:\n'
        '    mut b: Box<str>\n'
        '    b.data = "hello"\n'
        '    print(b.get())\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "hello" in out


def test_impl_generic_multiple_instantiations():
    """`Box<int>` e `Box<str>` no mesmo programa usam o mesmo método."""
    src = (
        'struct Box<T>:\n'
        '    data: T\n'
        '\n'
        'impl Box<T>:\n'
        '    fn get() -> int:\n'
        '        return self.data\n'
        '\n'
        'fn main() -> int:\n'
        '    mut bi: Box<int>\n'
        '    bi.data = 42\n'
        '    print(bi.get())\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "42" in out


def test_impl_generic_setter():
    src = (
        'struct Box<T>:\n'
        '    data: T\n'
        '\n'
        'impl Box<T>:\n'
        '    fn set(v: int):\n'
        '        self.data = v\n'
        '    fn get() -> int:\n'
        '        return self.data\n'
        '\n'
        'fn main() -> int:\n'
        '    mut b: Box<int>\n'
        '    b.set(99)\n'
        '    print(b.get())\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "99" in out


# ============================================================
# Regressão: impl não-genérico continua
# ============================================================
def test_impl_non_generic_still_works():
    src = (
        'struct Counter:\n'
        '    n: int\n'
        '\n'
        'impl Counter:\n'
        '    fn inc():\n'
        '        self.n = self.n + 1\n'
        '    fn get() -> int:\n'
        '        return self.n\n'
        '\n'
        'fn main() -> int:\n'
        '    mut c: Counter\n'
        '    c.n = 0\n'
        '    c.inc()\n'
        '    c.inc()\n'
        '    c.inc()\n'
        '    print(c.get())\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "3" in out


def test_impl_trait_for_generic():
    """`impl Trait for Box<T>:` — trait_name = Trait, struct_name = Box."""
    src = (
        'struct Box<T>:\n'
        '    data: T\n'
        '\n'
        'trait Gettable:\n'
        '    fn get() -> int\n'
        '\n'
        'impl Gettable for Box<int>:\n'
        '    fn get() -> int:\n'
        '        return self.data\n'
        '\n'
        'fn main() -> int:\n'
        '    mut b: Box<int>\n'
        '    b.data = 7\n'
        '    print(b.get())\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "7" in out
