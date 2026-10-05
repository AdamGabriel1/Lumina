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


def test_generic_enum_construction():
    src = (
        'enum MyRes<T, E>:\n'
        '    Ok(T)\n'
        '    Err(E)\n'
        '\n'
        'fn main() -> int:\n'
        '    let r = MyRes::Ok(42)\n'
        '    return 0\n'
    )
    # Se não houver sintaxe `::`, usa o construtor direto:
    src = (
        'enum MyRes<T, E>:\n'
        '    Ok(T)\n'
        '    Err(E)\n'
        '\n'
        'fn main() -> int:\n'
        '    let r: MyRes<int, str> = Ok(42)\n'
        '    return 0\n'
    )
    # Nota: Ok é hardcoded para Result no codegen. Vamos usar nome único.
    src = (
        'enum Custom<T>:\n'
        '    Wrap(T)\n'
        '    Empty\n'
        '\n'
        'fn main() -> int:\n'
        '    let c = Wrap(42)\n'
        '    match c:\n'
        '        case Wrap(v): print(v)\n'
        '        case Empty:   print(0)\n'
        '    return 0\n'
    )
    assert "42" in _run(src)


def test_generic_enum_str_payload():
    src = (
        'enum Box<T>:\n'
        '    Has(T)\n'
        '    Empty\n'
        '\n'
        'fn main() -> int:\n'
        '    let b = Has("hello")\n'
        '    match b:\n'
        '        case Has(s): print(s)\n'
        '        case Empty:  print("empty")\n'
        '    return 0\n'
    )
    assert "hello" in _run(src)
