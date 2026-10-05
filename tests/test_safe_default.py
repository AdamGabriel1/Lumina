"""Safe-by-default global (v0.7.0).

Antes: `@safe` era opt-in. Sem ele, `u.id` com `u == nil` causava
SIGSEGV. Agora null checks são o **padrão**, e `@unsafe` é o opt-out.

Cobre:
  - `u.id` com `u == nil` retorna 0 sem `@safe`
  - `@unsafe` remove os blocos `safe_nav_*` do IR
  - Closures herdam o modo safe do escopo externo
  - Cópias especializadas de genéricos herdam
  - Membros de SCCs (mutual TCO) herdam
  - `?.` (safe nav explícito) continua funcionando em ambos os modos
"""
import os
import pathlib
import re
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


def _build_ir(src, timeout=30):
    with tempfile.NamedTemporaryFile("w", suffix=".lm", delete=False) as f:
        f.write(src)
        path = f.name
    try:
        r = subprocess.run(
            [sys.executable, "-m", "lumina_cli", "build", path],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=timeout,
        )
        assert r.returncode == 0, f"Build falhou:\n{r.stdout}\n{r.stderr}"
        with open(path[:-3] + ".ll") as irf:
            return irf.read()
    finally:
        for p in (path, path[:-3] + ".ll", path[:-3]):
            if os.path.exists(p):
                os.remove(p)


def _fn_body_ir(ir, fn_name):
    """Extrai o corpo IR (entre `define` desta fn e o próximo `define`)."""
    pattern = rf'define [^\n]*@["\']?{re.escape(fn_name)}["\']?\([^)]*\)[^{{]*\{{'
    m = re.search(pattern, ir)
    if not m:
        return None
    start = m.start()
    end = ir.find("\ndefine ", start + 1)
    if end < 0:
        end = len(ir)
    return ir[start:end]


# ============================================================
# Comportamento em runtime
# ============================================================
def test_nil_member_without_safe_attr_returns_zero():
    """Sem `@safe`, `u.id` com `u == nil` retorna 0 (novo default)."""
    src = (
        'struct U:\n'
        '    id: int\n'
        '\n'
        'fn get_id(u: U) -> int:\n'
        '    return u.id\n'
        '\n'
        'fn main() -> int:\n'
        '    let u: U = nil\n'
        '    print(get_id(u))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert rc == 0, f"deveria rodar sem crash, rc={rc}, out={out!r}"
    assert "0" in out, f"out={out!r}"


def test_explicit_safe_attr_still_works():
    """`@safe` continua sendo aceito (redundante, mas não quebra)."""
    src = (
        'struct U:\n'
        '    id: int\n'
        '\n'
        '@safe\n'
        'fn get_id(u: U) -> int:\n'
        '    return u.id\n'
        '\n'
        'fn main() -> int:\n'
        '    let u: U = nil\n'
        '    print(get_id(u))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert rc == 0
    assert "0" in out


def test_valid_struct_still_returns_value():
    """Null check não interfere em acesso normal."""
    src = (
        'struct U:\n'
        '    id: int\n'
        '\n'
        'fn get_id(u: U) -> int:\n'
        '    return u.id\n'
        '\n'
        'fn main() -> int:\n'
        '    mut u: U\n'
        '    u.id = 99\n'
        '    print(get_id(u))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "99" in out


def test_safe_nav_still_works():
    """`?.` continua sendo null check explícito (independente do modo)."""
    src = (
        'struct U:\n'
        '    id: int\n'
        '\n'
        'fn main() -> int:\n'
        '    let u: U = nil\n'
        '    let x = u?.id\n'
        '    print(x)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "0" in out


# ============================================================
# Inspeção do IR
# ============================================================
def test_safe_default_emits_null_check_blocks():
    """Sem `@unsafe`, `u.id` deve emitir blocos `safe_nav_*`."""
    src = (
        'struct U:\n'
        '    id: int\n'
        '\n'
        'fn get_id(u: U) -> int:\n'
        '    return u.id\n'
        '\n'
        'fn main() -> int:\n'
        '    return 0\n'
    )
    ir = _build_ir(src)
    assert "safe_nav" in ir, (
        f"Safe-by-default não emitiu null check:\n{ir[:800]}"
    )


def test_unsafe_attr_removes_null_check_blocks():
    """`@unsafe` desliga os blocos `safe_nav_*` na função."""
    src = (
        'struct U:\n'
        '    id: int\n'
        '\n'
        '@unsafe\n'
        'fn get_id(u: U) -> int:\n'
        '    return u.id\n'
        '\n'
        'fn main() -> int:\n'
        '    return 0\n'
    )
    ir = _build_ir(src)
    body = _fn_body_ir(ir, "get_id")
    assert body is not None, f"get_id não encontrada:\n{ir[:500]}"
    assert "safe_nav" not in body, (
        f"@unsafe deveria remover null check, mas ele está lá:\n{body[:500]}"
    )


# ============================================================
# Herança de safe-mode em contextos especiais
# ============================================================
def test_closure_inherits_safe_mode():
    """Closure definida em função safe-default herda o null check."""
    src = (
        'struct U:\n'
        '    id: int\n'
        '\n'
        'fn main() -> int:\n'
        '    let u: U = nil\n'
        '    let get = fn() -> int: u.id\n'
        '    print(get())\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert rc == 0, f"closure deveria herdar safe, rc={rc}\n{out!r}"
    assert "0" in out


def test_generic_specialization_inherits_safe_mode():
    """Cópia especializada de genérico herda safe-mode."""
    src = (
        'struct Box<T>:\n'
        '    data: T\n'
        '\n'
        'fn get_field<T>(b: Box<T>) -> int:\n'
        '    return b.data\n'
        '\n'
        'fn main() -> int:\n'
        '    let b: Box<int> = nil\n'
        '    print(get_field(b))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert rc == 0, f"genérico deveria herdar safe, rc={rc}\n{out!r}"
    assert "0" in out


def test_scc_member_inherits_safe_mode():
    """Membro de SCC (mutual TCO) herda safe-mode."""
    src = (
        'struct U:\n'
        '    id: int\n'
        '\n'
        'fn a(n: int) -> int:\n'
        '    if n == 0:\n'
        '        let u: U = nil\n'
        '        return u.id\n'
        '    return b(n - 1)\n'
        '\n'
        'fn b(n: int) -> int:\n'
        '    if n == 0:\n'
        '        return 0\n'
        '    return a(n - 1)\n'
        '\n'
        'fn main() -> int:\n'
        '    print(a(2))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert rc == 0, f"SCC deveria herdar safe, rc={rc}\n{out!r}"
    assert "0" in out
