# 0002 — Add-on-only; standalone mode removed, fork no longer tracks upstream

Upstream `Tediore/audioflow2mqtt` supports running standalone (config via environment
variables, comma-separated device IPs). The original add-on already hardcoded
`config_file = True`, making that branch unreachable, but the dead code remained.

We have **committed this fork to Home Assistant add-on use only**: config is read
solely from `/data/options.json` plus the Supervisor services API, and the env-var /
standalone path has been removed. As a consequence this fork **no longer aims to be
mergeable with upstream** — we restructure freely (async rewrite, package layout,
Supervisor integration) without preserving upstream's shape.

Recorded because a reader seeing options-only config will wonder why the standalone
mode upstream advertises is gone. The trade-off: we lose standalone portability in
exchange for a simpler, single-purpose codebase. Re-adding a standalone config source
later would be possible but is explicitly out of scope.
