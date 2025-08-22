#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RainViewer Live Radar — Desktop GUI + Live Alerts

• Python + PySide6 + QtWebEngine
• Live NWS (USA) severe weather alerts by point (lat,lon) with auto‑refresh
• Dark-themed GUI with controls for lat/lon/zoom, layer, color scheme, opacity, legend/labels/snow, timestep
• Update button, Copy-Embed button, Open-in-browser button
• Persists last-used settings to settings.json in the same folder

Install & run:
    pip install --upgrade PySide6 PySide6-Addons PySide6-Essentials requests
    python rainviewer_gui.py

Notes:
  - Alerts source (USA): National Weather Service API (api.weather.gov). We query
    /alerts/active?point=LAT,LON. You can optionally pull by state/zone.
  - For Canada: click the “Open ECCC Alerts (Canada)” button to view official
    federal alerts for your area in the browser. Full in‑app parsing for Canada
    can be added (ECCC CAP feeds) if you want.

Docs:
  - NWS API overview: https://www.weather.gov/documentation/services-web-api
  - NWS alerts by point (see Geolocation guide): https://www.weather.gov/media/documentation/docs/NWS_Geolocation.pdf
"""
from __future__ import annotations
import json
import os
import sys
import webbrowser
from datetime import datetime, timezone

import requests

from PySide6.QtCore import Qt, QUrl, QSize, QTimer
from PySide6.QtGui import QPalette, QColor, QGuiApplication
from PySide6.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout,
    QLabel, QSpinBox, QDoubleSpinBox, QComboBox, QSlider, QCheckBox,
    QPushButton, QGroupBox, QMessageBox, QSplitter, QTabWidget, QTreeWidget,
    QTreeWidgetItem, QHeaderView
)
from PySide6.QtWebEngineWidgets import QWebEngineView

APP_TITLE = "RainViewer Live Weather Map"
SETTINGS_FILE = "settings.json"

DEFAULTS = {
    "lat": 49.7847,
    "lon": -94.9921,
    "zoom": 5,
    "layer": "radar",  # or "satellite"
    "c": 3,             # color scheme 0–9
    "o": 83,            # opacity 0–100
    "lm": True,         # legend
    "sm": True,         # map labels
    "sn": True,         # show snow
    "ts": 2,            # timestep
    # Alerts
    "alerts_auto": True,
    "alerts_interval_sec": 120,
    "alerts_mode": "point",   # point | state | zone
    "alerts_area": "FL",      # used when mode=state (2-letter state/territory)
    "alerts_user_agent": "dc404-weathermap (contact: you@example.com)"
}

NWS_API = "https://api.weather.gov"
ECCC_ALERTS_MAP = "https://weather.gc.ca/warnings/index_e.html"

class RainViewerGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(QSize(1200, 700))

        self.settings = self.load_settings()
        self.alert_timer = QTimer(self)
        self.alert_timer.timeout.connect(self.fetch_alerts)

        self.build_ui()
        self.apply_dark_theme()
        self.update_map()
        self.configure_alert_timer()
        self.fetch_alerts()  # initial

    # --- UI ---
    def build_ui(self):
        root = QHBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter)

        # Left: Controls panel
        controls = QWidget(); controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(12, 12, 12, 12)
        controls_layout.setSpacing(10)

        form = QGridLayout(); form.setHorizontalSpacing(10); form.setVerticalSpacing(8)

        self.lat = QDoubleSpinBox(); self.lat.setDecimals(4); self.lat.setRange(-90.0, 90.0); self.lat.setValue(self.settings["lat"]) 
        self.lon = QDoubleSpinBox(); self.lon.setDecimals(4); self.lon.setRange(-180.0, 180.0); self.lon.setValue(self.settings["lon"]) 
        self.zoom = QSpinBox(); self.zoom.setRange(1, 12); self.zoom.setValue(self.settings["zoom"]) 

        self.layer = QComboBox(); self.layer.addItems(["radar", "satellite"]) 
        self.layer.setCurrentText(self.settings["layer"]) 

        self.c = QComboBox(); self.c.addItems([str(i) for i in range(0,10)]) 
        self.c.setCurrentText(str(self.settings["c"]))

        self.o = QSlider(Qt.Horizontal); self.o.setRange(0, 100); self.o.setValue(self.settings["o"]) 

        self.lm = QCheckBox("Legend (lm)"); self.lm.setChecked(self.settings["lm"]) 
        self.sm = QCheckBox("Map labels (sm)"); self.sm.setChecked(self.settings["sm"]) 
        self.sn = QCheckBox("Show snow (sn)"); self.sn.setChecked(self.settings["sn"]) 

        self.ts = QComboBox(); self.ts.addItems(["1","2","3","4"]) 
        self.ts.setCurrentText(str(self.settings["ts"]))

        row = 0
        form.addWidget(QLabel("Latitude"), row, 0); form.addWidget(self.lat, row, 1); row += 1
        form.addWidget(QLabel("Longitude"), row, 0); form.addWidget(self.lon, row, 1); row += 1
        form.addWidget(QLabel("Zoom (1–12)"), row, 0); form.addWidget(self.zoom, row, 1); row += 1
        form.addWidget(QLabel("Layer"), row, 0); form.addWidget(self.layer, row, 1); row += 1
        form.addWidget(QLabel("Color scheme (c)"), row, 0); form.addWidget(self.c, row, 1); row += 1
        form.addWidget(QLabel("Opacity (o)"), row, 0); form.addWidget(self.o, row, 1); row += 1
        form.addWidget(QLabel("Time step (ts)"), row, 0); form.addWidget(self.ts, row, 1); row += 1

        toggles = QGroupBox("Toggles"); tlay = QVBoxLayout(toggles)
        tlay.addWidget(self.lm); tlay.addWidget(self.sm); tlay.addWidget(self.sn)

        btn_update = QPushButton("Update Map")
        btn_copy = QPushButton("Copy Embed Code")
        btn_open = QPushButton("Open Map in Browser")
        btn_save = QPushButton("Save Settings")
        btn_reset = QPushButton("Reset Defaults")

        btn_update.clicked.connect(self.update_map)
        btn_copy.clicked.connect(self.copy_embed)
        btn_open.clicked.connect(self.open_in_browser)
        btn_save.clicked.connect(self.save_settings)
        btn_reset.clicked.connect(self.reset_defaults)

        controls_layout.addLayout(form)
        controls_layout.addWidget(toggles)

        row2 = QGridLayout()
        row2.addWidget(btn_update, 0, 0)
        row2.addWidget(btn_copy, 0, 1)
        row2.addWidget(btn_open, 1, 0)
        row2.addWidget(btn_save, 1, 1)
        controls_layout.addLayout(row2)

        # Alerts Controls
        alerts_box = QGroupBox("Live Alerts (USA: NWS)")
        al = QGridLayout(alerts_box)
        self.alerts_mode = QComboBox(); self.alerts_mode.addItems(["point", "state", "zone"]) 
        self.alerts_mode.setCurrentText(self.settings.get("alerts_mode","point"))
        self.alerts_area = QComboBox();  # for state list quick pick
        self.alerts_area.addItems([
            "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY","DC","PR","GU","AS","VI","MP"
        ])
        self.alerts_area.setCurrentText(self.settings.get("alerts_area","FL"))
        self.alerts_auto = QCheckBox("Auto‑refresh"); self.alerts_auto.setChecked(self.settings.get("alerts_auto", True))
        self.alerts_interval = QSpinBox(); self.alerts_interval.setRange(30, 900); self.alerts_interval.setSuffix(" s"); self.alerts_interval.setValue(self.settings.get("alerts_interval_sec", 120))
        self.ua_input = QComboBox(); self.ua_input.setEditable(True); self.ua_input.addItem(self.settings.get("alerts_user_agent", DEFAULTS["alerts_user_agent"]))

        btn_fetch = QPushButton("Refresh Now")
        btn_eccc = QPushButton("Open ECCC Alerts (Canada)")
        btn_fetch.clicked.connect(self.fetch_alerts)
        btn_eccc.clicked.connect(lambda: webbrowser.open(ECCC_ALERTS_MAP))

        r=0
        al.addWidget(QLabel("Mode"), r, 0); al.addWidget(self.alerts_mode, r, 1); r+=1
        al.addWidget(QLabel("State (when mode=state)"), r, 0); al.addWidget(self.alerts_area, r, 1); r+=1
        al.addWidget(QLabel("Interval"), r, 0); al.addWidget(self.alerts_interval, r, 1); r+=1
        al.addWidget(self.alerts_auto, r, 0, 1, 2); r+=1
        al.addWidget(QLabel("User‑Agent (required by NWS)"), r, 0, 1, 2); r+=1
        al.addWidget(self.ua_input, r, 0, 1, 2); r+=1
        al.addWidget(btn_fetch, r, 0); al.addWidget(btn_eccc, r, 1); r+=1

        controls_layout.addWidget(alerts_box)

        info = QLabel("Powered by RainViewer (map) + NWS (alerts). Adjust settings and click ‘Update Map’. Double‑click an alert to open details.")
        info.setWordWrap(True)
        controls_layout.addWidget(info)
        controls_layout.addStretch(1)

        # Right: Tabs (Map + Alerts)
        right = QTabWidget()
        # Map tab
        map_tab = QWidget(); map_layout = QVBoxLayout(map_tab)
        self.web = QWebEngineView()
        map_layout.addWidget(self.web)
        right.addTab(map_tab, "Map")

        # Alerts tab
        alerts_tab = QWidget(); a_layout = QVBoxLayout(alerts_tab)
        self.alerts_view = QTreeWidget(); self.alerts_view.setColumnCount(6)
        self.alerts_view.setHeaderLabels(["Event", "Severity", "Urgency", "Certainty", "Ends", "Area/Office"])
        self.alerts_view.header().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.alerts_view.header().setStretchLastSection(True)
        self.alerts_view.itemActivated.connect(self.open_alert_url)
        a_layout.addWidget(self.alerts_view)
        self.alerts_status = QLabel("—")
        a_layout.addWidget(self.alerts_status)
        right.addTab(alerts_tab, "Alerts")

        splitter.addWidget(controls)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        # Live update hooks
        self.lat.valueChanged.connect(self.live_update)
        self.lon.valueChanged.connect(self.live_update)
        self.zoom.valueChanged.connect(self.live_update)
        self.layer.currentTextChanged.connect(self.live_update)
        self.c.currentTextChanged.connect(self.live_update)
        self.o.valueChanged.connect(self.live_update)
        self.lm.toggled.connect(self.live_update)
        self.sm.toggled.connect(self.live_update)
        self.sn.toggled.connect(self.live_update)
        self.ts.currentTextChanged.connect(self.live_update)

        # Alerts behavior hooks
        self.alerts_auto.toggled.connect(self.configure_alert_timer)
        self.alerts_interval.valueChanged.connect(self.configure_alert_timer)

    def apply_dark_theme(self):
        pal = QPalette()
        pal.setColor(QPalette.Window, QColor(11, 16, 32))
        pal.setColor(QPalette.WindowText, QColor(233, 238, 251))
        pal.setColor(QPalette.Base, QColor(18, 24, 52))
        pal.setColor(QPalette.AlternateBase, QColor(16, 22, 48))
        pal.setColor(QPalette.ToolTipBase, QColor(233, 238, 251))
        pal.setColor(QPalette.ToolTipText, QColor(18, 24, 52))
        pal.setColor(QPalette.Text, QColor(233, 238, 251))
        pal.setColor(QPalette.Button, QColor(17, 25, 52))
        pal.setColor(QPalette.ButtonText, QColor(233, 238, 251))
        pal.setColor(QPalette.BrightText, QColor(255, 0, 0))
        pal.setColor(QPalette.Highlight, QColor(110, 168, 254))
        pal.setColor(QPalette.HighlightedText, QColor(15, 18, 28))
        self.setPalette(pal)

    # --- Map URL / Embed ---
    def build_src(self) -> str:
        lat = f"{self.lat.value():.4f}"
        lon = f"{self.lon.value():.4f}"
        zoom = str(max(1, min(12, int(self.zoom.value()))))
        params = {
            "loc": f"{lat},{lon},{zoom}",
            "oCS": "1",
            "c": self.c.currentText(),
            "o": str(self.o.value()),
            "lm": "1" if self.lm.isChecked() else "0",
            "layer": self.layer.currentText(),
            "sm": "1" if self.sm.isChecked() else "0",
            "sn": "1" if self.sn.isChecked() else "0",
            "ts": self.ts.currentText(),
        }
        q = "&".join(f"{k}={v}" for k, v in params.items())
        return f"https://www.rainviewer.com/map.html?{q}"

    def update_map(self):
        self.web.setUrl(QUrl(self.build_src()))

    def live_update(self):
        self.update_map()
        # If we're on point mode, also refresh alerts to match new coords
        if self.alerts_mode.currentText() == "point":
            self.fetch_alerts()

    def build_embed_html(self) -> str:
        src = self.build_src()
        return (
            f'<iframe src="{src}" width="100%" frameborder="0" '
            f'style="border:0;height:50vh;" allowfullscreen></iframe>'
        )

    def copy_embed(self):
        html = self.build_embed_html()
        cb = QGuiApplication.clipboard(); cb.setText(html)
        QMessageBox.information(self, APP_TITLE, "Embed HTML copied to clipboard.")

    def open_in_browser(self):
        webbrowser.open(self.build_src())

    # --- Alerts ---
    def configure_alert_timer(self):
        if self.alerts_auto.isChecked():
            self.alert_timer.start(self.alerts_interval.value() * 1000)
        else:
            self.alert_timer.stop()

    def nws_headers(self):
        ua = self.ua_input.currentText().strip() or DEFAULTS["alerts_user_agent"]
        return {
            "User-Agent": ua,
            "Accept": "application/geo+json"
        }

    def fetch_alerts(self):
        mode = self.alerts_mode.currentText()
        try:
            if mode == "point":
                lat = f"{self.lat.value():.4f}"; lon = f"{self.lon.value():.4f}"
                url = f"{NWS_API}/alerts/active?point={lat},{lon}"
            elif mode == "state":
                area = self.alerts_area.currentText()
                url = f"{NWS_API}/alerts/active?area={area}"
            elif mode == "zone":
                # Expect a UGC like FLZ063/ FLC033 etc. (could be added as another input)
                # For now, map current point to county zone via /points
                lat = f"{self.lat.value():.4f}"; lon = f"{self.lon.value():.4f}"
                p = requests.get(f"{NWS_API}/points/{lat},{lon}", headers=self.nws_headers(), timeout=10)
                p.raise_for_status()
                j = p.json()
                county = j.get("properties", {}).get("county")
                if county:
                    url = f"{NWS_API}/alerts/active?zone={county.split('/')[-1]}"
                else:
                    url = f"{NWS_API}/alerts/active?point={lat},{lon}"
            else:
                url = f"{NWS_API}/alerts/active"

            r = requests.get(url, headers=self.nws_headers(), timeout=15)
            r.raise_for_status()
            data = r.json()
            self.populate_alerts(data)
            count = len(data.get("features", []))
            self.alerts_status.setText(f"NWS alerts: {count} (source: {url})")
        except Exception as e:
            self.alerts_status.setText(f"Alerts error: {e}")

    def populate_alerts(self, data: dict):
        self.alerts_view.clear()
        feats = data.get("features", []) or []
        for f in feats:
            props = f.get("properties", {})
            event = props.get("event", "—")
            sev = props.get("severity", "—")
            urg = props.get("urgency", "—")
            cert = props.get("certainty", "—")
            ends = props.get("ends") or props.get("expires") or props.get("effective")
            ends_text = self.fmt_time(ends)
            area = props.get("areaDesc", "")
            office = props.get("senderName", "")
            col5 = f"{ends_text}" if ends_text else "—"
            col6 = office if office else area
            item = QTreeWidgetItem([event, sev, urg, cert, col5, col6])
            # store URL to open
            url = props.get("id") or f.get("id") or props.get("@id")
            if url:
                item.setData(0, Qt.UserRole, url)
            self.alerts_view.addTopLevelItem(item)

        self.alerts_view.header().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.alerts_view.header().setStretchLastSection(True)

    def fmt_time(self, t: str | None) -> str:
        if not t:
            return ""
        try:
            # NWS uses RFC3339/ISO 8601
            dt = datetime.fromisoformat(t.replace("Z", "+00:00"))
            return dt.astimezone().strftime("%b %d %Y, %I:%M %p")
        except Exception:
            return t

    def open_alert_url(self, item: QTreeWidgetItem):
        url = item.data(0, Qt.UserRole)
        if url:
            webbrowser.open(url)

    # --- settings ---
    def current_settings(self) -> dict:
        return {
            "lat": float(self.lat.value()),
            "lon": float(self.lon.value()),
            "zoom": int(self.zoom.value()),
            "layer": self.layer.currentText(),
            "c": int(self.c.currentText()),
            "o": int(self.o.value()),
            "lm": bool(self.lm.isChecked()),
            "sm": bool(self.sm.isChecked()),
            "sn": bool(self.sn.isChecked()),
            "ts": int(self.ts.currentText()),
            # Alerts
            "alerts_auto": bool(self.alerts_auto.isChecked()),
            "alerts_interval_sec": int(self.alerts_interval.value()),
            "alerts_mode": self.alerts_mode.currentText(),
            "alerts_area": self.alerts_area.currentText(),
            "alerts_user_agent": self.ua_input.currentText().strip() or DEFAULTS["alerts_user_agent"],
        }

    def save_settings(self):
        data = self.current_settings()
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            QMessageBox.information(self, APP_TITLE, f"Settings saved to {SETTINGS_FILE}.")
        except Exception as e:
            QMessageBox.critical(self, APP_TITLE, f"Failed to save settings: {e}")

    def reset_defaults(self):
        for k,v in DEFAULTS.items():
            if k in ("alerts_user_agent",):
                continue
        self.lat.setValue(DEFAULTS["lat"]) 
        self.lon.setValue(DEFAULTS["lon"]) 
        self.zoom.setValue(DEFAULTS["zoom"]) 
        self.layer.setCurrentText(DEFAULTS["layer"]) 
        self.c.setCurrentText(str(DEFAULTS["c"]))
        self.o.setValue(DEFAULTS["o"]) 
        self.lm.setChecked(DEFAULTS["lm"]) 
        self.sm.setChecked(DEFAULTS["sm"]) 
        self.sn.setChecked(DEFAULTS["sn"]) 
        self.ts.setCurrentText(str(DEFAULTS["ts"]))
        # alerts
        self.alerts_auto.setChecked(DEFAULTS["alerts_auto"])
        self.alerts_interval.setValue(DEFAULTS["alerts_interval_sec"])
        self.alerts_mode.setCurrentText(DEFAULTS["alerts_mode"]) 
        self.alerts_area.setCurrentText(DEFAULTS["alerts_area"]) 
        if self.ua_input.count() == 0:
            self.ua_input.addItem(DEFAULTS["alerts_user_agent"]) 
        self.ua_input.setCurrentText(DEFAULTS["alerts_user_agent"]) 
        self.update_map(); self.fetch_alerts()

    def load_settings(self) -> dict:
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                merged = DEFAULTS.copy(); merged.update(data)
                return merged
            except Exception:
                pass
        return DEFAULTS.copy()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    w = RainViewerGUI(); w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
