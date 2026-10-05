"""Genéricos aninhados: Box<T> como parâmetro.

Bug original: `fn put<T>(b: Box<T>, val: T)` falhava em compile-time
com "Tipo inválido para parâmetro 'b': esperado 'Box<T>', obteve 'Box<int>'".

Causa em 2 camadas:
  1. Semantic: is_assignable("Box<T>", "Box<int>") é False (compara
     strings literais). Fix: unificar e substituir type params.
  2. Codegen: materialize_generic só mapeava type params diretos.
     Fix: aceitar type_map e resolver tipos aninhados recursivamente.
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
# Box<T> como parâmetro
# ============================================================
def test_box_int_put_get():
    src = (
        'struct Box<T>:\n'
        '    data: T\n'
        '\n'
        'fn put<T>(b: Box<T>, val: T):\n'
        '    b.data = val\n'
        '\n'
        'fn get<T>(b: Box<T>) -> T:\n'
        '    return b.data\n'
        '\n'
        'fn main() -> int:\n'
        '    mut b: Box<int>\n'
        '    put(b, 100)\n'
        '    print(get(b))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "100" in out, f"stdout={out!r}"


def test_box_float_put_get():
    src = (
        'struct Box<T>:\n'
        '    data: T\n'
        '\n'
        'fn put<T>(b: Box<T>, val: T):\n'
        '    b.data = val\n'
        '\n'
        'fn get<T>(b: Box<T>) -> T:\n'
        '    return b.data\n'
        '\n'
        'fn main() -> int:\n'
        '    mut b: Box<float>\n'
        '    put(b, 2.5)\n'
        '    print(get(b))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "2.5" in out or "2.500000" in out, f"stdout={out!r}"


def test_box_str_put_get():
    src = (
        'struct Box<T>:\n'
        '    data: T\n'
        '\n'
        'fn put<T>(b: Box<T>, val: T):\n'
        '    b.data = val\n'
        '\n'
        'fn get<T>(b: Box<T>) -> T:\n'
        '    return b.data\n'
        '\n'
        'fn main() -> int:\n'
        '    mut b: Box<str>\n'
        '    put(b, "Lumina")\n'
        '    print(get(b))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "Lumina" in out, f"stdout={out!r}"


def test_box_int_and_str_coexist():
    """Duas especializações de Box no mesmo TU."""
    src = (
        'struct Box<T>:\n'
        '    data: T\n'
        '\n'
        'fn put<T>(b: Box<T>, val: T):\n'
        '    b.data = val\n'
        '\n'
        'fn get<T>(b: Box<T>) -> T:\n'
        '    return b.data\n'
        '\n'
        'fn main() -> int:\n'
        '    mut bi: Box<int>\n'
        '    mut bs: Box<str>\n'
        '    put(bi, 42)\n'
        '    put(bs, "hello")\n'
        '    print(get(bi))\n'
        '    print(get(bs))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    lines = _lines(out, {"42", "hello"})
    assert lines == ["42", "hello"], f"ordem: {out!r}"


# ============================================================
# Regressão: genéricos diretos continuam funcionando
# ============================================================
def test_direct_generic_still_works():
    src = (
        'fn identidade<T>(x: T) -> T:\n'
        '    return x\n'
        '\n'
        'fn main() -> int:\n'
        '    print(identidade(10))\n'
        '    print(identidade(3.14))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "10" in out
    assert "3.14" in out or "3.140000" in out


def test_box_local_var_only():
    """Box<int> como variável local (sem função genérica) — regressão."""
    src = (
        'struct Box<T>:\n'
        '    data: T\n'
        '\n'
        'fn main() -> int:\n'
        '    mut b: Box<int>\n'
        '    b.data = 42\n'
        '    print(b.data)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "42" in out
