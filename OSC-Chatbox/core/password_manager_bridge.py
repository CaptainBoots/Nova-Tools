"""
core/password_manager_bridge.py
──────────────────────────────────
Optional helpers to pull the master password FROM a password manager's
own CLI instead of the person typing it. Deliberately narrow, on
purpose:

  - Only ever READS one named item; never writes, creates, or lists.
  - The retrieved secret only ever travels back to us over the
    subprocess's stdout pipe. It is NEVER passed as a command-line
    argument to any of these tools — command-line args are visible to
    every other process on the machine via the OS process list
    (`ps aux` on Linux/macOS, the Task Manager "Command line" column on
    Windows), so putting a secret there would leak it exactly the way
    we're trying to avoid.
  - Nothing in this module logs, prints, or writes the retrieved value
    anywhere. The caller (ui/master_password_dialog.py) is responsible
    for holding it only in memory for as short a time as possible.
  - `shell=False` always — avoids both shell-injection risk and the
    secret ever touching shell history.
  - If a CLI isn't installed, isn't authenticated, or the vault is
    locked, every function here fails quietly (returns None) rather
    than raising — a "not set up" password manager should never break
    the dialog, just make that button not do anything useful.
"""

from __future__ import annotations

import shutil
import subprocess

TIMEOUT_SEC = 10


def _run_capture(cmd: list[str], input_text: str | None = None) -> str | None:
    """Run a CLI command, returning stripped stdout, or None on any
    failure (missing binary, non-zero exit, timeout, locked vault,
    wrong item name, etc.) — deliberately not distinguishing WHY it
    failed, so a caller can't be used to probe whether an item exists."""
    try:
        result = subprocess.run(
            cmd,
            input=input_text,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SEC,
            shell=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def available_managers() -> list[str]:
    """Which supported CLIs are actually installed on this machine —
    used by the dialog to decide which buttons are worth showing at
    all, rather than presenting three buttons where two always fail."""
    found = []
    if shutil.which("op"):
        found.append("1password")
    if shutil.which("bw"):
        found.append("bitwarden")
    if shutil.which("keepassxc-cli"):
        found.append("keepassxc")
    return found


def get_from_1password(item_reference: str) -> str | None:
    """`item_reference` is a full 'op://vault/item/field' secret
    reference, or a plain item name (op resolves it against your
    default vault). Requires the 1Password desktop app's CLI
    integration to already be unlocked — that unlock state, and any
    biometric/prompt it needs, is entirely 1Password's own UI, never
    ours."""
    if not shutil.which("op"):
        return None
    return _run_capture(["op", "read", item_reference])


def get_from_bitwarden(item_name: str) -> str | None:
    """Requires `bw unlock` to have already been run in this shell
    session (or BW_SESSION set) — same principle as 1Password: we never
    ask for or touch Bitwarden's own vault password ourselves."""
    if not shutil.which("bw"):
        return None
    return _run_capture(["bw", "get", "password", item_name])


def get_from_keepassxc(db_path: str, entry_title: str, db_password: str) -> str | None:
    """KeePassXC's CLI, unlike the other two, has no ambient
    'already-unlocked' desktop-app state to lean on — it needs the
    vault's own password on every single call. That password is piped
    in via stdin (the tool prompts for it on stdin when given -q),
    never as an argument, for the same process-list-leak reason
    documented at the top of this file."""
    if not shutil.which("keepassxc-cli"):
        return None
    return _run_capture(
        ["keepassxc-cli", "show", "-a", "Password", "-q", db_path, entry_title],
        input_text=db_password + "\n",
    )
