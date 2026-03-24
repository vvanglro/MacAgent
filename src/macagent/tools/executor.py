from __future__ import annotations

import subprocess

from macagent.domain.errors import ExecutionError


class CommandExecutor:
    def run(self, command: list[str], timeout: int = 20) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                command,
                text=True,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ExecutionError(f"Command timed out: {' '.join(command)}") from exc

    def run_or_raise(self, command: list[str], timeout: int = 20) -> subprocess.CompletedProcess[str]:
        result = self.run(command, timeout=timeout)
        if result.returncode != 0:
            raise ExecutionError(result.stderr.strip() or f"Command failed: {' '.join(command)}")
        return result
