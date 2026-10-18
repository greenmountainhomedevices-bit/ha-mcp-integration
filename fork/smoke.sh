#!/bin/zsh
# Static check of the built tree, run from the repo root after fork/build.py:
# a Python 3.14 env with the pinned Home Assistant and fork/requirements.lock,
# a stale PyPI ha-mcp planted in site-packages, then the component imports, the
# bundled copy must win, and ha-mcp's own smoke test must pass. Talks to no
# Home Assistant instance.
set -euo pipefail
root=${0:A:h:h}
ha=$(python3 -c "import json;print(json.load(open('$root/fork/UPSTREAM.json'))['home_assistant_pinned_against'])")
env=$root/fork/.cache/smoke
work=$(mktemp -d)
trap 'rm -rf $work' EXIT

rm -rf $env
uv venv -q --python 3.14 $env
curl -sfL "https://raw.githubusercontent.com/home-assistant/core/$ha/homeassistant/package_constraints.txt" -o $work/constraints.txt
grep -v '^#' $root/fork/requirements.lock > $work/reqs.txt
VIRTUAL_ENV=$env uv pip install -q "homeassistant==$ha" -r $work/reqs.txt -c $work/constraints.txt
VIRTUAL_ENV=$env uv pip install -q --no-deps "ha-mcp==8.6.0"

cd $root
$env/bin/python -W ignore - <<'EOF'
import compileall, importlib.metadata as md, os, sys
assert compileall.compile_dir("custom_components/ha_mcp_tools", quiet=1), "compile failed"
sys.path.insert(0, ".")
stale = md.version("ha-mcp")
from custom_components.ha_mcp_tools import (bundled_server, config_flow, coordinator,
    embedded_entry, embedded_server, embedded_setup, update)
version = bundled_server.activate()
import ha_mcp, ha_mcp.server
assert ha_mcp.__file__.startswith(str(bundled_server.VENDOR_DIR)), ha_mcp.__file__
assert md.version("ha-mcp") == version
assert os.environ["HA_MCP_DISABLE_UPDATE_CHECK"] == "1"
assert embedded_server._is_compatible_embedded_version(version)
print(f"component imports; bundled ha-mcp {version} wins over planted {stale}")
EOF
find custom_components -name __pycache__ -prune -exec rm -rf {} +
VIRTUAL_ENV=$env uv pip uninstall -q ha-mcp
cd custom_components/ha_mcp_tools/vendor
$env/bin/python -W ignore -m ha_mcp.smoke_test | tail -5
find . -name __pycache__ -prune -exec rm -rf {} +
