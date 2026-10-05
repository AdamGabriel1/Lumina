"""defer com escopo de bloco (mudança do Sprint 8b).

Antes: `defer` dentro de `if`/`while`/`for` rodava no fim da FUNÇÃO.
Bug: `if false: defer print("x")` ainda imprimia "x".

Agora: cada bloco tem seu próprio escopo de defer.
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


# ============================================================
# Regressão: defer no fim da função
# ============================================================
def test_defer_at_function_level():
    src = (
        'fn main() -> int:\n'
        '    print("a")\n'
        '    defer print("b")\n'
        '    print("c")\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    lines = [l for l in out.splitlines() if l in ("a", "b", "c")]
    assert lines == ["a", "c", "b"], f"ordem: {out!r}"


# ============================================================
# NOVO: defer em if toma o bloco
# ============================================================
def test_defer_in_if_runs_at_end_of_if():
    src = (
        'fn main() -> int:\n'
        '    print("inicio")\n'
        '    if 1 == 1:\n'
        '        defer print("defer-if")\n'
        '        print("dentro")\n'
        '    print("depois")\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    # Ordem esperada: inicio, dentro, defer-if, depois
    lines = [l for l in out.splitlines() if l in ("inicio", "defer-if", "dentro", "depois")]
    assert lines == ["inicio", "dentro", "defer-if", "depois"], f"ordem: {out!r}"


def test_defer_in_untaken_if_does_not_run():
    """BUG corrigido: `defer` dentro de `if false` não deve rodar."""
    src = (
        'fn main() -> int:\n'
        '    if 1 == 2:\n'
        '        defer print("NAO DEVE APARECER")\n'
        '        print("nao")\n'
        '    print("fim")\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "NAO DEVE APARECER" not in out, f"defer vazou: {out!r}"
    assert "fim" in out


def test_defer_in_while_body_runs_each_iteration():
    src = (
        'fn main() -> int:\n'
        '    mut i = 0\n'
        '    while i < 2:\n'
        '        defer print("iter")\n'
        '        print(i)\n'
        '        i = i + 1\n'
        '    print("fim")\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    lines = [l for l in out.splitlines() if l in ("0", "1", "iter", "fim")]
    # "iter" deve aparecer entre as iterações e antes de "fim"
    assert lines.count("iter") == 2, f"iter count: {out!r}"
    assert lines[-1] == "fim"


def test_defer_in_for_body():
    src = (
        'fn main() -> int:\n'
        '    for i in 0..2:\n'
        '        defer print("cleanup")\n'
        '        print(i)\n'
        '    print("done")\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    lines = [l for l in out.splitlines() if l in ("0", "1", "cleanup", "done")]
    assert lines.count("cleanup") == 2, f"cleanup count: {out!r}"
    assert lines[-1] == "done"


# ============================================================
# Return dentro de bloco emite defers pendentes
# ============================================================
def test_return_emits_block_and_function_defers():
    src = (
        'fn f() -> int:\n'
        '    defer print("func")\n'
        '    if 1 == 1:\n'
        '        defer print("bloco")\n'
        '        print("no-if")\n'
        '        return 42\n'
        '    return 0\n'
        '\n'
        'fn main() -> int:\n'
        '    let x = f()\n'
        '    print(x)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    # Ordem: no-if, bloco, func, 42
    lines = [l for l in out.splitlines() if l in ("no-if", "bloco", "func", "42")]
    assert lines == ["no-if", "bloco", "func", "42"], f"ordem: {out!r}"


def test_break_emits_block_defers():
    src = (
        'fn main() -> int:\n'
        '    mut i = 0\n'
        '    while 1 == 1:\n'
        '        defer print("iter-cleanup")\n'
        '        print(i)\n'
        '        if i == 1:\n'
        '            break\n'
        '        i = i + 1\n'
        '    print("after")\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    lines = [l for l in out.splitlines() if l in ("0", "1", "iter-cleanup", "after")]
    # Esperado: 0, iter-cleanup, 1, iter-cleanup, after
    assert lines.count("iter-cleanup") == 2
    assert lines[-1] == "after"
