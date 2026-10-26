import os
import sys
import json
import tempfile
from typing import Any, Dict, List, Optional

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
    "cache": {},
    "location_history": []
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
        default_copy = dict(DEFAULT_SETTINGS)
        # Seed initial location into history
        city = default_copy.get("city")
        if city:
            default_copy["location_history"] = [{
                "city": city,
                "country": default_copy.get("country", ""),
                "lat": default_copy.get("latitude", 0.0),
                "lon": default_copy.get("longitude", 0.0),
                "myquran_id": default_copy.get("myquran_id"),
                "display_name": f"{city}, {default_copy.get('country', '')}",
                "addresstype": "city",
                "candidates": [city]
            }]
        save_settings(default_copy)
        return default_copy

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            settings = json.load(f)
            # Ensure all default keys exist
            for key, val in DEFAULT_SETTINGS.items():
                if key not in settings:
                    if key == "location_history":
                        city = settings.get("city")
                        if city:
                            settings["location_history"] = [{
                                "city": city,
                                "country": settings.get("country", ""),
                                "lat": settings.get("latitude", 0.0),
                                "lon": settings.get("longitude", 0.0),
                                "myquran_id": settings.get("myquran_id"),
                                "display_name": f"{city}, {settings.get('country', '')}",
                                "addresstype": "city",
                                "candidates": [city]
                            }]
                        else:
                            settings["location_history"] = []
                    else:
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
            # Skip writing if file already exists with identical content
            if os.path.exists(autostart_file):
                try:
                    with open(autostart_file, "r", encoding="utf-8") as f:
                        if f.read() == content:
                            return
                except Exception:
                    pass

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


def get_location_history() -> List[Dict[str, Any]]:
    """Retrieves list of location history entries."""
    settings = load_settings()
    history = settings.get("location_history", [])
    if not isinstance(history, list):
        return []
    return list(history)


def add_location_history(location_data: Dict[str, Any], max_items: int = 10) -> None:
    """Adds a location entry to history, deduplicating and moving it to the top."""
    if not location_data or not isinstance(location_data, dict):
        return

    settings = load_settings()
    history = settings.get("location_history", [])
    if not isinstance(history, list):
        history = []

    city = location_data.get("city", "Unknown")
    country = location_data.get("country", "")
    try:
        lat = float(location_data.get("lat", 0.0))
        lon = float(location_data.get("lon", 0.0))
    except (ValueError, TypeError):
        lat, lon = 0.0, 0.0

    display_name = location_data.get("display_name", f"{city}, {country}")
    addresstype = location_data.get("addresstype", "city")
    candidates = location_data.get("candidates")
    if not candidates:
        candidates = [city]
    myquran_id = location_data.get("myquran_id")

    filtered_history = []
    for item in history:
        item_city = item.get("city", "")
        item_country = item.get("country", "")
        try:
            item_lat = float(item.get("lat", 0.0))
            item_lon = float(item.get("lon", 0.0))
        except (ValueError, TypeError):
            item_lat, item_lon = 0.0, 0.0

        is_same_display = display_name and item.get("display_name") == display_name
        is_same_coords = (
            item_city.lower() == city.lower()
            and item_country.lower() == country.lower()
            and abs(item_lat - lat) < 0.05
            and abs(item_lon - lon) < 0.05
        )

        if is_same_display or is_same_coords:
            if not myquran_id and item.get("myquran_id"):
                myquran_id = item.get("myquran_id")
            continue
        filtered_history.append(item)

    new_item = {
        "city": city,
        "country": country,
        "lat": lat,
        "lon": lon,
        "display_name": display_name,
        "addresstype": addresstype,
        "candidates": candidates,
    }
    if myquran_id:
        new_item["myquran_id"] = str(myquran_id)

    filtered_history.insert(0, new_item)
    settings["location_history"] = filtered_history[:max_items]
    save_settings(settings)


def remove_location_history(index: int) -> None:
    """Removes a location history entry by its index."""
    settings = load_settings()
    history = settings.get("location_history", [])
    if isinstance(history, list) and 0 <= index < len(history):
        history.pop(index)
        settings["location_history"] = history
        save_settings(settings)


def clear_location_history() -> None:
    """Clears all location history."""
    settings = load_settings()
    settings["location_history"] = []
    save_settings(settings)


def update_latest_history_myquran_id(myquran_id: Optional[str]) -> None:
    """Updates the myquran_id of the most recent history entry if applicable."""
    if not myquran_id:
        return
    settings = load_settings()
    history = settings.get("location_history", [])
    if history and isinstance(history, list):
        history[0]["myquran_id"] = str(myquran_id)
        settings["location_history"] = history
        save_settings(settings)
