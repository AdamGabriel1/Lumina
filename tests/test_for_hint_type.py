"""`for x: T in arr:` — anotação opcional de tipo do elemento (v0.7.0).

Sem hint, o compilador **infere** o tipo do elemento a partir do
iterável (v0.7.0 fix). Ordem de precedência:

  1. Hint explícito (`for x: T in arr`)
  2. Array literal inline (`for x in [1.5, 2.5]`) — tipo do 1º elemento
  3. Variável com `array_elem_types` populado — tipo registrado
  4. String literal ou variável de tipo `str` — `int` (char i8)
  5. Fallback — `int`

Antes deste fix, `for x in ["a", "b"]` declarava `x: int` (hardcoded
em `_analyze_for`), então `let y: str = x` falhava no semantic mesmo
que o codegen iterasse `i8*` corretamente.

Cobre:
  - Hint `float` sobre array literal de float
  - Hint `str` sobre array literal de str
  - Inferência automática de `str` (sem hint) — v0.7.0 fix
  - Inferência automática de `float` (sem hint) — v0.7.0 fix
  - Teste negativo: tipo errado ainda falha
  - Hint com índice (`for i, x: T in arr`)
  - Preservação do comportamento anterior (sem hint, int array)
  - Formatter preserva a anotação

Limitação conhecida:
  `for x: T in ptr` (parâmetro sem `array_lengths` populado) produz
  loop vazio. Requer runtime type info para funcionar — planejado
  para v0.8.x.
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
        r2 = subprocess.run(
            [path[:-3]], capture_output=True, text=True, timeout=timeout,
        )
        return r2.stdout, r2.returncode
    finally:
        for p in (path, path[:-3] + ".ll", path[:-3]):
            if os.path.exists(p):
                os.remove(p)


def _build_fails(src, timeout=30):
    """Compila; espera falha. Retorna (stdout+stderr, rc)."""
    with tempfile.NamedTemporaryFile("w", suffix=".lm", delete=False) as f:
        f.write(src)
        path = f.name
    try:
        r = subprocess.run(
            [sys.executable, "-m", "lumina_cli", "build", path],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=timeout,
        )
        return r.stdout + r.stderr, r.returncode
    finally:
        for p in (path, path[:-3] + ".ll", path[:-3]):
            if os.path.exists(p):
                os.remove(p)


# ============================================================
# Casos funcionais com hint explícito
# ============================================================
def test_hint_float_array_literal():
    """Hint `float` sobre `[1.5, 2.5]` — compila e imprime floats."""
    src = (
        'fn main() -> int:\n'
        '    let precos = [1.5, 2.5, 3.5]\n'
        '    mut total = 0.0\n'
        '    for x: float in precos:\n'
        '        total += x\n'
        '    print(total)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "7.5" in out, f"out={out!r}"


def test_hint_str_enables_string_ops():
    """Com hint `str`, `x` é declarado como `str`."""
    src = (
        'fn main() -> int:\n'
        '    let nomes = ["a", "b", "c"]\n'
        '    mut count = 0\n'
        '    for x: str in nomes:\n'
        '        let y: str = x\n'
        '        count += 1\n'
        '    print(count)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "3" in out, f"out={out!r}"


def test_hint_with_index():
    """`for i, x: T in arr` — hint combinado com index_var."""
    src = (
        'fn main() -> int:\n'
        '    let v = [10.5, 20.5, 30.5]\n'
        '    mut weighted = 0.0\n'
        '    for i, x: float in v:\n'
        '        weighted += (i as float) * x\n'
        '    print(weighted)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    # 0*10.5 + 1*20.5 + 2*30.5 = 0 + 20.5 + 61.0 = 81.5
    assert "81.5" in out, f"out={out!r}"


# ============================================================
# Inferência automática (v0.7.0 fix do semantic)
# ============================================================
def test_without_hint_string_inference_works():
    """Sem hint, `_infer_for_elem_type` detecta `str` pelo array literal.

    Antes do fix de v0.7.0, `_analyze_for` declarava `x: int`
    (hardcoded), e `let y: str = x` falhava no semantic mesmo
    com o codegen iterando `i8*` corretamente.

    Agora `x` é inferido como `str` e o programa compila.
    """
    src = (
        'fn main() -> int:\n'
        '    let nomes = ["a", "b"]\n'
        '    for x in nomes:\n'
        '        let y: str = x\n'
        '        print(y)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert rc == 0, f"deveria compilar:\n{out}"
    assert "a" in out
    assert "b" in out


def test_without_hint_float_inference_works():
    """Sem hint, `_infer_for_elem_type` detecta `float` pelo array literal."""
    src = (
        'fn main() -> int:\n'
        '    let precos = [1.5, 2.5]\n'
        '    mut total = 0.0\n'
        '    for x in precos:\n'
        '        let y: float = x\n'
        '        total += y\n'
        '    print(total)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert rc == 0, f"deveria compilar:\n{out}"
    assert "4.0" in out, f"out={out!r}"


def test_without_hint_inline_array_inference():
    """Array literal inline também é inferido."""
    src = (
        'fn main() -> int:\n'
        '    for x in ["a", "b"]:\n'
        '        let y: str = x\n'
        '        print(y)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert rc == 0, f"deveria compilar:\n{out}"
    assert "a" in out
    assert "b" in out


# ============================================================
# Teste negativo — tipo errado ainda falha
# ============================================================
def test_int_array_with_str_annotation_fails():
    """Array de int + `let y: str = x` → erro em compile-time.

    Este é o teste negativo real: a inferência correta de v0.7.0
    declara `x` como `int` para `[1, 2]`, então `let y: str = x`
    deve falhar no semantic com "Tipo inválido".
    """
    src = (
        'fn main() -> int:\n'
        '    let nums = [1, 2]\n'
        '    for x in nums:\n'
        '        let y: str = x\n'   # x é int → erro
        '    return 0\n'
    )
    out, rc = _build_fails(src)
    assert rc != 0, (
        f"Array de int com `let y: str = x` deveria falhar.\n{out}"
    )
    assert "Tipo inválido" in out, f"out={out!r}"


def test_hint_conflicts_with_array_type_fails():
    """Hint `str` sobre array de int → erro em compile-time.

    O hint tem precedência, mas a inferência do array gera `int`.
    O codegen tenta `bitcast i64* → i8**` que o LLVM rejeita
    (ou o semantic detecta incompatibilidade antes).
    """
    src = (
        'fn main() -> int:\n'
        '    let nums = [1, 2, 3]\n'
        '    for x: str in nums:\n'
        '        print(x)\n'
        '    return 0\n'
    )
    out, rc = _build_fails(src)
    # Pode falhar no semantic OU no codegen/LLVM. Basta falhar.
    assert rc != 0, (
        f"Hint `str` sobre array de int deveria falhar.\n{out}"
    )


# ============================================================
# Baseline: sem hint, int array continua funcionando
# ============================================================
def test_without_hint_baseline_int_array():
    """Sem hint, iteração sobre int array continua funcionando."""
    src = (
        'fn main() -> int:\n'
        '    let v = [1, 2, 3, 4]\n'
        '    mut total = 0\n'
        '    for x in v:\n'
        '        total += x\n'
        '    print(total)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "10" in out


# ============================================================
# Formatter preserva a anotação
# ============================================================
def test_formatter_preserves_hint():
    """`lumina fmt` reemite `for x: T in arr` corretamente."""
    src = (
        'fn main() -> int:\n'
        '    let v = [1.5, 2.5]\n'
        '    for x: float in v:\n'
        '        print(x)\n'
        '    return 0\n'
    )
    with tempfile.NamedTemporaryFile("w", suffix=".lm", delete=False) as f:
        f.write(src)
        path = f.name
    try:
        r = subprocess.run(
            [sys.executable, "-m", "lumina_cli", "fmt", path],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert r.returncode == 0, f"fmt falhou:\n{r.stderr}"
        with open(path) as fh:
            formatted = fh.read()
        assert "for x: float in v" in formatted, (
            f"fmt perdeu a anotação:\n{formatted}"
        )
    finally:
        os.remove(path)


# ============================================================
# Limitação conhecida
# ============================================================
def test_limitation_ptr_without_length():
    """`for x: T in ptr` sem `array_lengths` → loop vazio.

    Esta é a **limitação conhecida** documentada no CHANGELOG.
    A anotação de tipo resolve o problema de *tipo*, mas não o de
    *comprimento* — o compilador não sabe quantos elementos existem.
    Solução completa requer Slice<T> ou runtime type info (v0.8.x).
    """
    src = (
        'fn sum_via_ptr(arr: ptr) -> float:\n'
        '    mut total = 0.0\n'
        '    for x: float in arr:\n'
        '        total += x\n'
        '    return total\n'
        '\n'
        'fn main() -> int:\n'
        '    let v = [1.5, 2.5, 3.5]\n'
        '    let s = sum_via_ptr(v)\n'
        '    print(s)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    # Hoje: retorna 0 (loop vazio). Documentado.
    assert rc == 0, f"deveria compilar, rc={rc}\n{out!r}"
    assert "0.000000" in out, (
        f"comportamento atual é loop vazio; se mudou, atualize o teste:\n{out!r}"
    )