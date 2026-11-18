"""Run fixed CLI commands with a timeout. Never pass user input as argv."""
import asyncio
import shutil
from dataclasses import dataclass

from ..core.config import settings


@dataclass
class Result:
    ok: bool
    stdout: str
    stderr: str
    code: int | None  # None: binary missing or timed out
    missing: bool = False
    timed_out: bool = False


async def run(*argv: str, timeout: float | None = None) -> Result:
    if shutil.which(argv[0]) is None:
        return Result(False, "", f"{argv[0]} not found on PATH", None, missing=True)
    proc = await asyncio.create_subprocess_exec(
        *argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout or settings.command_timeout_seconds)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        return Result(False, "", f"{' '.join(argv[:2])} timed out", None, timed_out=True)
    return Result(proc.returncode == 0, out.decode(errors="replace").strip(),
                  err.decode(errors="replace").strip(), proc.returncode)
