import os
import sys
import json
import datetime
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gio
gi.require_version('AyatanaAppIndicator3', '0.1')
from gi.repository import AyatanaAppIndicator3 as appindicator

# Import internationalization helper
import i18n

# Paths
SETTINGS_PATH = os.path.expanduser("~/.config/prayer-time/settings.json")

# Post-adhan (iqamah) window length in minutes
POST_PRAYER_WINDOW_MINUTES = 15

# State variables
settings = {}
next_prayer_time = None
next_prayer_name = ""
today_timings = None  # Today's timings cache for iqamah window calculation
last_checked_day = None
indicator = None
current_icon_name = None
file_monitor = None  # Reference kept globally to prevent Python GC
screensaver_active = False

# Menu item global references
item_show = None
item_exit = None

PRAYER_ICONS = {
    "Fajr": "weather-clear-night-symbolic",
    "Sunrise": "weather-few-clouds-symbolic",
    "Dhuhr": "weather-clear-symbolic",
    "Asr": "weather-few-clouds-symbolic",
    "Maghrib": "weather-clear-night-symbolic",
    "Isha": "weather-clear-night-symbolic"
}

def load_settings():
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading settings in tray helper: {e}")
    return {}

def parse_time(time_str):
    # HH:MM
    time_clean = time_str.split()[0]
    h, m = map(int, time_clean.split(':'))
    return h, m

def recalculate_next_prayer():
    global settings, next_prayer_time, next_prayer_name, today_timings
    
    next_prayer_time = None
    next_prayer_name = ""
    today_timings = None
    
    if not settings:
        return
        
    city = settings.get("city", "Jakarta")
    cache = settings.get("cache", {})
    
    now = datetime.datetime.now()
    month = now.month
    year = now.year
    
    # Get cache key matching settings.py key normalization
    normalized_city = "".join(c.lower() for c in city if c.isalnum())
    cache_key = f"{normalized_city}_{month:02d}_{year}"
    
    data = cache.get(cache_key)
    if not data:
        return
        
    today_str = now.strftime("%d-%m-%Y")
    tomorrow_str = (now + datetime.timedelta(days=1)).strftime("%d-%m-%Y")
    
    today_data = None
    tomorrow_data = None
    
    for day in data:
        g_date = day['date']['gregorian']['date']
        if g_date == today_str:
            today_data = day
        elif g_date == tomorrow_str:
            tomorrow_data = day
            
    if not today_data:
        return
        
    today_timings = today_data['timings']  # Save today's timings for iqamah check
    
    prayer_names = {
        "Fajr": "Fajr",
        "Sunrise": "Sunrise",
        "Dhuhr": "Dhuhr",
        "Asr": "Asr",
        "Maghrib": "Maghrib",
        "Isha": "Isha"
    }
    
    today_date = now.date()
    tomorrow_date = today_date + datetime.timedelta(days=1)
    
    upcoming = []
    for api_name in prayer_names.keys():
        time_str = today_timings.get(api_name)
        if time_str:
            h, m = parse_time(time_str)
            p_dt = datetime.datetime.combine(today_date, datetime.time(h, m))
            if p_dt > now:
                upcoming.append((api_name, p_dt))
                
    # If no upcoming today, get tomorrow's Fajr
    if not upcoming:
        tomorrow_fajr_str = None
        if tomorrow_data:
            tomorrow_fajr_str = tomorrow_data['timings'].get('Fajr')
        else:
            tomorrow_fajr_str = today_timings.get('Fajr')
            
        if tomorrow_fajr_str:
            h, m = parse_time(tomorrow_fajr_str)
            p_dt = datetime.datetime.combine(tomorrow_date, datetime.time(h, m))
            upcoming.append(("Fajr", p_dt))
            
    if upcoming:
        upcoming.sort(key=lambda x: x[1])
        next_prayer_name, next_prayer_time = upcoming[0]

def get_current_iqamah_prayer(timings, now):
    """
    Checks if we are within the configured post-adhan window for any prayer.
    Returns (api_name, prayer_datetime) if true, else None.
    """
    prayers = [
        ("Fajr", "Fajr"),
        ("Sunrise", "Sunrise"),
        ("Dhuhr", "Dhuhr"),
        ("Asr", "Asr"),
        ("Maghrib", "Maghrib"),
        ("Isha", "Isha")
    ]
    iqamah_keys = {
        "Fajr": "fajr_iqamah",
        "Dhuhr": "dhuhr_iqamah",
        "Asr": "asr_iqamah",
        "Maghrib": "maghrib_iqamah",
        "Isha": "isha_iqamah",
        "Sunrise": None
    }
    
    today_date = now.date()
    
    for display_name, api_name in prayers:
        time_str = timings.get(api_name)
        if time_str:
            h, m = parse_time(time_str)
            p_dt = datetime.datetime.combine(today_date, datetime.time(h, m))
            
            key = iqamah_keys.get(api_name)
            duration = settings.get(key, 10) if key else 0
            if duration <= 0:
                continue
                
            end_dt = p_dt + datetime.timedelta(minutes=duration)
            if p_dt <= now <= end_dt:
                return api_name, p_dt
                
    return None

def on_settings_changed(monitor, file, other_file, event_type):
    global settings
    # CHANGES_DONE_HINT triggers when file has finished writing and was closed
    if event_type == Gio.FileMonitorEvent.CHANGES_DONE_HINT:
        print("Settings file updated, reloading...")
        settings = load_settings()
        recalculate_next_prayer()
        update_menu_translations()

def update_menu_translations():
    global item_show, item_exit, settings
    if item_show and item_exit:
        lang = settings.get("language", "id")
        item_show.set_label(i18n.get_string("tray_show", lang))
        item_exit.set_label(i18n.get_string("tray_exit", lang))

def update_timer():
    global next_prayer_time, next_prayer_name, today_timings, indicator, current_icon_name, last_checked_day, screensaver_active, settings
    
    if screensaver_active:
        return True
        
    # Check if the day has changed
    now = datetime.datetime.now()
    day_str = now.strftime("%d-%m-%Y")
    if day_str != last_checked_day:
        last_checked_day = day_str
        recalculate_next_prayer()
    
    lang = settings.get("language", "id")
    
    # 1. Check if a prayer has just entered and we are in the iqamah window
    iqamah_active = None
    if today_timings:
        iqamah_active = get_current_iqamah_prayer(today_timings, now)
        
    if iqamah_active:
        api_name, p_dt = iqamah_active
        elapsed = now - p_dt
        seconds = int(elapsed.total_seconds())
        minutes = seconds // 60
        secs = seconds % 60
        
        translated_name = i18n.get_prayer_name(api_name, lang)
        # Display: "Maghrib +03:45"
        label_text = f" {translated_name} +{minutes:02d}:{secs:02d}"
        indicator.set_label(label_text, "00:00:00")
        
        # Set dynamic icon for the current active prayer
        icon_name = PRAYER_ICONS.get(api_name, "alarm-symbolic")
        if icon_name != current_icon_name:
            current_icon_name = icon_name
            indicator.set_icon(icon_name)
            
        return True
        
    # 2. Otherwise, display the countdown to the next prayer
    if not next_prayer_time:
        loading_text = i18n.get_string("tray_loading", lang)
        indicator.set_label(loading_text, "00:00:00")
        indicator.set_icon("alarm-symbolic")
        current_icon_name = "alarm-symbolic"
        return True
        
    diff = next_prayer_time - now
    
    # Countdown finished, recalculate on next tick
    if diff.total_seconds() <= 0:
        next_prayer_time = None
        return True
        
    # Format diff
    seconds = int(diff.total_seconds())
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    translated_name = i18n.get_prayer_name(next_prayer_name, lang)
    label_text = f" {translated_name} - {hours:02d}:{minutes:02d}:{secs:02d}"
    indicator.set_label(label_text, "00:00:00")
    
    # Dynamic Icon update
    icon_name = PRAYER_ICONS.get(next_prayer_name, "alarm-symbolic")
    if icon_name != current_icon_name:
        current_icon_name = icon_name
        indicator.set_icon(icon_name)
    
    return True

def main():
    global indicator, current_icon_name, settings, last_checked_day, file_monitor, item_show, item_exit
    
    if len(sys.argv) < 2:
        print("Usage: tray_helper.py <parent_pid>")
        sys.exit(1)
        
    parent_pid = int(sys.argv[1])
    
    # Create indicator
    indicator = appindicator.Indicator.new(
        "com.github.aska.PrayerTime.indicator",
        "alarm-symbolic",
        appindicator.IndicatorCategory.APPLICATION_STATUS
    )
    indicator.set_status(appindicator.IndicatorStatus.ACTIVE)
    current_icon_name = "alarm-symbolic"
    
    # Initial load of configuration
    now = datetime.datetime.now()
    last_checked_day = now.strftime("%d-%m-%Y")
    settings = load_settings()
    recalculate_next_prayer()
    
    # Setup GIO File Monitor for settings.json (Event-driven, no polling)
    try:
        gfile = Gio.File.new_for_path(SETTINGS_PATH)
        file_monitor = gfile.monitor_file(Gio.FileMonitorFlags.NONE, None)
        file_monitor.connect("changed", on_settings_changed)
    except Exception as e:
        print(f"Error initializing Gio.FileMonitor: {e}")
        
    # Setup Screensaver DBus monitor
    setup_screensaver_monitor()
    
    # Create Menu
    menu = Gtk.Menu()
    
    # Item 1: Show Application
    item_show = Gtk.MenuItem()
    item_show.connect("activate", on_show_clicked)
    menu.append(item_show)
    
    # Separator
    separator = Gtk.SeparatorMenuItem()
    menu.append(separator)
    
    # Item 2: Exit
    item_exit = Gtk.MenuItem()
    item_exit.connect("activate", lambda w: on_exit_clicked(parent_pid))
    menu.append(item_exit)
    
    # Apply initial translations
    update_menu_translations()
    
    menu.show_all()
    indicator.set_menu(menu)
    
    # Start timer loop (updates every 1 second)
    GLib.timeout_add_seconds(1, update_timer)
    
    # Monitor if parent process dies (updates every 2 seconds)
    GLib.timeout_add_seconds(2, check_parent_alive, parent_pid)
    
    Gtk.main()

def on_show_clicked(widget):
    import subprocess
    script_dir = os.path.dirname(os.path.abspath(__file__))
    main_path = os.path.join(script_dir, "main.py")
    subprocess.Popen(["python3", main_path])

def on_exit_clicked(parent_pid):
    import signal
    try:
        os.kill(parent_pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    Gtk.main_quit()
    sys.exit(0)

def check_parent_alive(parent_pid):
    try:
        os.kill(parent_pid, 0)
    except OSError:
        # Parent process is dead, exit tray helper
        Gtk.main_quit()
        sys.exit(0)
    return True

def on_screensaver_signal(connection, sender_name, object_path, interface_name, signal_name, parameters, user_data):
    global screensaver_active
    if signal_name == "ActiveChanged":
        screensaver_active = parameters.get_child_value(0).get_boolean()
        print(f"Screensaver active state changed in tray helper: {screensaver_active}")
        if not screensaver_active:
            # Wake up and update immediately
            update_timer()

def setup_screensaver_monitor():
    try:
        connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        connection.signal_subscribe(
            None,
            "org.freedesktop.ScreenSaver",
            "ActiveChanged",
            "/org/freedesktop/ScreenSaver",
            None,
            Gio.DBusSignalFlags.NONE,
            on_screensaver_signal,
            None
        )
        print("Subscribed to Screensaver DBus events")
    except Exception as e:
        print(f"Failed to subscribe to Screensaver DBus events: {e}")

if __name__ == "__main__":
    main()
