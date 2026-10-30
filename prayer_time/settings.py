import os
import sys
import json
import re
import copy
import tempfile
from typing import Any, Dict, List, Optional, Tuple

CONFIG_DIR = os.path.expanduser("~/.config/prayer-time")
CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.json")

# In-memory settings cache to avoid disk I/O on every tick
_settings_cache: Optional[Dict[str, Any]] = None
_settings_mtime: Optional[float] = None

DEFAULT_SETTINGS: Dict[str, Any] = {
    "city": "Jakarta",
    "country": "Indonesia",
    "method": 20,  # KEMENAG
    "latitude": -6.2088,
    "longitude": 106.8456,
    "myquran_id": "1301",  # Jakarta v2 ID
    "autostart": False,
    "enable_audio": True,
    "auto_location": False,
    "language": "id",
    "fajr_iqamah": 15,
    "dhuhr_iqamah": 10,
    "asr_iqamah": 10,
    "maghrib_iqamah": 10,
    "isha_iqamah": 10,
    "cache": {},
    "location_history": []
}


def _build_initial_history(cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Constructs the seed location history entry from configuration values."""
    city = cfg.get("city")
    if not city:
        return []
    country = cfg.get("country", "")
    return [{
        "city": city,
        "country": country,
        "lat": cfg.get("latitude", 0.0),
        "lon": cfg.get("longitude", 0.0),
        "myquran_id": cfg.get("myquran_id"),
        "display_name": f"{city}, {country}" if country else city,
        "addresstype": "city",
        "candidates": [city]
    }]


def init_config() -> None:
    """Ensures the configuration directory exists with restricted permissions."""
    if not os.path.exists(CONFIG_DIR):
        try:
            os.makedirs(CONFIG_DIR, mode=0o700, exist_ok=True)
            os.chmod(CONFIG_DIR, 0o700)
        except Exception as e:
            print(f"[PrayerTime] Error creating config directory: {e}")


def load_settings() -> Dict[str, Any]:
    """Loads application settings with in-memory caching and deep-copy protection."""
    global _settings_cache, _settings_mtime
    init_config()

    if not os.path.exists(CONFIG_FILE):
        default_copy = copy.deepcopy(DEFAULT_SETTINGS)
        default_copy["location_history"] = _build_initial_history(default_copy)
        save_settings(default_copy)
        return copy.deepcopy(default_copy)

    try:
        current_mtime = os.stat(CONFIG_FILE).st_mtime
        if _settings_cache is not None and _settings_mtime == current_mtime:
            return copy.deepcopy(_settings_cache)

        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            settings = json.load(f)
            # Ensure all default keys exist
            for key, val in DEFAULT_SETTINGS.items():
                if key not in settings:
                    if key == "location_history":
                        settings["location_history"] = _build_initial_history(settings)
                    else:
                        settings[key] = copy.deepcopy(val)

            _settings_cache = copy.deepcopy(settings)
            _settings_mtime = current_mtime
            return copy.deepcopy(settings)
    except Exception as e:
        print(f"[PrayerTime] Error loading settings: {e}")
        if _settings_cache is not None:
            return copy.deepcopy(_settings_cache)
        return copy.deepcopy(DEFAULT_SETTINGS)


def save_settings(settings: Dict[str, Any]) -> None:
    """Atomically saves settings to JSON to prevent corruption on sudden exit."""
    global _settings_cache, _settings_mtime
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
        _settings_cache = copy.deepcopy(settings)
        try:
            _settings_mtime = os.stat(CONFIG_FILE).st_mtime
        except OSError:
            _settings_mtime = None
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
    """Updates a single setting value and saves immediately."""
    settings = load_settings()
    settings[key] = value
    save_settings(settings)
    if key == "autostart":
        update_autostart(bool(value))


def update_settings(updates: Dict[str, Any]) -> None:
    """Updates multiple settings simultaneously with a single disk write."""
    if not updates:
        return
    settings = load_settings()
    settings.update(updates)
    save_settings(settings)
    if "autostart" in updates:
        update_autostart(bool(updates["autostart"]))


def invalidate_cached_timings(city: str, month: int, year: int) -> None:
    """Invalidates the cached timings for a specific city, month, and year."""
    key = get_cache_key(city, month, year)
    settings = load_settings()
    if "cache" in settings and isinstance(settings["cache"], dict) and key in settings["cache"]:
        settings["cache"].pop(key, None)
        save_settings(settings)


def _upsert_history_entry(
    history: List[Dict[str, Any]],
    location_data: Dict[str, Any],
    myquran_id_override: Any = ...,
    max_items: int = 10
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Deduplicates and inserts location_data at index 0 of history.
    Returns (updated_history, resolved_myquran_id).
    """
    if not isinstance(history, list):
        history = []

    city = location_data.get("city", "Unknown")
    country = location_data.get("country", "")
    try:
        lat = float(location_data.get("lat", 0.0))
        lon = float(location_data.get("lon", 0.0))
    except (ValueError, TypeError):
        lat, lon = 0.0, 0.0

    display_name = location_data.get("display_name", f"{city}, {country}" if country else city)
    addresstype = location_data.get("addresstype", "city")
    candidates = location_data.get("candidates") or [city]

    resolved_myquran_id = (
        myquran_id_override if myquran_id_override is not ... else location_data.get("myquran_id")
    )

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
            if not resolved_myquran_id and item.get("myquran_id"):
                resolved_myquran_id = item.get("myquran_id")
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
    if resolved_myquran_id:
        new_item["myquran_id"] = str(resolved_myquran_id)

    filtered_history.insert(0, new_item)
    return filtered_history[:max_items], (str(resolved_myquran_id) if resolved_myquran_id else None)


def apply_location_selection(
    location_data: Dict[str, Any],
    auto_location: Optional[bool] = None,
    myquran_id: Any = ...,
    max_history_items: int = 10
) -> Optional[str]:
    """
    Applies location selection (history deduplication, active coordinates,
    auto_location mode, cache flush, and optional myquran_id) in a single atomic disk write.
    Returns the resolved myquran_id (if any).
    """
    if not location_data or not isinstance(location_data, dict):
        return None

    settings = load_settings()
    updated_history, resolved_myquran_id = _upsert_history_entry(
        settings.get("location_history", []),
        location_data,
        myquran_id_override=myquran_id,
        max_items=max_history_items
    )
    settings["location_history"] = updated_history

    first = updated_history[0]
    settings["city"] = first["city"]
    settings["country"] = first["country"]
    settings["latitude"] = first["lat"]
    settings["longitude"] = first["lon"]
    settings["cache"] = {}

    if auto_location is not None:
        settings["auto_location"] = bool(auto_location)

    if first["country"] != "Indonesia":
        settings["myquran_id"] = None
        resolved_myquran_id = None
    else:
        settings["myquran_id"] = resolved_myquran_id

    save_settings(settings)
    return resolved_myquran_id


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
    """Generates a standardized cache key for a city and month, compatible with extension."""
    normalized_city = re.sub(r'[^a-z0-9]', '', (city or "jakarta").lower())
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
    key = get_cache_key(city, month, year)

    # Evict oldest entry if at capacity and adding a new key
    if key not in cache and len(cache) >= 5:
        oldest_key = next(iter(cache))
        cache.pop(oldest_key, None)

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
    updated_history, _ = _upsert_history_entry(
        settings.get("location_history", []),
        location_data,
        max_items=max_items
    )
    settings["location_history"] = updated_history
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
    """Updates the active myquran_id and the most recent history entry in a single write."""
    settings = load_settings()
    settings["myquran_id"] = str(myquran_id) if myquran_id else None
    history = settings.get("location_history", [])
    if myquran_id and history and isinstance(history, list):
        history[0]["myquran_id"] = str(myquran_id)
        settings["location_history"] = history
    save_settings(settings)
