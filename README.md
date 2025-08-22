# 404-weather
**404-Weather** is a dark-themed desktop weather radar and alerts GUI.   It combines the RainViewer live radar/satellite viewer with live National Weather Service (USA) alerts, and quick access to Environment Canada (ECCC) alerts.


<img width="1024" height="1024" alt="ChatGPT Image Aug 22, 2025, 05_12_21 PM" src="https://github.com/user-attachments/assets/041edf14-476d-4ede-9713-6ba5050eb8aa" />




## ✨ Features
- 🌎 **Interactive Map**  
  - Live RainViewer radar or satellite layers  
  - Adjustable center latitude/longitude, zoom, opacity, color scheme, labels, snow overlay  
  - Instant update button and "open in browser" option  

- 🚨 **Live Alerts (USA, NWS)**  
  - Pulls from [api.weather.gov](https://api.weather.gov)  
  - Modes: **point** (lat/lon), **state** (2-letter), **zone** (county/UGC)  
  - Auto-refresh timer (30s–15m)  
  - Alerts tab with severity, urgency, certainty, expiry, area/office  
  - Double-click any alert to open its official NWS page  

- 🍁 **Canada Alerts**  
  - Quick button opens Environment Canada (ECCC) warning page in your browser  

- 🎨 **Dark Hacker Theme**  
  - Consistent dark palette with blue highlights  
  - GUI remembers your last settings (`settings.json`)

---

## 🛠 Install & Run

### Requirements
- Python 3.9+  
- [PySide6](https://pypi.org/project/PySide6/) with QtWebEngine  
- `requests`

### Setup
```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip wheel
pip install PySide6 PySide6-Addons PySide6-Essentials requests

Run
python map.py

<img width="1920" height="1080" alt="Screenshot_2025-08-21_23_15_32" src="https://github.com/user-attachments/assets/0decd907-087d-4e7f-8ba6-a509e280c439" />

<img width="1920" height="1080" alt="Screenshot_2025-08-22_17_01_07" src="https://github.com/user-attachments/assets/765a6261-1991-44d2-a049-3f9e5f923959" />

⚙️ Settings

Saved in settings.json in the working directory.

Stores map center, zoom, layer, color scheme, opacity, toggles, and alert preferences.

📚 References

RainViewer maps: rainviewer.com/map




