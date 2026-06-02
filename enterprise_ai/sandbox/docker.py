from __future__ import annotations

import asyncio
import io
import tarfile
import uuid
from pathlib import Path
from typing import Any

from enterprise_ai.sandbox.base import ExecResult, Sandbox

DEFAULT_IMAGE = "python:3.12-slim"
DEFAULT_MEMORY = "512m"
DEFAULT_CPU = 1.0


class DockerSandbox(Sandbox):
    """
    Executes commands inside an ephemeral Docker container.

    Each sandbox instance creates a single container for its lifetime.
    The container is removed on stop().

    Usage:
        async with DockerSandbox(working_dir="/workspace") as sb:
            result = await sb.exec("python script.py", timeout=60)
    """

    def __init__(
        self,
        image: str = DEFAULT_IMAGE,
        working_dir: str = "/workspace",
        memory_limit: str = DEFAULT_MEMORY,
        cpu_limit: float = DEFAULT_CPU,
        network_disabled: bool = True,
        extra_env: dict[str, str] | None = None,
    ) -> None:
        self._image = image
        self._working_dir = working_dir
        self._memory_limit = memory_limit
        self._cpu_limit = cpu_limit
        self._network_disabled = network_disabled
        self._extra_env = extra_env or {}
        self._container: Any = None
        self._container_id = f"enterprise-ai-{uuid.uuid4().hex[:12]}"

    async def start(self) -> None:
        try:
            import docker  # type: ignore[import-not-found]
        except ImportError:
            raise ImportError("docker package required: pip install 'enterprise-ai[docker]'")

        client = docker.from_env()

        env = {"PYTHONUNBUFFERED": "1", **self._extra_env}

        self._container = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: client.containers.run(
                self._image,
                command="sleep infinity",
                name=self._container_id,
                working_dir=self._working_dir,
                mem_limit=self._memory_limit,
                nano_cpus=int(self._cpu_limit * 1e9),
                network_disabled=self._network_disabled,
                environment=env,
                detach=True,
                remove=False,
                labels={"managed-by": "enterprise-ai"},
            ),
        )

    async def stop(self) -> None:
        if self._container is None:
            return
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._container.remove(force=True),
            )
        except Exception:
            pass
        finally:
            self._container = None

    async def exec(self, command: str, timeout: float = 30.0) -> ExecResult:
        if self._container is None:
            return ExecResult(output="Sandbox not started", exit_code=1)

        try:
            exit_code, output = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self._container.exec_run(
                        ["bash", "-c", command],
                        workdir=self._working_dir,
                        demux=False,
                    ),
                ),
                timeout=timeout,
            )
            decoded = (output or b"").decode(errors="replace").strip()
            return ExecResult(output=decoded or "(no output)", exit_code=exit_code or 0)

        except asyncio.TimeoutError:
            return ExecResult(
                output=f"Command timed out after {timeout}s",
                exit_code=124,
                timed_out=True,
            )
        except Exception as e:
            return ExecResult(output=str(e), exit_code=1)

    async def write_file(self, path: str, content: str) -> None:
        if self._container is None:
            raise RuntimeError("Sandbox not started")

        target = path if path.startswith("/") else f"{self._working_dir}/{path}"
        encoded = content.encode("utf-8")

        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            info = tarfile.TarInfo(name=Path(target).name)
            info.size = len(encoded)
            tar.addfile(info, io.BytesIO(encoded))
        buf.seek(0)

        parent = str(Path(target).parent)
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self._container.put_archive(parent, buf.getvalue()),
        )

    async def read_file(self, path: str) -> str:
        if self._container is None:
            raise RuntimeError("Sandbox not started")

        target = path if path.startswith("/") else f"{self._working_dir}/{path}"

        bits, _ = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self._container.get_archive(target),
        )

        buf = io.BytesIO()
        for chunk in bits:
            buf.write(chunk)
        buf.seek(0)

        with tarfile.open(fileobj=buf) as tar:
            member = tar.getmembers()[0]
            f = tar.extractfile(member)
            if f is None:
                return ""
            return f.read().decode(errors="replace")

    @property
    def container_id(self) -> str:
        return self._container_id

    @property
    def working_dir(self) -> str:
        return self._working_dir
