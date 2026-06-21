import settings

STRINGS = {
    "id": {
        "app_title": "Waktu Salat",
        "search_tooltip": "Cari Lokasi",
        "refresh_tooltip": "Segarkan Jadwal",
        "menu_tooltip": "Menu",
        "preferences": "Pengaturan",
        "about": "Tentang Aplikasi",
        "loading_dialog_title": "Cari Lokasi",
        "search_entry_title": "Nama Kota / Daerah",
        "loading_data": "Memuat jadwal salat...",
        "today_schedule": "Jadwal Hari Ini",
        "failed_load_schedule": "Gagal Memuat Jadwal",
        "check_connection": "Periksa koneksi internet Anda atau coba lagi.",
        "retry_btn": "Coba Lagi",
        "search_error": "Gagal memuat hasil pencarian",
        "search_not_found": "Lokasi tidak ditemukan",
        "next_prayer": "Salat Berikutnya",
        "prayer_time_active": "Waktu Salat",
        "about_comments": "Aplikasi Pengingat Waktu Salat Desktop berbasis GTK 4 & Libadwaita.",
        "notif_title": "Waktu Salat",
        "notif_body": "Waktu salat {} telah tiba ({}).",
        "tray_show": "Tampilkan Aplikasi",
        "tray_exit": "Keluar",
        "tray_loading": "Memuat...",
        "pref_general": "Umum",
        "pref_autostart": "Mulai Otomatis saat Boot",
        "pref_autostart_sub": "Jalankan aplikasi otomatis saat masuk sistem",
        "pref_audio": "Nada Pengingat Salat",
        "pref_audio_sub": "Putar bunyi bel lembut saat masuk waktu salat",
        "pref_iqamah_group": "Jeda Waktu Iqamah (Menit)",
        "pref_lang": "Bahasa",
        "pref_lang_sub": "Pilih bahasa tampilan antarmuka",
        "fajr": "Subuh",
        "sunrise": "Terbit",
        "dhuhr": "Zuhur",
        "asr": "Asar",
        "maghrib": "Magrib",
        "isha": "Isya"
    },
    "en": {
        "app_title": "Prayer Times",
        "search_tooltip": "Search Location",
        "refresh_tooltip": "Refresh Schedule",
        "menu_tooltip": "Menu",
        "preferences": "Preferences",
        "about": "About Application",
        "loading_dialog_title": "Search Location",
        "search_entry_title": "City or Region",
        "loading_data": "Loading prayer schedule...",
        "today_schedule": "Today's Schedule",
        "failed_load_schedule": "Failed to Load Schedule",
        "check_connection": "Check your internet connection or try again.",
        "retry_btn": "Try Again",
        "search_error": "Failed to load search results",
        "search_not_found": "Location not found",
        "next_prayer": "Next Prayer",
        "prayer_time_active": "Prayer Time",
        "about_comments": "A desktop prayer time reminder application based on GTK 4 & Libadwaita.",
        "notif_title": "Prayer Times",
        "notif_body": "Prayer time for {} has arrived ({}).",
        "tray_show": "Show Application",
        "tray_exit": "Exit",
        "tray_loading": "Loading...",
        "pref_general": "General",
        "pref_autostart": "Run Automatically on Boot",
        "pref_autostart_sub": "Start application automatically on login",
        "pref_audio": "Prayer Alert Tone",
        "pref_audio_sub": "Play a soft chime when prayer time arrives",
        "pref_iqamah_group": "Iqamah Wait Time (Minutes)",
        "pref_lang": "Language",
        "pref_lang_sub": "Choose UI display language",
        "fajr": "Fajr",
        "sunrise": "Sunrise",
        "dhuhr": "Dhuhr",
        "asr": "Asr",
        "maghrib": "Maghrib",
        "isha": "Isha"
    }
}

PRAYER_NAMES = {
    "id": {
        "Fajr": "Subuh",
        "Sunrise": "Terbit",
        "Dhuhr": "Zuhur",
        "Asr": "Asar",
        "Maghrib": "Magrib",
        "Isha": "Isya"
    },
    "en": {
        "Fajr": "Fajr",
        "Sunrise": "Sunrise",
        "Dhuhr": "Dhuhr",
        "Asr": "Asr",
        "Maghrib": "Maghrib",
        "Isha": "Isha"
    }
}

PRAYER_ICONS = {
    "Fajr": "weather-clear-night-symbolic",
    "Sunrise": "weather-few-clouds-symbolic",
    "Dhuhr": "weather-clear-symbolic",
    "Asr": "weather-few-clouds-symbolic",
    "Maghrib": "weather-clear-night-symbolic",
    "Isha": "weather-clear-night-symbolic"
}

WEEKDAYS = {
    "id": {
        "Monday": "Senin", "Tuesday": "Selasa", "Wednesday": "Rabu",
        "Thursday": "Kamis", "Friday": "Jumat", "Saturday": "Sabtu", "Sunday": "Ahad"
    }
}

MONTHS = {
    "id": {
        "January": "Januari", "February": "Februari", "March": "Maret",
        "April": "April", "May": "Mei", "June": "Juni",
        "July": "Juli", "August": "Agustus", "September": "September",
        "October": "Oktober", "November": "November", "December": "Desember"
    }
}

def get_string(key, lang=None):
    if not lang:
        lang = settings.get_setting("language", "id")
    return STRINGS.get(lang, STRINGS["id"]).get(key, key)

def get_prayer_name(api_name, lang=None):
    if not lang:
        lang = settings.get_setting("language", "id")
    return PRAYER_NAMES.get(lang, PRAYER_NAMES["id"]).get(api_name, api_name)

def get_icon(api_name):
    return PRAYER_ICONS.get(api_name, "time-symbolic")

def format_gregorian_date(day, month_en, year, weekday_en, lang=None):
    if not lang:
        lang = settings.get_setting("language", "id")
    
    if lang == "en":
        return f"{weekday_en}, {day} {month_en} {year}"
    else:
        weekday_id = WEEKDAYS["id"].get(weekday_en, weekday_en)
        month_id = MONTHS["id"].get(month_en, month_en)
        return f"{weekday_id}, {day} {month_id} {year}"
