"""Locate Devin's local session stores across platforms.

The legacy script hardcoded ``%APPDATA%/devin`` on one Windows machine. This
module auto-detects the data root per OS and derives the three stores the
janitor cares about:

- ``cli/sessions.db``          — CLI session metadata + message forest
- ``User/acp-messages/``       — one ``<session-id>.db`` per GUI session
- ``cli/session_locks/``       — ``<session-id>.lock`` files for live sessions
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DevinPaths:
    """Resolved locations of Devin's local session stores."""

    root: Path
    sessions_db: Path
    acp_messages_dir: Path
    session_locks_dir: Path

    @classmethod
    def from_root(cls, root: str | Path) -> "DevinPaths":
        root = Path(root).expanduser()
        return cls(
            root=root,
            sessions_db=root / "cli" / "sessions.db",
            acp_messages_dir=root / "User" / "acp-messages",
            session_locks_dir=root / "cli" / "session_locks",
        )


def default_data_root(
    environ: dict[str, str] | None = None, platform: str | None = None
) -> Path:
    """Best-guess Devin data dir for the current OS.

    ``DEVIN_DATA_DIR`` wins when set; otherwise per-platform convention:

    - Windows: ``%APPDATA%\\devin``
    - macOS:   ``~/Library/Application Support/devin``
    - Linux:   ``~/.config/devin``
    """
    env = os.environ if environ is None else environ
    plat = sys.platform if platform is None else platform

    override = env.get("DEVIN_DATA_DIR")
    if override:
        return Path(override).expanduser()

    if plat.startswith("win"):
        appdata = env.get("APPDATA")
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
        return base / "devin"
    if plat == "darwin":
        return Path.home() / "Library" / "Application Support" / "devin"
    return Path(env.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "devin"


def resolve(
    data_dir: str | Path | None = None,
    sessions_db: str | Path | None = None,
    acp_messages_dir: str | Path | None = None,
    session_locks_dir: str | Path | None = None,
) -> DevinPaths:
    """Resolve store paths: explicit flags > ``--data-dir`` > auto-detect."""
    base = DevinPaths.from_root(
        Path(data_dir).expanduser() if data_dir else default_data_root()
    )
    return DevinPaths(
        root=base.root,
        sessions_db=Path(sessions_db).expanduser()
        if sessions_db
        else base.sessions_db,
        acp_messages_dir=Path(acp_messages_dir).expanduser()
        if acp_messages_dir
        else base.acp_messages_dir,
        session_locks_dir=Path(session_locks_dir).expanduser()
        if session_locks_dir
        else base.session_locks_dir,
    )
