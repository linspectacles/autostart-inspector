#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# LinSpectacles - Linux Inspector Suite
# Copyright (C) 2026 brunonlinespace
# GPL-3.0-or-later

APPLET_ID = "linspectacles-autostart-inspector"
APPLET_NAME = "Autostart Inspector"
APPLET_VERSION = "0.0.5"
APPLET_AUTHOR = "brunonlinespace"
APPLET_ORGANIZATION_NAME = "LinSpectacles"
APPLET_ORGANIZATION_ID = "linspectacles"
APPLET_ORGANIZATION_URL = "https://github.com/linspectacles/"
APPLET_REPOSITORY = "https://github.com/linspectacles/autostart-inspector"

from pathlib import Path
from PyQt6.QtCore import QSettings, Qt, QTimer, QUrl
from PyQt6.QtGui import QBrush, QColor, QKeySequence, QPixmap, QShortcut, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QHBoxLayout,
    QLabel, QMessageBox, QPushButton, QTabWidget, QTextEdit,
    QVBoxLayout, QWidget,
)
from ._support import BaseInspectorTab, export_records_dialog, metadata_font_qss
from .collector import collect_all

CATEGORIES = [
    "All Categories",
    "Systemd Service",
    "Systemd Timer",
    "XDG Autostart",
    "Cron",
    "Anacron",
    "Legacy Startup",
]

class AutostartOptionsDialog(QDialog):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.setWindowTitle("Options — Autostart Inspector")
        self.resize(980, 720)

        root = QVBoxLayout(self)
        tabs = QTabWidget()
        root.addWidget(tabs, 1)

        appearance_page = QWidget()
        appearance_layout = QVBoxLayout(appearance_page)
        appearance_layout.setContentsMargins(12, 12, 12, 12)
        appearance_layout.setSpacing(10)
        appearance_heading = QLabel("Metadata display")
        heading_font = appearance_heading.font()
        heading_font.setBold(True)
        appearance_heading.setFont(heading_font)
        appearance_layout.addWidget(appearance_heading)
        appearance_note = QLabel(
            "Metadata Details presents the reported configuration for the selected autostart record. "
            "Display and scan settings are remembered."
        )
        appearance_note.setWordWrap(True)
        appearance_layout.addWidget(appearance_note)

        layout_row = QHBoxLayout()
        layout_row.addWidget(QLabel("Record details layout:"))
        self.layout_combo = QComboBox()
        self.layout_combo.addItems(["Horizontal", "Vertical"])
        self.layout_combo.setCurrentText(
            "Vertical" if owner.details_orientation == "vertical" else "Horizontal"
        )
        self.layout_combo.currentTextChanged.connect(self._layout_changed)
        layout_row.addWidget(self.layout_combo)
        layout_row.addStretch(1)
        appearance_layout.addLayout(layout_row)

        self.show_metadata_panel = QCheckBox("Show Metadata Details panel (F3)")
        self.show_metadata_panel.setChecked(owner.metadata_panel_visible)
        self.show_metadata_panel.toggled.connect(self._metadata_panel_changed)
        appearance_layout.addWidget(self.show_metadata_panel)

        self.automatic_scan = QCheckBox("Enable automatic scan — Ctrl+Shift+F5")
        self.automatic_scan.setChecked(owner.automatic_scan_enabled)
        self.automatic_scan.toggled.connect(self._automatic_scan_changed)
        appearance_layout.addWidget(self.automatic_scan)

        automatic_scan_note = QLabel(
            "When enabled, Autostart Inspector scans automatically when it opens. "
            "The top-level Scan / Scan Again button is hidden. Search and Category remain local filters "
            "and do not re-run acquisition."
        )
        automatic_scan_note.setWordWrap(True)
        appearance_layout.addWidget(automatic_scan_note)

        scan_note = QLabel(
            "With automatic scan off, close this dialog and use the top-level Scan button. "
            "F3 hides/restores Metadata Details. Shift+F5 repeats the current scan. "
            "Ctrl+Shift+F5 toggles automatic scan. Ctrl+L toggles the details layout. "
            "Ctrl+/ opens Options."
        )
        scan_note.setWordWrap(True)
        appearance_layout.addWidget(scan_note)

        appearance_layout.addStretch(1)
        tabs.addTab(appearance_page, "Appearance")

        sources_page = QWidget()
        sources_layout = QVBoxLayout(sources_page)
        sources_layout.setContentsMargins(12, 12, 12, 12)
        sources_layout.setSpacing(10)
        sources_heading = QLabel("Data Sources")
        sf = sources_heading.font()
        sf.setBold(True)
        sf.setPointSize(max(sf.pointSize(), 11))
        sources_heading.setFont(sf)
        sources_layout.addWidget(sources_heading)
        sources_note = QLabel(
            "Linux interfaces used by this read-only automatic-start configuration inspector."
        )
        sources_note.setWordWrap(True)
        sources_layout.addWidget(sources_note)
        sources_text = QTextEdit()
        sources_text.setReadOnly(True)
        sources_text.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        chosen_font = getattr(owner, "_metadata_font", None)
        if chosen_font is not None:
            sources_text.setFont(chosen_font)
            sources_text.document().setDefaultFont(chosen_font)
            sources_text.setCurrentFont(chosen_font)
            font_rule = metadata_font_qss(chosen_font)
        else:
            font_rule = ""
        # Match the established LinSpectacles Sources canvas and heading treatment.
        sources_text.setStyleSheet(
            "QTextEdit { "
            + font_rule
            + " background-color: #151719; color: #dcdcdc; "
              "border: 1px solid #333333; }"
        )
        source_key_format = QTextCharFormat()
        source_key_format.setForeground(QColor("#9cdcfe"))
        source_key_format.setFontWeight(600)
        source_value_format = QTextCharFormat()
        source_value_format.setForeground(QColor("#dcdcdc"))

        cursor = sources_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        for line in owner.sources_text().splitlines():
            # The introductory statement is ordinary text, not a section heading.
            is_heading = bool(line and not line[:1].isspace()
                              and not line.startswith("Autostart Inspector is read-only."))
            cursor.insertText(
                line + "\n", source_key_format if is_heading else source_value_format
            )
        sources_text.setTextCursor(cursor)
        sources_text.moveCursor(QTextCursor.MoveOperation.Start)
        sources_text.verticalScrollBar().setValue(0)
        sources_layout.addWidget(sources_text, 1)
        tabs.addTab(sources_page, "Sources")

        export_page = QWidget()
        export_layout = QVBoxLayout(export_page)
        export_layout.setContentsMargins(12, 12, 12, 12)
        export_layout.setSpacing(10)
        export_heading = QLabel("Export details")
        ef = export_heading.font()
        ef.setBold(True)
        export_heading.setFont(ef)
        export_layout.addWidget(export_heading)
        export_note = QLabel(
            "Select the Autostart Inspector details to include in the export."
        )
        export_note.setWordWrap(True)
        export_layout.addWidget(export_note)

        self.export_entry = QCheckBox("Entry")
        self.export_category = QCheckBox("Category")
        self.export_scope = QCheckBox("Scope")
        self.export_state = QCheckBox("State")
        self.export_trigger = QCheckBox("Schedule / Trigger")
        self.export_source = QCheckBox("Source")
        self.export_metadata = QCheckBox("Metadata Details")
        for cb in (
            self.export_entry, self.export_category, self.export_scope,
            self.export_state, self.export_trigger, self.export_source
        ):
            cb.setChecked(True)
        self.export_metadata.setChecked(False)
        for cb in (
            self.export_entry, self.export_category, self.export_scope,
            self.export_state, self.export_trigger, self.export_source,
            self.export_metadata
        ):
            export_layout.addWidget(cb)

        export_layout.addStretch(1)
        export_row = QHBoxLayout()
        export_row.addStretch(1)
        export_button = QPushButton("Export...")
        export_button.clicked.connect(self._export_selected)
        export_row.addWidget(export_button)
        export_layout.addLayout(export_row)
        tabs.addTab(export_page, "Export")

        about_page = QWidget()
        about_layout = QVBoxLayout(about_page)
        about_layout.setContentsMargins(24, 20, 24, 18)
        about_layout.setSpacing(8)
        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setFixedSize(112, 112)
        icon_path = Path(__file__).resolve().parent / "icon.png"
        if icon_path.is_file():
            pixmap = QPixmap(str(icon_path))
            if not pixmap.isNull():
                icon_label.setPixmap(
                    pixmap.scaled(
                        112, 112,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
        about_layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignHCenter)
        name = QLabel("<h2 style='margin:0'>Autostart Inspector</h2>")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_layout.addWidget(name)
        version = QLabel(f"Version {APPLET_VERSION}")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_layout.addWidget(version)
        slogan = QLabel("<b>Expose. Explore. Explain.</b>")
        slogan.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_layout.addWidget(slogan)
        description = QLabel(
            "A read-only LinSpectacles applet for inspecting automatic-start and "
            "scheduled-launch configuration across common Linux mechanisms."
        )
        description.setWordWrap(True)
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_layout.addWidget(description)
        details = QLabel(
            "<b>Build:</b> Standalone LinSpectacles applet<br>"
            "<b>Organisation ID:</b> "
            f"<a href='{APPLET_ORGANIZATION_URL}'>{APPLET_ORGANIZATION_ID}</a><br>"
            f"<b>Applet ID:</b> {APPLET_ID}"
        )
        details.setWordWrap(True)
        details.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
            | Qt.TextInteractionFlag.TextSelectableByMouse
        )
        details.setOpenExternalLinks(True)
        details.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_layout.addWidget(details)
        copyright_label = QLabel(
            "Copyright © 2026 "
            "<a href='https://github.com/brunonlinespace'>brunonlinespace</a>"
        )
        copyright_label.setOpenExternalLinks(True)
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_layout.addWidget(copyright_label)
        license_label = QLabel("Licensed under GNU GPLv3 or later.")
        license_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_layout.addWidget(license_label)
        readme_url = QUrl.fromLocalFile(str(Path(__file__).resolve().parent.parent / "README.md")).toString()
        license_url = QUrl.fromLocalFile(str(Path(__file__).resolve().parent.parent / "LICENSE")).toString()
        links = QLabel(
            f"<a href='{readme_url}'>README</a> "
            "&nbsp;·&nbsp; "
            f"<a href='{license_url}'>License</a> "
            "&nbsp;·&nbsp; "
            f"<a href='{APPLET_REPOSITORY}'>Repository</a>"
        )
        links.setOpenExternalLinks(True)
        links.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_layout.addWidget(links)
        about_layout.addStretch(1)
        tabs.addTab(about_page, "About")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _layout_changed(self, text):
        self.owner.set_details_orientation(str(text).strip().lower(), persist=True)

    def _metadata_panel_changed(self, checked):
        self.owner.set_metadata_panel_visible(bool(checked), persist=True)

    def _automatic_scan_changed(self, checked):
        self.owner.set_automatic_scan_enabled(bool(checked), persist=True)

    def _export_selected(self):
        selected = []
        if self.export_entry.isChecked():
            selected.append(("entry", "Entry", 190, "left"))
        if self.export_category.isChecked():
            selected.append(("category", "Category", 145, "left"))
        if self.export_scope.isChecked():
            selected.append(("scope", "Scope", 80, "left"))
        if self.export_state.isChecked():
            selected.append(("state", "State", 105, "left"))
        if self.export_trigger.isChecked():
            selected.append(("trigger", "Schedule / Trigger", 180, "left"))
        if self.export_source.isChecked():
            selected.append(("source", "Source", 260, "left"))
        if self.export_metadata.isChecked():
            selected.append(("metadata_details", "Metadata Details", 520, "left"))

        if not selected:
            QMessageBox.information(self, "Export", "Select at least one detail to export.")
            return

        records = []
        include_metadata = self.export_metadata.isChecked()
        for record in self.owner.get_export_records():
            exported = dict(record)
            if include_metadata:
                exported["metadata_details"] = self.owner.metadata_details_for_export(record)
            records.append(exported)

        if not records:
            QMessageBox.information(self, "Export", "There is no collected data to export yet.")
            return

        path = export_records_dialog(self, APPLET_NAME, records, columns=selected)
        if path is not None:
            self.owner.set_status(f"Exported data to {path}")


class AutostartTab(BaseInspectorTab):
    def __init__(self, parent=None):
        columns = [
            ("entry", "Entry", 190, "left"),
            ("category", "Category", 145, "left"),
            ("scope", "Scope", 80, "left"),
            ("state", "State", 105, "left"),
            ("trigger", "Schedule / Trigger", 180, "left"),
            ("source", "Source", 260, "left"),
        ]
        super().__init__("Total Autostart Entries", columns, CATEGORIES, parent)
        self.export_title = APPLET_NAME
        self.search_entry.setPlaceholderText("Search autostart entries...")

        self.details_orientation = "horizontal"
        self.metadata_panel_visible = True
        self.automatic_scan_enabled = False
        self._has_scanned = False
        self._configuration_open = False
        self._auto_scan_requested = False
        self._diagnostics = []
        self._load_preferences()

        # Established compact top bar: Scan / Scan Again | Options...
        self.export_btn.setText("Options...")
        try:
            self.export_btn.clicked.disconnect()
        except TypeError:
            pass
        self.export_btn.clicked.connect(self.show_options)
        self.export_btn.setEnabled(True)

        self._auto_scan_timer = QTimer(self)
        self._auto_scan_timer.setSingleShot(True)
        self._auto_scan_timer.setInterval(250)
        self._auto_scan_timer.timeout.connect(self.load_modules)

        self._setup_shortcuts()
        self.set_metadata_panel_visible(self.metadata_panel_visible, persist=False)

        self.refresh_btn.setText("Scan")
        self._apply_scan_mode()

        # Manual scan is the first-use/default mode. Do not do expensive
        # acquisition during construction.
        self.modules_data.clear()
        self.table.setRowCount(0)
        self.clear_info()
        self.stats_label.setText(f"{self.total_label_text}: Not scanned")

        if self.automatic_scan_enabled:
            self.set_status("Automatic scan enabled. Collecting autostart configuration...")
            self._schedule_auto_scan(delay_ms=0)
        else:
            self.set_status("Not scanned. Press Scan to inspect autostart configuration.")

    def style_table_item(self, item, column_id, record):
        if column_id != "category":
            return
        color_map = {
            "Systemd Service": "#9cdcfe",
            "Systemd Timer": "#dcdcaa",
            "XDG Autostart": "#4ec9b0",
            "Cron": "#c586c0",
            "Anacron": "#ce9178",
            "Legacy Startup": "#b5cea8",
        }
        color = color_map.get(record.get("category"))
        if color:
            item.setForeground(QBrush(QColor(color)))

    def filter_modules(self, *_):
        super().filter_modules(*_)
        # BaseInspectorTab owns an Export button; Kernel Modules repurposes it
        # as Options. Keep Options available even before the first scan or when
        # a scan legitimately returns no records.
        self.export_btn.setEnabled(True)

    def load_modules(self):
        self.modules_data.clear()
        self._diagnostics = []
        self.clear_info()
        self.table.setRowCount(0)
        self._has_scanned = False
        self.stats_label.setText(f"{self.total_label_text}: Scanning...")
        self.set_status("Scanning autostart configuration...")
        self.refresh_btn.setText("Scanning...")
        self.refresh_btn.setEnabled(False)
        QApplication.processEvents()
        try:
            records, diagnostics = collect_all()
            self.modules_data.extend(records)
            self._diagnostics = list(diagnostics)
            self._has_scanned = True
            self.stats_label.setText(f"{self.total_label_text}: {len(self.modules_data)}")
            self.filter_modules()
            if diagnostics:
                self.set_status(
                    f"Observed {len(records)} autostart entries · "
                    f"{len(diagnostics)} source diagnostic(s)."
                )
            else:
                self.set_status(f"Observed {len(records)} autostart entries.")
        except Exception as exc:
            self.modules_data.clear()
            self._has_scanned = True
            self.clear_info()
            self.table.setRowCount(0)
            self.stats_label.setText(f"{self.total_label_text}: 0")
            self.set_status(f"Unavailable: {exc}")
        finally:
            self._apply_scan_mode()

    def on_module_select(self):
        record = self.current_record()
        if not record:
            self.clear_info()
            return
        self._render_record_details(record)
        self.info_text.moveCursor(QTextCursor.MoveOperation.Start)
        self.info_text.verticalScrollBar().setValue(0)
        self.set_status(
            f"Inspecting {record.get('category', 'autostart')} entry "
            f"[{record.get('entry', '')}]."
        )

    def _render_record_details(self, record):
        self.clear_info()
        self.append_info("--- Autostart Entry ---\n")
        for label, key in (
            ("Entry", "entry"), ("Category", "category"), ("Scope", "scope"),
            ("State", "state"), ("Schedule / Trigger", "trigger"), ("Source", "source"),
        ):
            self.append_key_value(label, record.get(key) or "Not reported")

        kind = record.get("_kind", "")
        if kind == "systemd":
            self.append_info("\n--- Systemd Unit ---\n")
            self.append_key_value("Unit Type", record.get("_systemd_type", ""))
            self.append_key_value("Manager Scope", record.get("_systemd_scope", ""))
            self.append_key_value("Preset", record.get("_preset") or "Not reported")
            metadata = record.get("_metadata", {}) or {}
            for label, key in (
                ("Description", "Description"), ("Load State", "LoadState"),
                ("Active State", "ActiveState"), ("Sub State", "SubState"),
                ("Unit File State", "UnitFileState"), ("Fragment Path", "FragmentPath"),
                ("Source Path", "SourcePath"), ("Drop-ins", "DropInPaths"),
                ("Wanted By", "WantedBy"), ("Required By", "RequiredBy"),
                ("Triggered By", "TriggeredBy"), ("Triggers", "Triggers"),
                ("ExecStart", "ExecStart"),
            ):
                value = metadata.get(key, "")
                if value:
                    self.append_key_value(label, value)
            if record.get("_systemd_type") == "timer":
                for label, key in (
                    ("Next Elapse", "NextElapseUSecRealtime"),
                    ("Last Trigger", "LastTriggerUSec"),
                ):
                    value = metadata.get(key, "")
                    if value:
                        self.append_key_value(label, value)

        elif kind == "xdg":
            self.append_info("\n--- XDG Desktop Autostart ---\n")
            fields = record.get("_desktop_fields", {}) or {}
            preferred = {
                "Name", "GenericName", "Comment", "Exec", "TryExec", "Hidden",
                "OnlyShowIn", "NotShowIn", "AutostartCondition",
                "X-GNOME-Autostart-enabled", "X-GNOME-Autostart-Delay",
            }
            for key in (
                "Name", "GenericName", "Comment", "Exec", "TryExec", "Hidden",
                "OnlyShowIn", "NotShowIn", "AutostartCondition",
                "X-GNOME-Autostart-enabled", "X-GNOME-Autostart-Delay",
            ):
                if key in fields:
                    self.append_key_value(key, fields[key])
            other = [(k, v) for k, v in fields.items() if k not in preferred]
            if other:
                self.append_info("\n--- Other Reported Desktop Entry Fields ---\n")
                for key, value in sorted(other, key=lambda item: item[0].casefold()):
                    self.append_key_value(key, value)

        elif kind in {"cron", "cron-directory"}:
            self.append_info("\n--- Cron Configuration ---\n")
            self.append_key_value("Schedule", record.get("_schedule") or record.get("trigger", ""))
            if record.get("_cron_user"):
                self.append_key_value("Configured User", record.get("_cron_user"))
            if record.get("_line_number"):
                self.append_key_value("Source Line", record.get("_line_number"))
            self.append_key_value("Command / Target", record.get("_command") or "Not reported")

        elif kind == "anacron":
            self.append_info("\n--- Anacron Configuration ---\n")
            self.append_key_value("Period", record.get("_period") or "Not reported")
            self.append_key_value("Delay (minutes)", record.get("_delay") or "Not reported")
            self.append_key_value("Source Line", record.get("_line_number") or "Not reported")
            self.append_key_value("Command", record.get("_command") or "Not reported")

        elif kind == "rc-local":
            self.append_info("\n--- Legacy Startup ---\n")
            self.append_key_value("Mechanism", "rc.local compatibility script")
            self.append_key_value("Script", record.get("_command") or record.get("source", ""))

        elif kind == "sysv":
            self.append_info("\n--- Legacy Startup ---\n")
            self.append_key_value("Mechanism", "SysV runlevel startup link")
            self.append_key_value("Link Target", record.get("_command") or "Not reported")

        self.append_info("\n--- Scope Notes ---\n")
        if record.get("scope") == "User":
            self.append_info(
                "This record belongs to the current user's visible configuration. "
                "Autostart Inspector does not elevate to enumerate other users' protected configuration.\n"
            )
        else:
            self.append_info(
                "This record comes from system-visible automatic-start configuration readable by the current user.\n"
            )
        self.info_text.moveCursor(QTextCursor.MoveOperation.Start)
        self.info_text.verticalScrollBar().setValue(0)

    @staticmethod
    def sources_text():
        return (
            "Autostart Inspector is read-only. Its displayed facts come from these interfaces.\n\n"
            "Enabled systemd system services and timers\n"
            "  systemctl list-unit-files --state=enabled,enabled-runtime\n"
            "  systemctl show (read-only metadata for the enabled units)\n\n"
            "Enabled systemd user services and timers for the current user\n"
            "  systemctl --user list-unit-files --state=enabled,enabled-runtime\n"
            "  systemctl --user show (where the user manager is available)\n\n"
            "XDG desktop-session autostart\n"
            "  $XDG_CONFIG_HOME/autostart/*.desktop (default ~/.config/autostart)\n"
            "  $XDG_CONFIG_DIRS/autostart/*.desktop (default /etc/xdg/autostart)\n\n"
            "Cron configuration\n"
            "  /etc/crontab\n"
            "  /etc/cron.d/*\n"
            "  /etc/cron.hourly/*, /etc/cron.daily/*, /etc/cron.weekly/*, /etc/cron.monthly/*\n"
            "  crontab -l (current user only)\n\n"
            "Anacron configuration\n"
            "  /etc/anacrontab\n\n"
            "Legacy startup mechanisms\n"
            "  /etc/rc.local\n"
            "  /etc/rc.d/rc.local\n"
            "  /etc/rc?.d/S* and /etc/rc.d/rc?.d/S*\n\n"
            "Important distinctions\n"
            "  The inventory reports configuration visible to the current user; it does not claim every entry executed successfully.\n"
            "  Disabled systemd unit files are not listed merely because they are installed.\n"
            "  Static systemd units pulled in only as dependencies are not guessed into the inventory.\n"
            "  Other users' protected crontabs are not read.\n"
            "  Cron and anacron are included because they automatically launch configured commands even when the trigger is periodic rather than boot/login.\n"
            "  No entry is enabled, disabled, edited, started, stopped or executed by this applet."
        )

    def _settings(self):
        return QSettings("brunonlinespace", "Autostart Inspector")

    @staticmethod
    def _settings_bool(value, default=False):
        if value is None:
            return bool(default)
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    def _load_preferences(self):
        settings = self._settings()
        orientation = str(
            settings.value("details_orientation", "horizontal") or "horizontal"
        ).lower()
        if orientation not in {"horizontal", "vertical"}:
            orientation = "horizontal"

        self.details_orientation = orientation
        self.metadata_panel_visible = self._settings_bool(
            settings.value("metadata_panel_visible", True), True
        )
        # First use is intentionally manual; no setting means False.
        self.automatic_scan_enabled = self._settings_bool(
            settings.value("automatic_scan_enabled", False), False
        )
        self.set_details_orientation(orientation, persist=False)

    def show_options(self):
        self._configuration_open = True
        try:
            AutostartOptionsDialog(self).exec()
        finally:
            self._configuration_open = False
            if self.automatic_scan_enabled and self._auto_scan_requested:
                self._auto_scan_requested = False
                self._schedule_auto_scan(delay_ms=0)

    def _setup_shortcuts(self):
        self._shortcuts = []

        def add_shortcut(sequence, handler):
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(handler)
            self._shortcuts.append(shortcut)
            return shortcut

        add_shortcut("F3", self._shortcut_toggle_metadata)
        add_shortcut("Ctrl+L", self._shortcut_toggle_layout)
        add_shortcut("Shift+F5", self._shortcut_repeat_scan)
        add_shortcut("Ctrl+Shift+F5", self._shortcut_toggle_automatic_scan)
        add_shortcut("Ctrl+/", self.show_options)

    def _shortcut_toggle_metadata(self):
        self.toggle_metadata_panel()
        self.set_status(
            "Metadata Details panel shown."
            if self.metadata_panel_visible
            else "Metadata Details panel hidden."
        )

    def _shortcut_toggle_layout(self):
        target = "vertical" if self.details_orientation == "horizontal" else "horizontal"
        self.set_details_orientation(target, persist=True)
        self.set_status(
            "Metadata Details layout set to Vertical."
            if target == "vertical"
            else "Metadata Details layout set to Horizontal."
        )

    def _shortcut_repeat_scan(self):
        self.set_status("Repeating autostart scan...")
        self.load_modules()

    def _shortcut_toggle_automatic_scan(self):
        self.set_automatic_scan_enabled(
            not self.automatic_scan_enabled, persist=True
        )
        self.set_status(
            "Automatic scan enabled."
            if self.automatic_scan_enabled
            else "Automatic scan disabled."
        )

    def set_metadata_panel_visible(self, visible, *, persist=True):
        visible = bool(visible)
        self.metadata_panel_visible = visible
        panel = self.splitter.widget(1)
        if panel is not None:
            panel.setVisible(visible)
        if visible:
            self.set_details_orientation(self.details_orientation, persist=False)
            if self.current_record() is not None:
                self.on_module_select()
        if persist:
            settings = self._settings()
            settings.setValue("metadata_panel_visible", visible)
            settings.sync()

    def toggle_metadata_panel(self):
        self.set_metadata_panel_visible(
            not self.metadata_panel_visible, persist=True
        )

    def set_details_orientation(self, orientation, *, persist=True):
        orientation = str(orientation or "horizontal").lower()
        if orientation not in {"horizontal", "vertical"}:
            orientation = "horizontal"
        self.details_orientation = orientation
        details_panel = self.splitter.widget(1)
        details_layout = details_panel.layout() if details_panel is not None else None
        if orientation == "vertical":
            self.splitter.setOrientation(Qt.Orientation.Vertical)
            if details_layout is not None:
                details_layout.setContentsMargins(0, 8, 0, 0)
            self.splitter.setSizes([430, 330])
        else:
            self.splitter.setOrientation(Qt.Orientation.Horizontal)
            if details_layout is not None:
                details_layout.setContentsMargins(8, 0, 0, 0)
            self.splitter.setSizes([480, 700])
        if persist:
            settings = self._settings()
            settings.setValue("details_orientation", orientation)
            settings.sync()

    def _schedule_auto_scan(self, delay_ms=None):
        if not self.automatic_scan_enabled:
            return
        if self._configuration_open:
            self._auto_scan_requested = True
            self.set_status("Automatic scan will run when Options closes.")
            return
        if delay_ms is None:
            delay_ms = 250
        self._auto_scan_timer.start(max(0, int(delay_ms)))

    def _apply_scan_mode(self):
        # Journal Inspector authority: manual mode exposes Scan / Scan Again;
        # automatic mode hides the top-level acquisition button.
        manual = not self.automatic_scan_enabled
        self.refresh_btn.setVisible(manual)
        self.refresh_btn.setEnabled(manual)
        if manual:
            self.refresh_btn.setText("Scan Again" if self._has_scanned else "Scan")

    def set_automatic_scan_enabled(self, enabled, *, persist=True):
        enabled = bool(enabled)
        changed = self.automatic_scan_enabled != enabled
        self.automatic_scan_enabled = enabled
        if persist:
            settings = self._settings()
            settings.setValue("automatic_scan_enabled", enabled)
            settings.sync()

        self._apply_scan_mode()

        if enabled:
            if changed:
                self._auto_scan_requested = True
            if self._configuration_open:
                self.set_status(
                    "Automatic scan enabled. It will run when Options closes."
                )
            else:
                self._auto_scan_requested = False
                self.set_status(
                    "Automatic scan enabled. Refreshing autostart configuration..."
                )
                self._schedule_auto_scan(delay_ms=0)
        else:
            self._auto_scan_timer.stop()
            self._auto_scan_requested = False
            if self._has_scanned:
                self.set_status(
                    "Automatic scan disabled. Use Scan Again to refresh the autostart inventory."
                )
            else:
                self.set_status(
                    "Automatic scan disabled. Use Scan to collect autostart configuration."
                )

    def metadata_details_for_export(self, record):
        original_info = self.info_text
        temp = QTextEdit()
        self.info_text = temp
        try:
            self._render_record_details(record)
            return temp.toPlainText()
        finally:
            self.info_text = original_info

    def get_export_records(self):
        return [{
            "entry": r.get("entry", ""),
            "category": r.get("category", ""),
            "scope": r.get("scope", ""),
            "state": r.get("state", ""),
            "trigger": r.get("trigger", ""),
            "source": r.get("source", ""),
        } for r in self.modules_data]


def create_applet(parent=None):
    return AutostartTab(parent=parent)

def run_standalone():
    import sys
    from PyQt6.QtGui import QIcon
    from PyQt6.QtWidgets import QApplication, QMainWindow
    from ._support import STANDALONE_STYLESHEET
    app = QApplication(sys.argv)
    app.setApplicationName(APPLET_NAME)
    app.setOrganizationName(APPLET_ORGANIZATION_NAME)
    icon_path = Path(__file__).resolve().parent / "icon.png"
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))
    app.setStyleSheet(STANDALONE_STYLESHEET)
    window = QMainWindow()
    if icon_path.is_file():
        window.setWindowIcon(QIcon(str(icon_path)))
    window.setWindowTitle(f"{APPLET_NAME} {APPLET_VERSION} — LinSpectacles Applet")
    window.resize(1200, 780)
    window.setCentralWidget(create_applet())
    window.show()
    return app.exec()
