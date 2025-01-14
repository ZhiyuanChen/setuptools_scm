from __future__ import annotations

import os
import shlex
import subprocess
from typing import Mapping

from . import _trace
from . import _types as _t


def no_git_env(env: Mapping[str, str]) -> dict[str, str]:
    # adapted from pre-commit
    # Too many bugs dealing with environment variables and GIT:
    # https://github.com/pre-commit/pre-commit/issues/300
    # In git 2.6.3 (maybe others), git exports GIT_WORK_TREE while running
    # pre-commit hooks
    # In git 1.9.1 (maybe others), git exports GIT_DIR and GIT_INDEX_FILE
    # while running pre-commit hooks in submodules.
    # GIT_DIR: Causes git clone to clone wrong thing
    # GIT_INDEX_FILE: Causes 'error invalid object ...' during commit
    for k, v in env.items():
        if k.startswith("GIT_"):
            _trace.trace(k, v)
    return {
        k: v
        for k, v in env.items()
        if not k.startswith("GIT_")
        or k in ("GIT_EXEC_PATH", "GIT_SSH", "GIT_SSH_COMMAND")
    }


def avoid_pip_isolation(env: Mapping[str, str]) -> dict[str, str]:
    """
    pip build isolation can break Mercurial
    (see https://github.com/pypa/pip/issues/10635)

    pip uses PYTHONNOUSERSITE and a path in PYTHONPATH containing "pip-build-env-".
    """
    new_env = {k: v for k, v in env.items() if k != "PYTHONNOUSERSITE"}
    if "PYTHONPATH" not in new_env:
        return new_env

    new_env["PYTHONPATH"] = os.pathsep.join(
        [
            path
            for path in new_env["PYTHONPATH"].split(os.pathsep)
            if "pip-build-env-" not in path
        ]
    )
    return new_env


def ensure_stripped_str(str_or_bytes: str | bytes) -> str:
    if isinstance(str_or_bytes, str):
        return str_or_bytes.strip()
    else:
        return str_or_bytes.decode("utf-8", "surrogateescape").strip()


def run(
    cmd: _t.CMD_TYPE,
    cwd: _t.PathT,
    *,
    strip: bool = True,
    trace: bool = True,
    timeout: int = 20,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)
    else:
        cmd = [os.fspath(x) for x in cmd]
    if trace:
        _trace.trace_command(cmd, cwd)
    res = subprocess.run(
        cmd,
        capture_output=True,
        cwd=str(cwd),
        env=dict(
            avoid_pip_isolation(no_git_env(os.environ)),
            # os.environ,
            # try to disable i18n
            LC_ALL="C",
            LANGUAGE="",
            HGPLAIN="1",
        ),
        text=True,
        timeout=timeout,
    )
    if strip:
        if res.stdout:
            res.stdout = ensure_stripped_str(res.stdout)
            res.stderr = ensure_stripped_str(res.stderr)
    if trace:
        if res.stdout:
            _trace.trace("out:\n", res.stdout, indent=True)
        if res.stderr:
            _trace.trace("err:\n", res.stderr, indent=True)
        if res.returncode:
            _trace.trace("ret:", res.returncode)
    if check:
        res.check_returncode()
    return res
