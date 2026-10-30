from prayer_time import settings


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
        "recent_locations": "Riwayat Lokasi",
        "search_results": "Hasil Pencarian",
        "clear_history": "Hapus Semua",
        "clear_history_tooltip": "Hapus semua riwayat lokasi",
        "delete_history_item_tooltip": "Hapus dari riwayat",
        "no_history": "Belum ada riwayat lokasi",
        "no_history_sub": "Cari kota atau daerah pada kolom di atas",
        "next_prayer": "Salat Berikutnya",
        "prayer_time_active": "Waktu Salat",
        "about_comments": "Aplikasi Pengingat Waktu Salat Desktop berbasis GTK 4 & Libadwaita.",
        "location_changed": "Lokasi diubah ke {}",
        "schedule_refreshed": "Jadwal diperbarui",
        "quit": "Keluar",
        "notif_title": "Waktu Salat",
        "notif_body": "Saatnya menunaikan salat ({}).",
        "notif_sunrise_title": "Terbit Matahari",
        "notif_sunrise_body": "Waktu Subuh telah berakhir ({}).",
        "sunrise_active": "Waktu Terbit",
        "tray_show": "Tampilkan Aplikasi",
        "tray_exit": "Keluar",
        "tray_loading": "Memuat...",
        "pref_general": "Umum",
        "pref_autostart": "Mulai Otomatis saat Boot",
        "pref_autostart_sub": "Jalankan aplikasi otomatis saat masuk sistem",
        "pref_audio": "Nada Pengingat Salat",
        "pref_audio_sub": "Putar bunyi bel lembut saat masuk waktu salat",
        "pref_location": "Lokasi",
        "pref_auto_location": "Lokasi Otomatis (Geoclue)",
        "pref_auto_location_sub": "Deteksi dan perbarui lokasi otomatis menggunakan Geoclue",
        "use_current_location": "Gunakan Lokasi Saat Ini",
        "use_current_location_sub": "Deteksi otomatis via Geoclue",
        "detecting_location": "Mendeteksi lokasi saat ini...",
        "location_detected": "Lokasi terdeteksi: {}",
        "location_detect_failed": "Gagal mendeteksi lokasi: {}",
        "geoclue_not_available": "Layanan Geoclue tidak tersedia",
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
        "recent_locations": "Recent Locations",
        "search_results": "Search Results",
        "clear_history": "Clear All",
        "clear_history_tooltip": "Clear all location history",
        "delete_history_item_tooltip": "Remove from history",
        "no_history": "No recent locations",
        "no_history_sub": "Search for a city or region in the entry above",
        "next_prayer": "Next Prayer",
        "prayer_time_active": "Prayer Time",
        "about_comments": "A desktop prayer time reminder application based on GTK 4 & Libadwaita.",
        "location_changed": "Location changed to {}",
        "schedule_refreshed": "Schedule refreshed",
        "quit": "Quit",
        "notif_title": "Prayer Times",
        "notif_body": "It's time to pray ({}).",
        "notif_sunrise_title": "Sunrise",
        "notif_sunrise_body": "Fajr time has ended ({}).",
        "sunrise_active": "Sunrise Time",
        "tray_show": "Show Application",
        "tray_exit": "Exit",
        "tray_loading": "Loading...",
        "pref_general": "General",
        "pref_autostart": "Run Automatically on Boot",
        "pref_autostart_sub": "Start application automatically on login",
        "pref_audio": "Prayer Alert Tone",
        "pref_audio_sub": "Play a soft chime when prayer time arrives",
        "pref_location": "Location",
        "pref_auto_location": "Automatic Location (Geoclue)",
        "pref_auto_location_sub": "Automatically detect and update location using Geoclue",
        "use_current_location": "Use Current Location",
        "use_current_location_sub": "Detect automatically via Geoclue",
        "detecting_location": "Detecting current location...",
        "location_detected": "Location detected: {}",
        "location_detect_failed": "Failed to detect location: {}",
        "geoclue_not_available": "Geoclue service is not available",
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
