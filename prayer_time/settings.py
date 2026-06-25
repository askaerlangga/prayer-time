import os
import json

CONFIG_DIR = os.path.expanduser("~/.config/prayer-time")
CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.json")

DEFAULT_SETTINGS = {
    "city": "Jakarta",
    "country": "Indonesia",
    "method": 20, # KEMENAG
    "latitude": -6.2088,
    "longitude": 106.8456,
    "myquran_id": "1301", # Jakarta v2 ID
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

def init_config():
    if not os.path.exists(CONFIG_DIR):
        try:
            # Create config directory with 0700 permissions (owner read/write/execute only)
            os.makedirs(CONFIG_DIR, mode=0o700)
            # Explicitly enforce in case umask relaxed it
            os.chmod(CONFIG_DIR, 0o700)
        except Exception as e:
            print(f"Error creating config directory: {e}")

def load_settings():
    init_config()
    if not os.path.exists(CONFIG_FILE):
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS
    
    try:
        with open(CONFIG_FILE, "r") as f:
            settings = json.load(f)
            # Ensure all default keys exist
            for key, val in DEFAULT_SETTINGS.items():
                if key not in settings:
                    settings[key] = val
            return settings
    except Exception as e:
        print(f"Error loading settings: {e}")
        return DEFAULT_SETTINGS

def save_settings(settings):
    init_config()
    try:
        # Secure file creation with 0600 permissions (owner read/write only)
        # to avoid race conditions during file creation.
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        fd = os.open(CONFIG_FILE, flags, 0o600)
        with open(fd, "w") as f:
            json.dump(settings, f, indent=4)
    except Exception as e:
        print(f"Error saving settings: {e}")

def get_setting(key, default=None):
    settings = load_settings()
    return settings.get(key, default)

def update_autostart(enable_status):
    autostart_dir = os.path.expanduser("~/.config/autostart")
    autostart_file = os.path.join(autostart_dir, "com.github.aska.PrayerTime.desktop")
    old_autostart_file = os.path.join(autostart_dir, "prayer-time.desktop")

    # Clean up old filename if it exists
    if os.path.exists(old_autostart_file):
        try:
            os.remove(old_autostart_file)
            print("Old autostart file removed successfully")
        except Exception as e:
            print(f"Error removing old autostart file: {e}")

    if enable_status:
        try:
            # Ensure the directory exists
            os.makedirs(autostart_dir, exist_ok=True)
            
            script_dir = os.path.dirname(os.path.abspath(__file__))
            if script_dir.startswith("/usr/"):
                exec_cmd = "prayer-time --background"
            else:
                main_path = os.path.join(os.path.dirname(script_dir), "main.py")
                exec_cmd = f"python3 {main_path} --background"
                
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
            with open(autostart_file, "w") as f:
                f.write(content)
            os.chmod(autostart_file, 0o644)
            print("Autostart entry created successfully")
        except Exception as e:
            print(f"Error writing autostart file: {e}")
    else:
        if os.path.exists(autostart_file):
            try:
                os.remove(autostart_file)
                print("Autostart entry removed successfully")
            except Exception as e:
                print(f"Error removing autostart file: {e}")

def set_setting(key, value):
    settings = load_settings()
    settings[key] = value
    save_settings(settings)
    if key == "autostart":
        update_autostart(value)

def get_cache_key(city, month, year):
    # Normalize city name
    normalized_city = "".join(c.lower() for c in city if c.isalnum())
    return f"{normalized_city}_{month:02d}_{year}"

def get_cached_timings(city, month, year):
    settings = load_settings()
    cache = settings.get("cache", {})
    key = get_cache_key(city, month, year)
    return cache.get(key)

def set_cached_timings(city, month, year, data):
    settings = load_settings()
    if "cache" not in settings:
        settings["cache"] = {}
    
    # Simple cache size limit (keep last 5 entries to prevent unbounded growth)
    cache = settings["cache"]
    if len(cache) > 5:
        # Remove the oldest key
        oldest_key = list(cache.keys())[0]
        cache.pop(oldest_key, None)
        
    key = get_cache_key(city, month, year)
    cache[key] = data
    save_settings(settings)
