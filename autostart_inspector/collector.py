#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only automatic-start configuration collectors for Autostart Inspector."""

from __future__ import annotations
import configparser
import os
import shlex
import subprocess
from pathlib import Path

SYSTEMD_ENABLED_STATES = {"enabled", "enabled-runtime"}

def _run(args, timeout=8):
    try:
        cp = subprocess.run(args, capture_output=True, text=True, check=False, timeout=timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        return None, str(exc)
    return cp, ""

def _systemctl_prefix(scope):
    return ["systemctl", "--user"] if scope == "User" else ["systemctl"]

def _parse_systemd_show(text):
    result = {}
    current = {}
    for raw in (text or "").splitlines():
        line = raw.rstrip("\n")
        if not line:
            if current.get("Id"):
                result[current["Id"]] = dict(current)
            current = {}
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key == "Id" and current.get("Id") and current["Id"] != value:
            result[current["Id"]] = dict(current)
            current = {}
        current[key] = value
    if current.get("Id"):
        result[current["Id"]] = dict(current)
    return result

def _systemd_metadata(scope, units):
    if not units:
        return {}
    props = [
        "Id", "Description", "LoadState", "ActiveState", "SubState",
        "UnitFileState", "FragmentPath", "SourcePath", "DropInPaths",
        "WantedBy", "RequiredBy", "TriggeredBy", "Triggers", "ExecStart",
        "NextElapseUSecRealtime", "LastTriggerUSec",
    ]
    cp, _ = _run(
        _systemctl_prefix(scope) + [
            "show", *units, "--no-pager", "--property=" + ",".join(props)
        ],
        timeout=12,
    )
    if cp is None or cp.returncode != 0:
        return {}
    return _parse_systemd_show(cp.stdout)

def collect_systemd(unit_type, scope):
    category = "Systemd Timer" if unit_type == "timer" else "Systemd Service"
    cp, error = _run(
        _systemctl_prefix(scope) + [
            "list-unit-files", f"--type={unit_type}",
            "--state=enabled,enabled-runtime",
            "--no-legend", "--no-pager", "--plain",
        ],
        timeout=10,
    )
    if cp is None:
        return [], [f"{scope} systemd {unit_type}: {error}"]
    if cp.returncode != 0:
        msg = (cp.stderr or cp.stdout or "").strip()
        return [], [f"{scope} systemd {unit_type}: {msg or 'query failed'}"]

    units = []
    basic = {}
    for raw in cp.stdout.splitlines():
        parts = raw.split()
        if len(parts) < 2:
            continue
        unit, state = parts[0], parts[1]
        if state not in SYSTEMD_ENABLED_STATES:
            continue
        units.append(unit)
        basic[unit] = {"state": state, "preset": parts[2] if len(parts) > 2 else ""}

    metadata = _systemd_metadata(scope, units)
    rows = []
    for unit in units:
        meta = metadata.get(unit, {})
        rows.append({
            "entry": unit,
            "category": category,
            "scope": scope,
            "state": basic[unit]["state"],
            "trigger": (meta.get("Triggers") or "Timer unit") if unit_type == "timer" else "Enabled unit file",
            "source": meta.get("FragmentPath") or ("systemctl --user" if scope == "User" else "systemctl"),
            "_kind": "systemd",
            "_systemd_type": unit_type,
            "_systemd_scope": scope,
            "_preset": basic[unit]["preset"],
            "_metadata": meta,
        })
    return rows, []

def _desktop_parser(path):
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    try:
        parser.read(path, encoding="utf-8")
    except (OSError, configparser.Error):
        return None
    if not parser.has_section("Desktop Entry"):
        return None
    return dict(parser.items("Desktop Entry"))

def _desktop_state(fields):
    if str(fields.get("Hidden", "")).strip().lower() == "true":
        return "Disabled"
    if str(fields.get("X-GNOME-Autostart-enabled", "")).strip().lower() == "false":
        return "Disabled"
    if fields.get("OnlyShowIn") or fields.get("NotShowIn") or fields.get("AutostartCondition"):
        return "Conditional"
    return "Enabled"

def collect_xdg_autostart():
    rows, diagnostics = [], []
    user_base = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    system_bases = [Path(x) for x in os.environ.get("XDG_CONFIG_DIRS", "/etc/xdg").split(":") if x]

    chosen = {}
    for base in reversed(system_bases):
        directory = base / "autostart"
        try:
            for path in directory.glob("*.desktop"):
                chosen[path.name] = ("System", path)
        except OSError as exc:
            diagnostics.append(f"XDG autostart {directory}: {exc}")

    user_dir = user_base / "autostart"
    try:
        for path in user_dir.glob("*.desktop"):
            chosen[path.name] = ("User", path)
    except OSError as exc:
        diagnostics.append(f"XDG autostart {user_dir}: {exc}")

    for _, (scope, path) in sorted(chosen.items(), key=lambda i: i[0].casefold()):
        fields = _desktop_parser(path)
        if fields is None:
            diagnostics.append(f"XDG autostart {path}: could not parse Desktop Entry")
            continue
        rows.append({
            "entry": fields.get("Name") or path.stem,
            "category": "XDG Autostart",
            "scope": scope,
            "state": _desktop_state(fields),
            "trigger": "Desktop session",
            "source": str(path),
            "_kind": "xdg",
            "_command": fields.get("Exec", ""),
            "_desktop_fields": fields,
        })
    return rows, diagnostics

def _meaningful_lines(path):
    try:
        lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    except (OSError, PermissionError) as exc:
        return [], str(exc)
    return list(enumerate(lines, 1)), ""

def _cron_record(source, line_no, schedule, command, scope, user=""):
    command = command.strip()
    try:
        argv = shlex.split(command, posix=True)
        entry = Path(argv[0]).name if argv else f"cron line {line_no}"
    except ValueError:
        entry = f"cron line {line_no}"
    return {
        "entry": entry or f"cron line {line_no}",
        "category": "Cron",
        "scope": scope,
        "state": "Configured",
        "trigger": schedule,
        "source": str(source),
        "_kind": "cron",
        "_command": command,
        "_schedule": schedule,
        "_cron_user": user,
        "_line_number": line_no,
    }

def _parse_cron_lines(lines, source, scope, has_user_field):
    rows = []
    for line_no, raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        first = line.split(None, 1)[0] if line.split() else ""
        if "=" in first and not line.startswith("@"):
            continue
        parts = line.split()
        if not parts:
            continue

        if parts[0].startswith("@"):
            if has_user_field:
                if len(parts) < 3: continue
                schedule, user, command = parts[0], parts[1], " ".join(parts[2:])
            else:
                if len(parts) < 2: continue
                schedule, user, command = parts[0], "", " ".join(parts[1:])
        else:
            if len(parts) < (7 if has_user_field else 6):
                continue
            schedule = " ".join(parts[:5])
            if has_user_field:
                user, command = parts[5], " ".join(parts[6:])
            else:
                user, command = "", " ".join(parts[5:])
        rows.append(_cron_record(source, line_no, schedule, command, scope, user))
    return rows

def collect_cron():
    rows, diagnostics = [], []

    system_sources = [Path("/etc/crontab")]
    cron_d = Path("/etc/cron.d")
    if cron_d.is_dir():
        try:
            system_sources += sorted(
                [p for p in cron_d.iterdir() if p.is_file() and not p.name.startswith(".")],
                key=lambda p: p.name.casefold(),
            )
        except OSError as exc:
            diagnostics.append(f"Cron {cron_d}: {exc}")

    for path in system_sources:
        if not path.exists():
            continue
        lines, error = _meaningful_lines(path)
        if error:
            diagnostics.append(f"Cron {path}: {error}")
        else:
            rows.extend(_parse_cron_lines(lines, path, "System", True))

    for period in ("hourly", "daily", "weekly", "monthly"):
        directory = Path(f"/etc/cron.{period}")
        if not directory.is_dir():
            continue
        try:
            entries = sorted(
                [p for p in directory.iterdir() if p.is_file() and not p.name.startswith(".")],
                key=lambda p: p.name.casefold(),
            )
        except OSError as exc:
            diagnostics.append(f"Cron {directory}: {exc}")
            continue
        for path in entries:
            rows.append({
                "entry": path.name,
                "category": "Cron",
                "scope": "System",
                "state": "Executable" if os.access(path, os.X_OK) else "Present",
                "trigger": period.capitalize(),
                "source": str(path),
                "_kind": "cron-directory",
                "_command": str(path),
                "_schedule": period,
                "_line_number": "",
            })

    cp, error = _run(["crontab", "-l"], timeout=5)
    if cp is None:
        if "No such file" not in error:
            diagnostics.append(f"User crontab: {error}")
    elif cp.returncode == 0:
        rows.extend(_parse_cron_lines(
            list(enumerate(cp.stdout.splitlines(), 1)), "crontab -l", "User", False
        ))
    else:
        msg = (cp.stderr or cp.stdout or "").strip()
        if msg and "no crontab for" not in msg.lower():
            diagnostics.append(f"User crontab: {msg}")
    return rows, diagnostics

def collect_anacron():
    path = Path("/etc/anacrontab")
    if not path.exists():
        return [], []
    lines, error = _meaningful_lines(path)
    if error:
        return [], [f"Anacron {path}: {error}"]

    rows = []
    for line_no, raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        first = line.split(None, 1)[0] if line.split() else ""
        if "=" in first:
            continue
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        period, delay, job_id, command = parts
        rows.append({
            "entry": job_id,
            "category": "Anacron",
            "scope": "System",
            "state": "Configured",
            "trigger": f"Period {period}; delay {delay} min",
            "source": str(path),
            "_kind": "anacron",
            "_command": command,
            "_period": period,
            "_delay": delay,
            "_line_number": line_no,
        })
    return rows, []

def collect_legacy():
    rows, diagnostics, seen = [], [], set()

    for path in (Path("/etc/rc.local"), Path("/etc/rc.d/rc.local")):
        if not path.exists():
            continue
        try:
            resolved = str(path.resolve())
        except OSError:
            resolved = str(path)
        if resolved in seen:
            continue
        seen.add(resolved)
        rows.append({
            "entry": path.name,
            "category": "Legacy Startup",
            "scope": "System",
            "state": "Executable" if os.access(path, os.X_OK) else "Present",
            "trigger": "Boot compatibility script",
            "source": str(path),
            "_kind": "rc-local",
            "_command": str(path),
        })

    paths = []
    for pattern in ("/etc/rc?.d/S*", "/etc/rc.d/rc?.d/S*"):
        paths.extend(Path("/").glob(pattern.lstrip("/")))
    for path in sorted(set(paths), key=lambda p: str(p).casefold()):
        try:
            if not path.is_symlink():
                continue
            target = os.readlink(path)
        except OSError as exc:
            diagnostics.append(f"Legacy startup {path}: {exc}")
            continue
        rows.append({
            "entry": path.name,
            "category": "Legacy Startup",
            "scope": "System",
            "state": "Configured",
            "trigger": f"SysV {path.parent.name}",
            "source": str(path),
            "_kind": "sysv",
            "_command": target,
        })
    return rows, diagnostics

def collect_all():
    rows, diagnostics = [], []
    for unit_type in ("service", "timer"):
        for scope in ("System", "User"):
            part, diag = collect_systemd(unit_type, scope)
            rows.extend(part); diagnostics.extend(diag)

    for fn in (collect_xdg_autostart, collect_cron, collect_anacron, collect_legacy):
        part, diag = fn()
        rows.extend(part); diagnostics.extend(diag)

    order = {
        "Systemd Service": 0, "Systemd Timer": 1, "XDG Autostart": 2,
        "Cron": 3, "Anacron": 4, "Legacy Startup": 5,
    }
    rows.sort(key=lambda r: (
        order.get(r.get("category"), 99),
        str(r.get("scope", "")).casefold(),
        str(r.get("entry", "")).casefold(),
        str(r.get("source", "")).casefold(),
    ))
    return rows, diagnostics
