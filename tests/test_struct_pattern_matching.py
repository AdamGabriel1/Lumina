"""Testes para Pattern Matching com Struct Destructuring."""
import sys
import os
import subprocess
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _run(src, timeout=30):
    with tempfile.NamedTemporaryFile("w", suffix=".lm", delete=False) as f:
        f.write(src)
        path = f.name
    try:
        r1 = subprocess.run(
            [sys.executable, "-m", "lumina_cli", "build", path],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=timeout,
        )
        if r1.returncode != 0:
            return r1.stdout + r1.stderr, r1.returncode
        
        bin_path = path.replace(".lm", "")
        r2 = subprocess.run([bin_path], capture_output=True, text=True, timeout=timeout)
        return r2.stdout + r2.stderr, r2.returncode
    finally:
        if os.path.exists(path):
            os.remove(path)
        bin_path = path.replace(".lm", "")
        if os.path.exists(bin_path):
            os.remove(bin_path)

def test_simple_binding():
    src = '''
struct Ponto:
    x: int
    y: int

fn main() -> int:
    let p = Ponto { x: 10, y: 20 }
    match p:
        case Ponto { x, y }:
            print(x + y)
            return 0
    return 1
'''
    out, rc = _run(src)
    assert rc == 0, f"Deveria rodar:\n{out}"
    assert "30" in out

def test_literal_match():
    src = '''
struct Ponto:
    x: int
    y: int

fn main() -> int:
    let p = Ponto { x: 10, y: 0 }
    match p:
        case Ponto { x, y: 0 }:
            print("Eixo X:", x)
            return 0
        case _:
            return 1
'''
    out, rc = _run(src)
    assert rc == 0, f"Deveria casar o literal:\n{out}"
    assert "Eixo X: 10" in out

def test_aliased_binding():
    src = '''
struct Ponto:
    x: int
    y: int

fn main() -> int:
    let p = Ponto { x: 42, y: 99 }
    match p:
        case Ponto { x: a, y: b }:
            print(a)
            print(b)
            return 0
    return 1
'''
    out, rc = _run(src)
    assert rc == 0, f"Deveria criar aliases:\n{out}"
    assert "42" in out
    assert "99" in out

def test_match_with_guard():
    src = '''
struct Ponto:
    x: int
    y: int

fn main() -> int:
    let p = Ponto { x: 150, y: 20 }
    match p:
        case Ponto { x: a, y: b } if a > 100:
            print("X grande:", a + b)
            return 0
        case _:
            return 1
'''
    out, rc = _run(src)
    assert rc == 0, f"Deveria passar no guard:\n{out}"
    assert "X grande: 170" in out

def test_fallthrough_to_default():
    src = '''
struct Ponto:
    x: int
    y: int

fn main() -> int:
    let p = Ponto { x: 10, y: 20 }
    match p:
        case Ponto { x, y: 0 }:
            return 1
        case Ponto { x: 0, y }:
            return 2
        case _:
            print("Nenhum dos anteriores")
            return 0
'''
    out, rc = _run(src)
    assert rc == 0, f"Deveria cair no default:\n{out}"
    assert "Nenhum dos anteriores" in out

def test_multiple_fields_literal():
    src = '''
struct Caixa:
    id: int
    valor: int

fn main() -> int:
    let c = Caixa { id: 1, valor: 99 }
    match c:
        case Caixa { id: 1, valor: 99 }:
            print("Achou a caixa exata")
            return 0
        case _:
            return 1
'''
    out, rc = _run(src)
    assert rc == 0, f"Deveria achar a caixa exata:\n{out}"
    assert "Achou a caixa exata" in out
