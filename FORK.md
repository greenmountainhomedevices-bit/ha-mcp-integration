# Bundled fork of ha-mcp-integration

Upstream's component pip-installs the `ha-mcp` server from PyPI at runtime and,
by default, upgrades it to every new PyPI release on its own. This fork ships a
reviewed server inside the component instead. New server code arrives only
when a new release of this repository is installed through HACS.

## What differs from upstream

- `custom_components/ha_mcp_tools/vendor/` holds the `ha-mcp` server, unpacked
  from a wheel built from the upstream tag in `fork/UPSTREAM.json`. The build
  also downloads PyPI's wheel for that version and refuses to continue unless
  the two hold identical files.
- `fork/patches/0001-bundled-server.patch`:
  - `bundled_server.py` puts `vendor/` first on `sys.path` and checks that
    `ha_mcp` imports from there.
  - `_async_ensure_package` only activates the bundled copy. Every pip/uv
    install, upgrade and uninstall path in `embedded_server.py` is unreachable.
  - The update coordinator no longer asks PyPI for the latest version, so the
    server update entity never offers an install and auto-update never reloads.
  - `HA_MCP_DISABLE_UPDATE_CHECK=1` turns off the server's own PyPI notice.
- `manifest.json` pins every requirement Home Assistant does not already ship
  to an exact version (`fork/requirements.lock`), resolved against Home
  Assistant's own constraints, ignoring any release younger than 7 days
  (`--cooldown-days`). Home Assistant installs manifest requirements one at a
  time with `--upgrade`, which lifts each one's dependencies to their newest
  release, so the list is ordered dependents-first: every exact pin installs
  after everything that depends on it and lands last.
- After start-up the component compares installed versions with the pins and
  logs `HA-MCP pinned requirements drifted: …` if anything moved (another
  integration's install can lift a shared package). A restart reinstalls the
  pinned versions.
- Releases carry `ha_mcp_tools.zip` (HACS `zip_release`); the release notes
  give its sha256.
- Upstream's GitHub workflows are removed and Actions are off.

Still fetched from PyPI, always at exact versions: the pinned requirements
above, and `quickjs-ng==0.17.0.1`, which the dashboard-card helper installs on
first use (upstream behaviour, already pinned). Packages Home Assistant itself
ships stay Home Assistant's.

The options flow still shows channel, auto-update and pip-spec fields; this
fork ignores them.

## Rebuilding for a new upstream release

The review-and-upgrade procedure lives in the ha-config repository
(`.claude/skills/ha-mcp-fork-upgrade`). The build itself:

```sh
uv run --no-project --python 3.13 fork/build.py --tag vX.Y.Z --ha <HA version> --rev 1 --zip
zsh fork/smoke.sh
```

`fork/smoke.sh` installs the pinned Home Assistant into a throwaway Python 3.14
env, installs the manifest requirements the way Home Assistant does (in order,
one at a time, `--upgrade`) and fails on any drift, plants a stale PyPI
`ha-mcp`, and checks the component imports, the bundled copy wins, and ha-mcp's
own smoke test passes.

If the patch stops applying, rebuild with `--no-patches`, redo the edits the
patch describes by hand, regenerate it with `git diff` (add `-N` the new file
first), and rebuild normally.

`--rev` counts fork builds of the same upstream tag. The manifest version is
`<component version>.<rev>`, and the release tag is `v<manifest version>`.
