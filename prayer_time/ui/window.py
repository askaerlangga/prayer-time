import datetime
import subprocess
from gi.repository import Gtk, Adw, GLib, Gio, Notify
from prayer_time import settings
from prayer_time import api
from prayer_time import i18n
from prayer_time import __version__
from prayer_time.ui.location_dialog import LocationDialog
from prayer_time.ui.preferences_window import PreferencesWindow


class PrayerWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_default_size(450, 650)

        # State variables
        self.prayer_data = []
        self.today_timings = None
        self.next_prayer_api_name = ""
        self.next_prayer_time = None
        self.last_notified_prayer = None
        self.timer_id = None
        self.current_day_str = ""
        self.is_loading = False

        # Toast Overlay for in-app feedback
        self.toast_overlay = Adw.ToastOverlay()

        # Header Bar & Window Title
        self.header_bar = Adw.HeaderBar()
        self.title_widget = Adw.WindowTitle()
        self.header_bar.set_title_widget(self.title_widget)

        # Search button
        self.search_btn = Gtk.Button(icon_name="system-search-symbolic")
        self.search_btn.connect("clicked", self.on_search_clicked)
        self.header_bar.pack_start(self.search_btn)

        # Menu button
        self.menu = Gio.Menu()
        self.menu_btn = Gtk.MenuButton(icon_name="open-menu-symbolic")
        self.menu_btn.set_menu_model(self.menu)
        self.header_bar.pack_end(self.menu_btn)

        # Window actions
        refresh_action = Gio.SimpleAction.new("refresh", None)
        refresh_action.connect("activate", self.on_refresh_clicked)
        self.add_action(refresh_action)

        pref_action = Gio.SimpleAction.new("preferences", None)
        pref_action.connect("activate", self.on_preferences_clicked)
        self.add_action(pref_action)

        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self.on_about_clicked)
        self.add_action(about_action)

        # Toolbar View
        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(self.header_bar)

        # Stack for states: loading, content, error
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        # 1. Loading page
        loading_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        loading_box.set_valign(Gtk.Align.CENTER)
        loading_box.set_halign(Gtk.Align.CENTER)
        loading_spinner = Adw.Spinner()
        loading_spinner.set_size_request(32, 32)
        self.loading_label = Gtk.Label()
        self.loading_label.add_css_class("dimmed")
        loading_box.append(loading_spinner)
        loading_box.append(self.loading_label)
        self.stack.add_named(loading_box, "loading")

        # 2. Content page
        content_scroll = Gtk.ScrolledWindow()
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Countdown Card
        self.card_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.card_box.add_css_class("countdown-card")

        self.lbl_next_prayer = Gtk.Label()
        self.lbl_next_prayer.add_css_class("next-prayer-title")
        self.lbl_next_prayer.set_halign(Gtk.Align.START)

        self.lbl_countdown = Gtk.Label(label="00:00:00")
        self.lbl_countdown.add_css_class("countdown-time")
        self.lbl_countdown.set_halign(Gtk.Align.START)

        self.lbl_gregorian_date = Gtk.Label()
        self.lbl_gregorian_date.add_css_class("date-label")
        self.lbl_gregorian_date.set_halign(Gtk.Align.START)

        self.lbl_hijri_date = Gtk.Label()
        self.lbl_hijri_date.add_css_class("date-label")
        self.lbl_hijri_date.set_halign(Gtk.Align.START)

        self.card_box.append(self.lbl_next_prayer)
        self.card_box.append(self.lbl_countdown)
        self.card_box.append(self.lbl_gregorian_date)
        self.card_box.append(self.lbl_hijri_date)
        content_box.append(self.card_box)

        # Boxed List for timings
        self.prayer_group = Adw.PreferencesGroup()
        self.prayer_group.set_margin_start(12)
        self.prayer_group.set_margin_end(12)
        self.prayer_group.set_margin_bottom(24)

        self.rows = {}
        for api_name in i18n.PRAYER_ICONS.keys():
            row = Adw.ActionRow()
            row.set_icon_name(i18n.get_icon(api_name))

            time_lbl = Gtk.Label()
            time_lbl.add_css_class("prayer-time-label")
            row.add_suffix(time_lbl)

            self.prayer_group.add(row)
            self.rows[api_name] = (row, time_lbl)

        content_box.append(self.prayer_group)
        content_scroll.set_child(content_box)
        self.stack.add_named(content_scroll, "content")

        # 3. Error page
        self.error_page = Adw.StatusPage()
        self.error_page.set_icon_name("network-offline-symbolic")
        self.retry_btn = Gtk.Button()
        self.retry_btn.add_css_class("pill")
        self.retry_btn.add_css_class("suggested-action")
        self.retry_btn.connect("clicked", self.on_refresh_clicked)
        self.error_page.set_child(self.retry_btn)
        self.stack.add_named(self.error_page, "error")

        # Set content inside ToastOverlay
        self.toast_overlay.set_child(self.stack)
        toolbar_view.set_content(self.toast_overlay)
        self.set_content(toolbar_view)

        # Apply initial translations
        self.update_translations()

        # Initial load
        self.load_data()

        # Window lifecycle & visibility management
        self.connect("close-request", self.on_close_request)
        self.connect("notify::visible", self.on_visibility_changed)

        # Start timer if visible
        self._ensure_timer()

    def _ensure_timer(self):
        if not self.timer_id:
            self.timer_id = GLib.timeout_add_seconds(1, self.update_tick)

    def _stop_timer(self):
        if self.timer_id:
            GLib.source_remove(self.timer_id)
            self.timer_id = None

    def on_visibility_changed(self, widget, pspec):
        if self.get_visible():
            self.update_ui()
            self._ensure_timer()
        else:
            self._stop_timer()

    def on_close_request(self, window):
        self.set_visible(False)
        return True  # Prevent destruction to keep running in background

    def show_toast(self, message):
        toast = Adw.Toast.new(message)
        self.toast_overlay.add_toast(toast)

    def update_translations(self):
        lang = settings.get_setting("language", "id")

        self.title_widget.set_title(i18n.get_string("app_title", lang))
        self.search_btn.set_tooltip_text(i18n.get_string("search_tooltip", lang))
        self.menu_btn.set_tooltip_text(i18n.get_string("menu_tooltip", lang))

        self.menu.remove_all()
        self.menu.append(i18n.get_string("refresh_tooltip", lang), "win.refresh")
        self.menu.append(i18n.get_string("preferences", lang), "win.preferences")
        self.menu.append(i18n.get_string("about", lang), "win.about")

        self.loading_label.set_label(i18n.get_string("loading_data", lang))

        self.prayer_group.set_title(i18n.get_string("today_schedule", lang))
        for api_name, (row, time_lbl) in self.rows.items():
            row.set_title(i18n.get_prayer_name(api_name, lang))

        self.error_page.set_title(i18n.get_string("failed_load_schedule", lang))
        self.error_page.set_description(i18n.get_string("check_connection", lang))
        self.retry_btn.set_label(i18n.get_string("retry_btn", lang))

        self.update_ui()

    def load_data(self, silent=False):
        if self.is_loading:
            return

        self.is_loading = True
        if not silent or not self.prayer_data:
            self.stack.set_visible_child_name("loading")

        city = settings.get_setting("city", "Jakarta")
        country = settings.get_setting("country", "Indonesia")
        lat = settings.get_setting("latitude", -6.2088)
        lon = settings.get_setting("longitude", 106.8456)
        method = settings.get_setting("method", 20)
        myquran_id = settings.get_setting("myquran_id")

        self.title_widget.set_subtitle(f"{city}, {country}")

        now = datetime.datetime.now()
        cached = settings.get_cached_timings(city, now.month, now.year)
        if cached:
            self.on_data_loaded(cached, None)
        else:
            api.fetch_prayer_times_async(lat, lon, method, now.month, now.year, myquran_id, self.on_data_loaded)

    def on_data_loaded(self, data, error):
        self.is_loading = False
        if error:
            if not self.prayer_data:
                lang = settings.get_setting("language", "id")
                desc = i18n.get_string("search_error", lang)
                self.error_page.set_description(f"{desc}: {error}")
                self.stack.set_visible_child_name("error")
            return

        city = settings.get_setting("city", "Jakarta")
        now = datetime.datetime.now()
        settings.set_cached_timings(city, now.month, now.year, data)

        self.prayer_data = data
        self.update_ui()
        self.stack.set_visible_child_name("content")

    def update_ui(self):
        if not self.prayer_data:
            return

        now = datetime.datetime.now()
        today_str = now.strftime("%d-%m-%Y")

        today_data = None
        for day in self.prayer_data:
            if day.get("date", {}).get("gregorian", {}).get("date") == today_str:
                today_data = day
                break

        if not today_data:
            self.load_data(silent=True)
            return

        self.current_day_str = today_str
        timings = today_data.get("timings", {})
        self.today_timings = timings
        hijri = today_data.get("date", {}).get("hijri", {})
        greg = today_data.get("date", {}).get("gregorian", {})

        # Gregorian Date
        g_day = greg.get("day", "")
        g_month = greg.get("month", {}).get("en", "")
        g_year = greg.get("year", "")
        g_weekday = greg.get("weekday", {}).get("en", "")

        lang = settings.get_setting("language", "id")
        formatted_date = i18n.format_gregorian_date(g_day, g_month, g_year, g_weekday, lang)
        self.lbl_gregorian_date.set_label(formatted_date)

        # Hijri Date
        h_day = hijri.get("day", "")
        h_month = hijri.get("month", {}).get("en", "")
        h_year = hijri.get("year", "")
        hijri_suffix = "AH" if lang == "en" else "H"
        self.lbl_hijri_date.set_label(f"{h_day} {h_month} {h_year} {hijri_suffix}")

        # Update row values
        for api_name, (row, time_lbl) in self.rows.items():
            time_raw = timings.get(api_name, "")
            time_clean = time_raw.split()[0] if time_raw else ""
            time_lbl.set_label(time_clean)

        self.recalculate_next_prayer(timings)

    def parse_time(self, time_str):
        if not time_str:
            return 0, 0
        clean = time_str.split()[0]
        h, m = map(int, clean.split(":"))
        return h, m

    def get_current_iqamah_prayer(self, timings):
        prayers = [
            ("Fajr", "fajr_iqamah"),
            ("Dhuhr", "dhuhr_iqamah"),
            ("Asr", "asr_iqamah"),
            ("Maghrib", "maghrib_iqamah"),
            ("Isha", "isha_iqamah"),
        ]
        now = datetime.datetime.now()
        today_date = now.date()

        for api_name, key in prayers:
            time_str = timings.get(api_name)
            if time_str:
                h, m = self.parse_time(time_str)
                p_dt = datetime.datetime.combine(today_date, datetime.time(h, m))
                duration = settings.get_setting(key, 10)
                if duration <= 0:
                    continue

                end_dt = p_dt + datetime.timedelta(minutes=duration)
                if p_dt <= now <= end_dt:
                    return api_name, p_dt
        return None

    def recalculate_next_prayer(self, today_timings):
        now = datetime.datetime.now()
        today_date = now.date()
        tomorrow_date = today_date + datetime.timedelta(days=1)

        iqamah_active = self.get_current_iqamah_prayer(today_timings)
        if iqamah_active:
            api_name, p_dt = iqamah_active
            translated_name = i18n.get_prayer_name(api_name)
            prefix = i18n.get_string("sunrise_active") if api_name == "Sunrise" else f"{i18n.get_string('prayer_time_active')}: {translated_name}"
            self.lbl_next_prayer.set_label(prefix)
            self.highlight_active_row(api_name)

            is_night = (api_name in ["Fajr", "Maghrib", "Isha"])
            self.card_box.remove_css_class("countdown-card")
            self.card_box.remove_css_class("countdown-card-night")
            self.card_box.add_css_class("countdown-card-night" if is_night else "countdown-card")

        upcoming = []
        for api_name in i18n.PRAYER_ICONS.keys():
            time_str = today_timings.get(api_name)
            if time_str:
                h, m = self.parse_time(time_str)
                p_dt = datetime.datetime.combine(today_date, datetime.time(h, m))
                if p_dt > now:
                    upcoming.append((api_name, p_dt))

        if not upcoming:
            tomorrow_str = tomorrow_date.strftime("%d-%m-%Y")
            tomorrow_data = None
            for day in self.prayer_data:
                if day.get("date", {}).get("gregorian", {}).get("date") == tomorrow_str:
                    tomorrow_data = day
                    break

            tomorrow_fajr = tomorrow_data.get("timings", {}).get("Fajr") if tomorrow_data else today_timings.get("Fajr")
            if tomorrow_fajr:
                h, m = self.parse_time(tomorrow_fajr)
                p_dt = datetime.datetime.combine(tomorrow_date, datetime.time(h, m))
                upcoming.append(("Fajr", p_dt))

        if upcoming:
            upcoming.sort(key=lambda x: x[1])
            next_name_api, next_dt = upcoming[0]
            self.next_prayer_api_name = next_name_api
            self.next_prayer_time = next_dt

            if not iqamah_active:
                translated_name = i18n.get_prayer_name(next_name_api)
                self.lbl_next_prayer.set_label(f"{i18n.get_string('next_prayer')}: {translated_name}")
                self.highlight_active_row(next_name_api)

                is_night = (next_name_api == "Fajr")
                self.card_box.remove_css_class("countdown-card")
                self.card_box.remove_css_class("countdown-card-night")
                self.card_box.add_css_class("countdown-card-night" if is_night else "countdown-card")

    def highlight_active_row(self, active_api_name):
        for api_name, (row, time_lbl) in self.rows.items():
            row.remove_css_class("active-prayer-row")
            if api_name == active_api_name:
                row.add_css_class("active-prayer-row")

    def update_tick(self):
        now = datetime.datetime.now()

        # Day rollover check
        day_str = now.strftime("%d-%m-%Y")
        if self.current_day_str and day_str != self.current_day_str:
            self.current_day_str = day_str
            self.update_ui()

        # Check if next prayer time arrived
        if self.next_prayer_time:
            diff = self.next_prayer_time - now
            if diff.total_seconds() <= 0:
                self.trigger_prayer_notification()
                if self.today_timings:
                    self.recalculate_next_prayer(self.today_timings)

        # Iqamah count-up window
        if self.today_timings:
            iqamah_active = self.get_current_iqamah_prayer(self.today_timings)
            if iqamah_active:
                api_name, p_dt = iqamah_active
                elapsed = now - p_dt
                seconds = int(elapsed.total_seconds())
                minutes = seconds // 60
                secs = seconds % 60

                translated_name = i18n.get_prayer_name(api_name)
                prefix = i18n.get_string("sunrise_active") if api_name == "Sunrise" else f"{i18n.get_string('prayer_time_active')}: {translated_name}"
                self.lbl_next_prayer.set_label(prefix)
                self.lbl_countdown.set_label(f"+{minutes:02d}:{secs:02d}")
                self.highlight_active_row(api_name)
                return True

        if not self.next_prayer_time:
            return True

        diff = self.next_prayer_time - now
        seconds = max(0, int(diff.total_seconds()))
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60

        self.lbl_countdown.set_label(f"{hours:02d}:{minutes:02d}:{secs:02d}")
        return True

    def trigger_prayer_notification(self):
        if self.last_notified_prayer == self.next_prayer_time:
            return

        self.last_notified_prayer = self.next_prayer_time

        try:
            time_str = self.next_prayer_time.strftime("%H:%M")
            lang = settings.get_setting("language", "id")

            if self.next_prayer_api_name == "Sunrise":
                title = i18n.get_string("notif_sunrise_title", lang)
                body = i18n.get_string("notif_sunrise_body", lang).format(time_str)
            else:
                title = i18n.get_string("notif_title", lang)
                prayer_name = i18n.get_prayer_name(self.next_prayer_api_name, lang)
                body = i18n.get_string("notif_body", lang).format(prayer_name, time_str)

            notification = Notify.Notification.new(title, body, "alarm-symbolic")
            notification.set_urgency(Notify.Urgency.NORMAL)
            notification.show()
        except Exception as e:
            print(f"[PrayerTime] Error sending notification: {e}")

        # Audio chime alert
        if settings.get_setting("enable_audio", True):
            try:
                subprocess.Popen(["canberra-gtk-play", "--id", "complete"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

    def on_search_clicked(self, btn):
        dialog = LocationDialog(self, self.on_location_selected)
        if hasattr(dialog, "present"):
            try:
                dialog.present(self)
            except TypeError:
                dialog.present()

    def on_location_selected(self, location_data):
        settings.set_setting("city", location_data["city"])
        settings.set_setting("country", location_data["country"])
        settings.set_setting("latitude", location_data["lat"])
        settings.set_setting("longitude", location_data["lon"])

        # Reset cache for fresh location data
        config = settings.load_settings()
        config["cache"] = {}
        settings.save_settings(config)

        lang = settings.get_setting("language", "id")
        self.show_toast(f"Lokasi diubah ke {location_data['city']}" if lang == "id" else f"Location changed to {location_data['city']}")

        if location_data.get("country") == "Indonesia":
            self.stack.set_visible_child_name("loading")
            api.get_myquran_id_async(location_data, self.on_myquran_id_resolved)
        else:
            settings.set_setting("myquran_id", None)
            self.load_data()

    def on_myquran_id_resolved(self, myquran_id):
        settings.set_setting("myquran_id", myquran_id)
        self.load_data()

    def on_refresh_clicked(self, widget_or_action=None, param=None):
        city = settings.get_setting("city", "Jakarta")
        now = datetime.datetime.now()
        key = settings.get_cache_key(city, now.month, now.year)

        config = settings.load_settings()
        if "cache" in config and key in config["cache"]:
            config["cache"].pop(key)
            settings.save_settings(config)

        lang = settings.get_setting("language", "id")
        self.show_toast("Jadwal diperbarui" if lang == "id" else "Schedule refreshed")
        self.load_data()

    def on_preferences_clicked(self, action, param):
        dialog = PreferencesWindow(self)
        dialog.present()

    def on_about_clicked(self, action, param):
        lang = settings.get_setting("language", "id")
        about = Adw.AboutWindow(
            transient_for=self,
            application_name=i18n.get_string("app_title", lang),
            application_icon="com.github.aska.PrayerTime",
            version=__version__,
            copyright="© 2026 Aska Erlangga",
            license_type=Gtk.License.GPL_3_0,
            developer_name="Aska Erlangga",
            developers=["Aska Erlangga"],
            designers=["Aska Erlangga"],
            website="https://github.com/askaerlangga/prayer-time",
            issue_url="https://github.com/askaerlangga/prayer-time/issues",
            comments=i18n.get_string("about_comments", lang)
        )
        about.present()
