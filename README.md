<p align="center">
  <a href="https://github.com/brunonlinespace/brunonlinespace/blob/main/linspectacles/autostart-inspector.png">
    <img
      src="https://raw.githubusercontent.com/brunonlinespace/brunonlinespace/main/linspectacles/autostart-inspector.png"
      alt="Autostart Inspector screenshot"
      width="900"
    >
  </a>
</p>

# Autostart Inspector

**Expose. Explore. Explain.**

Autostart Inspector is a read-only inspector for Linux automatic-start and scheduled-launch configuration. It brings several distinct startup mechanisms into one inventory while keeping the mechanism and source of each entry visible.

Current release: **0.0.5**

Repository: <https://github.com/linspectacles/autostart-inspector>

## What Autostart Inspector is

Autostart Inspector answers a focused question: **what is configured to start automatically or on a schedule, and through which Linux mechanism?**

Autostart Inspector is inspired in part by **Microsoft Sysinternals Autoruns**: the shared idea is to bring otherwise scattered automatic-start mechanisms into one inspectable inventory. The implementation remains Linux-native, using systemd, XDG autostart, cron/anacron and supported legacy startup mechanisms.

It keeps acquisition and interpretation close to the Linux interfaces actually used by the applet. When a source is unavailable, restricted, or does not report a field, the README does not imply that the applet can manufacture the missing information.

## Highlights

- Enabled systemd **system services and timers**.
- Enabled systemd **user services and timers** for the current user.
- XDG desktop-session autostart entries from user and system autostart directories.
- System cron configuration, periodic cron directories, and the current user's `crontab -l`.
- Anacron configuration and legacy `rc.local` / SysV `S*` startup links where present.
- Search and Category filtering operate on the acquired inventory and do not trigger new acquisition.
- Automatic scanning is optional and defaults off on first use; manual mode exposes **Scan / Scan Again**.

## Data sources and acquisition

- `systemctl list-unit-files --state=enabled,enabled-runtime` and read-only `systemctl show` metadata.
- `systemctl --user ...` equivalents where the current user's manager is available.
- `$XDG_CONFIG_HOME/autostart/*.desktop` and `$XDG_CONFIG_DIRS/autostart/*.desktop`.
- `/etc/crontab`, `/etc/cron.d/*`, periodic cron directories, and current-user `crontab -l`.
- `/etc/anacrontab`.
- `/etc/rc.local`, `/etc/rc.d/rc.local`, `/etc/rc?.d/S*`, and `/etc/rc.d/rc?.d/S*`.

The applet uses those sources according to the acquisition paths implemented in this release. Optional tools or privileged helpers only affect the views/actions that explicitly use them; they are not treated as silent substitutes for unrelated sources.

## Interface

Autostart Inspector follows the LinSpectacles inventory + **Metadata Details** pattern where applicable: an acquired inventory remains separate from the details for the selected record, and search/filter controls operate on the data the applet has actually collected.

The applet's **Options** surface provides the presentation/source/about controls implemented by this release, together with export controls where present in the source. Applet-specific actions remain explicit rather than being folded into background collection.

## Read-only and scope boundaries

The inventory reports configuration visible to the current user; it does not claim that an entry successfully executed. Disabled systemd unit files are not added merely because they exist, static dependency-only units are not guessed into the inventory, and other users' protected crontabs are not read. The applet never enables, disables, edits, starts, stops or executes an entry.

## Useful keyboard shortcuts

| Command | Shortcut |
| --- | --- |
| Show / hide Metadata Details | `F3` |
| Toggle Horizontal / Vertical details | `Ctrl+L` |
| Repeat current scan | `Shift+F5` |
| Toggle automatic scan | `Ctrl+Shift+F5` |
| Options | `Ctrl+/` |

## Running from source

The supplied source is directly runnable on Linux. The Python-side requirements are:

- Python 3.
- PyQt6 for the graphical interface.

Create a local virtual environment if you do not already have the required Python packages in the environment you want to use:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install PyQt6
python3 linspectacles_autostart_inspector/standalone.py
```

Linux commands, procfs/sysfs interfaces, system services, or optional helpers mentioned in **Data sources and acquisition** are applet-specific runtime inputs. A missing optional source is handled by the applet's existing availability/error path; it is not replaced here with an invented dependency or capability.

No RPM installation instructions are included in this README.

## Source layout and LinSpectacles integration

The applet source is contained in:

```text
linspectacles_autostart_inspector/
├── __init__.py
├── standalone.py
├── LICENSE
├── applet.json
├── README.md
└── autostart_inspector/
    ├── applet.py
    ├── _support.py
    ├── collector.py
    └── icon.png
```

`applet.json` supplies the LinSpectacles applet identity and entrypoint metadata. `standalone.py` launches the applet directly, while the package's applet factory provides the host-loadable LinSpectacles integration used by the source.

## Configuration

Presentation and inspection preferences are persisted only through the settings mechanisms already implemented by the applet. Persisted UI state does not grant the applet permission to modify the inspected Linux subsystem.

## Scope

Autostart Inspector is intentionally specialist. Related Linux information that belongs to another LinSpectacles subsystem remains outside this applet rather than being inferred or duplicated here.

## License

GNU General Public License v3.0 or later. See [`LICENSE`](LICENSE).

## Links

- LinSpectacles organisation: <https://github.com/linspectacles/>
- Repository: <https://github.com/linspectacles/autostart-inspector>
- Issues: <https://github.com/linspectacles/autostart-inspector/issues>

<p align="center">
  <a href="https://github.com/linspectacles/autostart-inspector">
    <img
      src="autostart_inspector/icon.png"
      alt="Autostart Inspector"
      width="256"
    >
  </a>
</p>
