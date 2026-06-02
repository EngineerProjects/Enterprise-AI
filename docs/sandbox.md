# Sandbox — Exécution isolée

Le sandbox isole l'exécution des commandes shell de l'agent dans un environnement contrôlé. Deux backends sont disponibles : local et Docker.

---

## LocalSandbox

Exécution dans un répertoire temporaire isolé, sans isolation de processus.

```python
from enterprise_ai.sandbox.local import LocalSandbox

sandbox = LocalSandbox(working_dir="/tmp/agent-workspace")

async with sandbox:
    result = await sandbox.exec("python script.py")
    print(result.output)
    print(result.exit_code)    # 0 = succès
    print(result.timed_out)   # True si timeout dépassé

    await sandbox.write_file("hello.py", "print('hello world')")
    content = await sandbox.read_file("hello.py")
```

---

## DockerSandbox

Isolation complète via Docker. **Prérequis** : `pip install "enterprise-ai[docker]"`

```python
from enterprise_ai.sandbox.docker import DockerSandbox

sandbox = DockerSandbox(
    image="python:3.12-slim",
    working_dir="/workspace",
)

async with sandbox:
    await sandbox.write_file("app.py", "print('running in Docker')")
    result = await sandbox.exec("python app.py", timeout=30.0)
    print(result.output)   # "running in Docker"
```

---

## API Sandbox (commune aux deux backends)

```python
class Sandbox(ABC):
    async def start(self) -> None          # démarre le sandbox
    async def stop(self) -> None           # arrête et nettoie
    async def exec(self, command: str, timeout: float = 30.0) -> ExecResult
    async def write_file(self, path: str, content: str) -> None
    async def read_file(self, path: str) -> str

    # Context manager async
    async def __aenter__(self) -> Sandbox
    async def __aexit__(self, ...) -> None
```

### ExecResult

```python
@dataclass
class ExecResult:
    output: str        # stdout + stderr
    exit_code: int
    timed_out: bool

    @property
    def error(self) -> bool:
        return self.exit_code != 0 or self.timed_out
```

---

## Sandbox custom

Implémente l'ABC pour brancher n'importe quel backend (VM, Firecracker, Nix, etc.) :

```python
from enterprise_ai.sandbox.base import Sandbox, ExecResult

class FirecrackerSandbox(Sandbox):
    async def start(self) -> None:
        await self._vm.boot()

    async def stop(self) -> None:
        await self._vm.shutdown()

    async def exec(self, command: str, timeout: float = 30.0) -> ExecResult:
        out, code = await self._vm.run(command, timeout=timeout)
        return ExecResult(output=out, exit_code=code)

    async def write_file(self, path: str, content: str) -> None:
        await self._vm.upload(path, content)

    async def read_file(self, path: str) -> str:
        return await self._vm.download(path)
```
