# 0004 — Build with uv on a Debian slim base

Home Assistant add-ons conventionally install dependencies with `pip`, typically on
the Home Assistant base images or Alpine. We instead manage dependencies with **uv**
(`pyproject.toml` plus a committed `uv.lock`) and install them in the image with
`uv sync --frozen` from the lockfile, on a **Debian `python:3-slim`** base, building
the add-on locally from source.

uv gives reproducible, lockfile-pinned installs and a fast local development workflow.
We chose Debian slim over Alpine because uv's musl (Alpine) support is unreliable
across the supported architectures — notably 32-bit ARM — and every runtime
dependency is a pure-Python wheel, so Alpine offers no size benefit.

Recorded because this deviates from the common pip-on-Alpine / HA-base pattern;
without it a maintainer would likely "fix" it by reverting to pip or Alpine.

## Consequences

- `armhf` (ARMv6) is not supported, because uv has no binary for that architecture.
- Dependency changes must regenerate `uv.lock` (`make lock`); the image build installs
  from the lockfile, not from loose version ranges.
- The base image is pinned directly with `FROM python:3.12-slim` in the Dockerfile, not
  via `build.yaml`/`BUILD_FROM`. The current Home Assistant builder ignores `build.yaml`
  and otherwise injects its Alpine base (no pip/python) through the `BUILD_FROM` arg,
  which broke the build. `python:3.12-slim` is a multi-arch manifest, so each host still
  builds its own architecture.
