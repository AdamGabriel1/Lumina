"""Testes de match com guard sobre strings.

Bug estrutural (corrigido em 2 camadas):
  1. Semantic declarava o binding de `case s if ...` como "int"
     (hardcoded), então `s.contains(...)` falhava com
     "Método 'contains' não implementado para a struct 'int'".
  2. Codegen extraía o binding DEPOIS do guard, então mesmo que
     o semantic passasse, `s` seria lido como 0 dentro do guard.
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
        r2 = subprocess.run(
            [binary], capture_output=True, text=True, timeout=timeout,
        )
        return r2.stdout, r2.returncode
    finally:
        for p in (path, path[:-3] + ".ll", path[:-3]):
            if os.path.exists(p):
                os.remove(p)


def _lines(out, wanted):
    return [l.strip() for l in out.splitlines() if l.strip() in wanted]


# ============================================================
# Guard usa o binding corretamente
# ============================================================
def test_str_guard_self_binding():
    src = (
        'fn classify(cmd: str) -> int:\n'
        '    match cmd:\n'
        '        case s if s.contains("danger"):\n'
        '            print("bloqueado")\n'
        '            return 1\n'
        '        case s if s.starts_with("run"):\n'
        '            print("executando")\n'
        '            return 2\n'
        '        default:\n'
        '            print("ignorado")\n'
        '            return 0\n'
        '    return -1\n'
        '\n'
        'fn main() -> int:\n'
        '    print(classify("dangerous"))\n'
        '    print(classify("running"))\n'
        '    print(classify("foo"))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert rc == 0, f"exit {rc}\n{out}"

    msg_lines = _lines(out, {"bloqueado", "executando", "ignorado"})
    assert msg_lines == ["bloqueado", "executando", "ignorado"], (
        f"ordem errada: {out!r}"
    )

    code_lines = _lines(out, {"1", "2", "0"})
    assert code_lines == ["1", "2", "0"], f"códigos errados: {out!r}"


def test_str_guard_falls_through():
    """Guard com contains() não deve casar strings sem o padrão."""
    src = (
        'fn check(s: str) -> str:\n'
        '    match s:\n'
        '        case x if x.contains("A"):\n'
        '            return "tem A"\n'
        '        case x if x.contains("B"):\n'
        '            return "tem B"\n'
        '        case x:\n'
        '            return "nada"\n'
        '    return "?"\n'
        '\n'
        'fn main() -> int:\n'
        '    print(check("XYZ"))\n'
        '    print(check("AB"))\n'
        '    print(check("QQQ"))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "nada" in out
    assert "tem A" in out


def test_str_guard_string_literal_case():
    """Case literal + guard em outro case."""
    src = (
        'fn route(cmd: str) -> str:\n'
        '    match cmd:\n'
        '        case "build":\n'
        '            return "build!"\n'
        '        case s if s.starts_with("test"):\n'
        '            return "testing"\n'
        '        default:\n'
        '            return "unknown"\n'
        '    return "?"\n'
        '\n'
        'fn main() -> int:\n'
        '    print(route("build"))\n'
        '    print(route("test_all"))\n'
        '    print(route("foobar"))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "build!" in out
    assert "testing" in out
    assert "unknown" in out


# ============================================================
# Regressão: match sem guard sobre str continua ok
# ============================================================
def test_str_match_without_guard():
    src = (
        'fn label(s: str) -> str:\n'
        '    match s:\n'
        '        case "a":\n'
        '            return "A"\n'
        '        case "b":\n'
        '            return "B"\n'
        '        default:\n'
        '            return "?"\n'
        '    return "!"\n'
        '\n'
        'fn main() -> int:\n'
        '    print(label("a"))\n'
        '    print(label("b"))\n'
        '    print(label("c"))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    lines = _lines(out, {"A", "B", "?"})
    assert lines == ["A", "B", "?"], f"ordem: {out!r}"
