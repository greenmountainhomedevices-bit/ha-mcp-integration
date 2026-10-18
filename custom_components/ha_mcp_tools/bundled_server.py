"""Fork: serve the ha-mcp package bundled in ``vendor/``, never a pip install.

Upstream installs and auto-updates ``ha-mcp`` from PyPI at runtime. This fork
ships the reviewed server inside the component instead (see fork/UPSTREAM.json
in the repository), so the only way new server code arrives is a new component
release. Importing this module puts ``vendor/`` first on ``sys.path``, ahead of
any ``ha_mcp`` an earlier upstream install left in site-packages, so both the
import and ``importlib.metadata`` resolve to the bundled copy.
"""

from __future__ import annotations

import importlib
import importlib.metadata
import importlib.util
import json
import os
import sys
from pathlib import Path

VENDOR_DIR = Path(__file__).resolve().parent / "vendor"
DIST_NAME = "ha-mcp"

# The server's PyPI update check only reports releases this fork will not take.
os.environ.setdefault("HA_MCP_DISABLE_UPDATE_CHECK", "1")

if str(VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(VENDOR_DIR))


class BundledServerError(RuntimeError):
    """The bundled server is missing or shadowed."""


def activate() -> str:
    """Return the bundled server version after checking it is what imports (blocking)."""
    vendor = str(VENDOR_DIR)
    if sys.path[0] != vendor:
        rest = [p for p in sys.path if p != vendor]
        sys.path[:] = [vendor, *rest]
    importlib.invalidate_caches()
    dist_infos = sorted(VENDOR_DIR.glob("ha_mcp-*.dist-info"))
    if len(dist_infos) != 1:
        raise BundledServerError(
            f"Expected one bundled ha_mcp dist-info in {VENDOR_DIR}, found {len(dist_infos)}; "
            "reinstall the component."
        )
    version = importlib.metadata.Distribution.at(dist_infos[0]).version
    loaded = sys.modules.get("ha_mcp")
    origin = getattr(loaded, "__file__", None) if loaded else None
    if origin is None:
        spec = importlib.util.find_spec("ha_mcp")
        origin = spec.origin if spec else None
    if origin is None or not Path(origin).resolve().is_relative_to(VENDOR_DIR):
        raise BundledServerError(
            f"ha_mcp resolves to {origin}, not the bundled copy in {VENDOR_DIR}; "
            "restart Home Assistant."
        )
    if importlib.metadata.version(DIST_NAME) != version:
        raise BundledServerError(
            f"Package metadata reports ha-mcp {importlib.metadata.version(DIST_NAME)} "
            f"but the bundled copy is {version}; restart Home Assistant."
        )
    return version


def pin_drift() -> list[str]:
    """Return 'name installed (pinned X)' for each manifest pin not installed as pinned (blocking).

    Home Assistant installs requirements one by one with --upgrade, and a later
    install of another integration can lift a shared dependency, so the pins can
    drift after the fact. The next restart reinstalls whatever drifted.
    """
    manifest = json.loads((VENDOR_DIR.parent / "manifest.json").read_text(encoding="utf-8"))
    drift = []
    for requirement in manifest.get("requirements", []):
        name, sep, pinned = requirement.partition("==")
        if not sep:
            continue
        try:
            installed = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            installed = "missing"
        if installed != pinned:
            drift.append(f"{name} {installed} (pinned {pinned})")
    return drift
