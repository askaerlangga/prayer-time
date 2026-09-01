import os
import sys
import json
import tempfile
from typing import Any, Dict, Optional

CONFIG_DIR = os.path.expanduser("~/.config/prayer-time")
CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.json")

DEFAULT_SETTINGS: Dict[str, Any] = {
    "city": "Jakarta",
    "country": "Indonesia",
    "method": 20,  # KEMENAG
    "latitude": -6.2088,
    "longitude": 106.8456,
    "myquran_id": "1301",  # Jakarta v2 ID
    "autostart": False,
    "enable_audio": True,
    "language": "id",
    "fajr_iqamah": 15,
    "dhuhr_iqamah": 10,
    "asr_iqamah": 10,
    "maghrib_iqamah": 10,
    "isha_iqamah": 10,
    "cache": {}
}


def init_config() -> None:
    """Ensures the configuration directory exists with restricted permissions."""
    if not os.path.exists(CONFIG_DIR):
        try:
            os.makedirs(CONFIG_DIR, mode=0o700, exist_ok=True)
            os.chmod(CONFIG_DIR, 0o700)
        except Exception as e:
            print(f"[PrayerTime] Error creating config directory: {e}")


def load_settings() -> Dict[str, Any]:
    """Loads application settings from JSON, filling in any missing default keys."""
    init_config()
    if not os.path.exists(CONFIG_FILE):
        save_settings(DEFAULT_SETTINGS)
        return dict(DEFAULT_SETTINGS)

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            settings = json.load(f)
            # Ensure all default keys exist
            for key, val in DEFAULT_SETTINGS.items():
                if key not in settings:
                    settings[key] = val
            return settings
    except Exception as e:
        print(f"[PrayerTime] Error loading settings: {e}")
        return dict(DEFAULT_SETTINGS)


def save_settings(settings: Dict[str, Any]) -> None:
    """Atomically saves settings to JSON to prevent corruption on sudden exit."""
    init_config()
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(dir=CONFIG_DIR, prefix="settings_", suffix=".tmp")
        os.chmod(tmp_path, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, CONFIG_FILE)
    except Exception as e:
        print(f"[PrayerTime] Error saving settings: {e}")
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def get_setting(key: str, default: Any = None) -> Any:
    """Retrieves a specific setting value."""
    settings = load_settings()
    return settings.get(key, default)


def set_setting(key: str, value: Any) -> None:
    """Updates a setting value and saves immediately."""
    settings = load_settings()
    settings[key] = value
    save_settings(settings)
    if key == "autostart":
        update_autostart(bool(value))


def update_autostart(enable_status: bool) -> None:
    """Creates or removes the XDG autostart desktop entry."""
    autostart_dir = os.path.expanduser("~/.config/autostart")
    autostart_file = os.path.join(autostart_dir, "com.github.aska.PrayerTime.desktop")
    old_autostart_file = os.path.join(autostart_dir, "prayer-time.desktop")

    # Clean up legacy filename if it exists
    if os.path.exists(old_autostart_file):
        try:
            os.remove(old_autostart_file)
        except Exception:
            pass

    if enable_status:
        try:
            os.makedirs(autostart_dir, exist_ok=True)
            script_dir = os.path.dirname(os.path.abspath(__file__))
            if script_dir.startswith("/usr/"):
                exec_cmd = "prayer-time --background"
            else:
                main_path = os.path.join(os.path.dirname(script_dir), "main.py")
                exec_cmd = f'"{sys.executable}" "{main_path}" --background'

            content = f"""[Desktop Entry]
Type=Application
Exec={exec_cmd}
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Name=Prayer Times
Name[id]=Waktu Salat
Comment=Desktop prayer times reminder
Comment[id]=Pengingat waktu salat desktop
Icon=com.github.aska.PrayerTime
Terminal=false
"""
            with open(autostart_file, "w", encoding="utf-8") as f:
                f.write(content)
            os.chmod(autostart_file, 0o644)
        except Exception as e:
            print(f"[PrayerTime] Error writing autostart file: {e}")
    else:
        if os.path.exists(autostart_file):
            try:
                os.remove(autostart_file)
            except Exception as e:
                print(f"[PrayerTime] Error removing autostart file: {e}")


def get_cache_key(city: str, month: int, year: int) -> str:
    """Generates a standardized cache key for a city and month."""
    normalized_city = "".join(c.lower() for c in (city or "jakarta") if c.isalnum())
    return f"{normalized_city}_{month:02d}_{year}"


def get_cached_timings(city: str, month: int, year: int) -> Optional[Any]:
    """Retrieves cached monthly prayer timings if present."""
    settings = load_settings()
    cache = settings.get("cache", {})
    key = get_cache_key(city, month, year)
    return cache.get(key)


def set_cached_timings(city: str, month: int, year: int, data: Any) -> None:
    """Stores monthly prayer timings in settings cache, limiting to the last 5 entries."""
    settings = load_settings()
    if "cache" not in settings or not isinstance(settings["cache"], dict):
        settings["cache"] = {}

    cache = settings["cache"]
    if len(cache) > 5:
        oldest_key = list(cache.keys())[0]
        cache.pop(oldest_key, None)

    key = get_cache_key(city, month, year)
    cache[key] = data
    save_settings(settings)
