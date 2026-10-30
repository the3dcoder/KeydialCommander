# Ubuntu package implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Ship an Ubuntu 26.04 preview package with explicit remapping startup, safe upgrades, and clear installation instructions.

**Architecture:** Stage a validated pure-Python wheel into Debian's system Python paths and build with dpkg-deb. Keep desktop startup and package lifecycle handling in separate, independently tested helpers. Qualify installation in a private Ubuntu root filesystem without host input or service access.

**Tech stack:** Python, pytest, dpkg-deb, systemd user units, GTK3/WebKit, Ubuntu APT.

**Spec:** `docs/superpowers/specs/2026-10-30-ubuntu-package-design.md`.

## Global constraints

- Python version `1.3.0a2`; Debian version `1.3.0~a2-1`; package name `huion-keydial-mini-driver`.
- Earl <earl@bigbwain.com> authors and commits all changes and tags.
- No service enable/start/restart at install, upgrade or removal; preserve profiles and user overrides.
- Use `/usr/lib/python3/dist-packages` with metadata and built UI; no runtime Node, pip or checkout.
- No host service changes or physical capture. Namespace/rootfs limitations remain explicit.
- Preserve `v1.3.0a1`; publish new artifacts only after verification and review.

## Review focus

- A user-local service masks the vendor service: explain migration without deleting it (Task 2).
- An active unit refuses to stop: fail before files change and keep maintenance protection (Task 1).
- A stale port file or another listener answers: reject invalid ports/version mismatch within the startup deadline (Task 2).
- Foreign-root maintscripts encounter host managers: make no host calls (Task 1).
- Removal leaves bytecode or changes profiles: clean owned bytecode and preserve guest profile hashes (Tasks 1 and 4).

### Task 1: Package lifecycle safety

**Files:** Create `packaging/debian/lifecycle.py`, `tests/test_debian_lifecycle.py`; modify vendor user unit.

**Interfaces:** Produce `maintain(script: str, action: str, root: Path, run: Callable) -> None`; command runner accepts argument arrays and returns CompletedProcess. Constants define exact unit, package and marker. Builder embeds the self-contained helper in executable Python maintscripts.

- [x] Write behavioral tests for multiple active managers, owned/unowned units, stop/query failure, marker ordering, foreign roots and abort cleanup. Run pytest and observe missing behavior.
- [x] Implement bounded subprocess calls, parsed systemd properties, verified stop, maintenance marker and owned bytecode cleanup. Postinst only refreshes metadata/udev and optionally loads uinput on a real host.
- [x] Run lifecycle tests; verify no start/enable/restart or host calls from foreign roots.

### Task 2: Explicit desktop startup

**Files:** Create `packaging/shell/service_startup.py`, `tests/test_shell_startup.py`; modify `commander_shell.py`, wrapper and Makefile shell target.

**Interfaces:** Produce `start_service(...) -> str` returning verified loopback URL, `stop_service(...) -> None`, and `StartupError`; inject command runner, status reader and clock at external boundaries. Shell lazily imports helper for explicit flags.

- [x] Write failing tests for verified success, masked unit, legacy rule, failed start/stop, malformed port, API version mismatch and bounded timeout.
- [x] Implement vendor-unit verification, daemon-reload, explicit start/stop, readiness polling and useful dialog/stderr errors. Plain shell invocation retains preview behavior; system wrapper chooses system shell before local fallback.
- [x] Run startup tests and existing packaging tests.

### Task 3: Native binary builder

**Files:** Create `packaging/debian/build_deb.py`, `tests/test_debian_package.py`; replace obsolete Debian build entrypoint/metadata; modify pyproject and Makefile.

**Interfaces:** Consume Task 1 lifecycle source and Task 2 launcher assets. Produce `build(wheel: Path, output: Path) -> Path`, invoked by `python3 packaging/debian/build_deb.py WHEEL --output-dir DIR`.

- [x] Write failing tests that build/extract a real wheel fixture into a real deb, inspect installed metadata, executable entry points, UI assets, desktop actions, dependencies and maintscript foreign-root behavior. Reject traversal, wrong metadata, native wheel/data layout, missing UI and unexpected entry points.
- [x] Implement strict wheel staging, version conversion, Earl metadata, no preset, dpkg-deb build and reproducible file modes. Replace stale debhelper instructions with the supported wheel-fed build.
- [x] Run all package/startup/lifecycle tests; build new UI and wheel, then build real a1 upgrade fixture and a2 deb.

### Task 4: Clean installation evidence and delivery

**Files:** Update README, INSTALL, RELEASING, ROADMAP and handoff; add `docs/releases/1.3.0a2.md` and dated qualification evidence.

**Interfaces:** Consume Task 3 native artifacts. Public release includes `.deb`, wheel and SHA256SUMS; optional generic preview remains linked separately.

- [ ] In the signed Ubuntu Base rootfs, use public APT repositories to install a1 native fixture and upgrade a2; verify CLI/version/API/built UI with no checkout or Node, and remove/purge while preserving profile hashes. Record exact tool/rootfs limits; if PRoot is prohibited, report the measured limitation and use extract/foreign-root checks without claiming installation qualification.
- [ ] Run full Python suite excluding physical capture, isolated Playwright suite, web build and lint. Obtain one fresh whole-branch review; fix material findings with regression tests and rerun relevant checks.
- [ ] Commit as Earl, create reviewed PR and new annotated tag, verify uploaded draft artifacts, publish prerelease and integrate locally as Earl. Update public documentation to the verified install path and remaining qualification limits.

## Pre-flight interfaces

Task 1 → Task 3: lifecycle is self-contained and Python 3.8 compatible; builder embeds code rather than importing installed application.
Task 2 → Task 3: desktop startup helper ships beside shell; native desktop adds explicit-start flag, preview entry stays unchanged.
Task 3 → Task 4: wheel version drives Debian version and expected API version; only a2 is a new public native release, a1 is an internal fixture.
