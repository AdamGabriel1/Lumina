# 📦 Lumina Standard Library

A Standard Library da Lumina (`std/`) é importada automaticamente (via `prelude.lm`) ou sob demanda. Ela é escrita em Lumina e C nativo, focando em alta performance e zero overhead.

## Módulos Disponíveis

### `std/epoll`
Event Loop Assíncrono nativo do Linux. Usado para construir servidores web de alta performance (non-blocking I/O).
* `criar()`: Cria uma instância do epoll.
* `adicionar(epfd, fd)`: Registra um file descriptor.
* `esperar(epfd, timeout)`: Aguarda eventos do Kernel.

### `std/http`
Web Framework HTTP nativo. Permite subir servidores com sockets POSIX puros.
* `iniciar(porta)`: Inicia um listener TCP na porta especificada.

### `std/json`
Parser de JSON nativo escrito em Lumina.
* `get_str(json, key)`: Extrai uma string de um JSON.
* `get_int(json, key)`: Extrai um inteiro de um JSON.

### `std/vector`
Array Dinâmico que cresce automaticamente na memória (Heap).
* `new()`: Cria um vector vazio.
* `push(v, val)`: Adiciona um elemento no final.

### `std/map`
Hash Map (Dicionário) com tratamento de colisões via Linked List.
* `init()`: Inicializa o mapa em memória.
* `set(key, val)`: Insere ou atualiza.
* `get(key)`: Busca um valor.

### `std/async`
Green Threads e troca de contexto (ucontext) para concorrência leve.
* `spawn(func)`: Cria uma nova corrotina.
* `join_all()`: Aguarda todas as corrotinas terminarem.

### `std/raylib`
Bindings para a engine gráfica Raylib.
* `InitWindow(w, h, title)`: Cria a janela do jogo.
* `BeginDrawing()` / `EndDrawing()`: Loop de renderização.
```

---

### 5. 🧪 Expansão dos Testes (Smoke Tests no Pytest)
Para garantir que nenhum commit quebre a geração de código, adicione este teste no arquivo `tests/test_cli.py`:

```python
import glob

def test_smoke_tests_examples():
    """Compila todos os arquivos da pasta examples/ para garantir que nenhum commit quebre o codegen."""
    examples = glob.glob("examples/*.lm")
    assert len(examples) > 0, "Nenhum exemplo encontrado"
    
    for file in examples:
        result = run_cli("build", file, cwd=".")
        assert result.returncode == 0, f"Erro ao compilar {file}: {result.stderr}"
```

Rode `pytest tests/ -v` e veja ele compilar todos os seus 50+ exemplos sem quebrar!

### 6. 🚀 Exemplo Prático: WASM chamando JS
Crie um arquivo `examples/wasm_js_interop.lm`:

```lumina
# Importa uma função do JavaScript
extern "wasm" fn js_alert(msg: str)

# Exporta uma função para o JavaScript chamar
export fn trigger_alert():
    js_alert("Hello from Lumina WASM!")

fn main() -> int:
    return 0
```

Compile com `lumina build examples/wasm_js_interop.lm --wasm`. O `wasm-ld` vai gerar um módulo que espera que o JS forneça a função `js_alert` e expõe a `trigger_alert` para o JS chamar!