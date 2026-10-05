"""Testes de std/os."""
import os
import pathlib
import subprocess
import sys
import tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _run(src, env_extra=None, timeout=30):
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
        env = {**os.environ}
        if env_extra:
            env.update(env_extra)
        r2 = subprocess.run(
            [binary], capture_output=True, text=True, timeout=timeout, env=env,
        )
        return r2.stdout, r2.returncode
    finally:
        for p in (path, path[:-3] + ".ll", path[:-3]):
            if os.path.exists(p):
                os.remove(p)


def test_get_env():
    src = (
        'import "std/os"\n'
        '\n'
        'fn main() -> int:\n'
        '    let v = get_env("LUMINA_TEST_VAR")\n'
        '    print(v)\n'
        '    return 0\n'
    )
    out, rc = _run(src, env_extra={"LUMINA_TEST_VAR": "hello"})
    assert "hello" in out, f"out={out!r}"


def test_get_env_missing():
    src = (
        'import "std/os"\n'
        '\n'
        'fn main() -> int:\n'
        '    let v = get_env("LUMINA_DOES_NOT_EXIST_12345")\n'
        '    if len(v) == 0:\n'
        '        print("empty")\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "empty" in out


def test_has_env():
    src = (
        'import "std/os"\n'
        '\n'
        'fn main() -> int:\n'
        '    print(has_env("LUMINA_TEST_VAR"))\n'
        '    print(has_env("LUMINA_DOES_NOT_EXIST_12345"))\n'
        '    return 0\n'
    )
    out, rc = _run(src, env_extra={"LUMINA_TEST_VAR": "x"})
    lines = [l.strip() for l in out.splitlines() if l.strip()]
    assert lines == ["1", "0"], f"out={out!r}"


def test_cwd():
    src = (
        'import "std/os"\n'
        '\n'
        'fn main() -> int:\n'
        '    let d = cwd()\n'
        '    if len(d) > 0:\n'
        '        print("ok")\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "ok" in out


def test_shell():
    src = (
        'import "std/os"\n'
        '\n'
        'fn main() -> int:\n'
        '    let rc = shell("true")\n'
        '    print(rc)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "0" in out
