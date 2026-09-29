from pathlib import Path

from devin_janitor.paths import DevinPaths, default_data_root, resolve


def test_env_override_wins(monkeypatch):
    monkeypatch.setenv("DEVIN_DATA_DIR", "/custom/devin")
    assert default_data_root(platform="win32") == Path("/custom/devin")


def test_windows_uses_appdata():
    env = {"APPDATA": r"C:\Users\x\AppData\Roaming"}
    root = default_data_root(environ=env, platform="win32")
    assert root == Path(env["APPDATA"]) / "devin"


def test_macos_and_linux():
    assert "Application Support" in str(
        default_data_root(environ={}, platform="darwin")
    )
    root = default_data_root(environ={}, platform="linux")
    assert root.name == "devin" and root.parent.name == ".config"


def test_layout_derived_from_root(tmp_path):
    p = DevinPaths.from_root(tmp_path / "devin")
    assert p.sessions_db == p.root / "cli" / "sessions.db"
    assert p.acp_messages_dir == p.root / "User" / "acp-messages"
    assert p.session_locks_dir == p.root / "cli" / "session_locks"


def test_resolve_explicit_overrides(tmp_path):
    p = resolve(
        data_dir=tmp_path / "d",
        sessions_db=tmp_path / "other.db",
        acp_messages_dir=tmp_path / "acp",
        session_locks_dir=tmp_path / "locks",
    )
    assert p.sessions_db == tmp_path / "other.db"
    assert p.acp_messages_dir == tmp_path / "acp"
    assert p.session_locks_dir == tmp_path / "locks"
