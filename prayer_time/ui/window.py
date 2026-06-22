import datetime
import gi
gi.require_version('Notify', '0.7')
from gi.repository import Gtk, Adw, GLib, Gio, GObject, Notify
from prayer_time import settings
from prayer_time import api
from prayer_time.ui.location_dialog import LocationDialog
from prayer_time import i18n
from prayer_time import __version__
from prayer_time.ui.preferences_window import PreferencesWindow


class PrayerWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_default_size(450, 650)
        
        # State variables
        self.prayer_data = [] # Current month timings
        self.today_timings = None # Today's timings cache for iqamah window calculation
        self.next_prayer_api_name = ""
        self.next_prayer_time = None
        self.last_notified_prayer = None
        self.timer_id = None
        
        # Header Bar & Window Title
        self.header_bar = Adw.HeaderBar()
        self.title_widget = Adw.WindowTitle()
        self.header_bar.set_title_widget(self.title_widget)
        
        # Header bar search button (start)
        self.search_btn = Gtk.Button(icon_name="system-search-symbolic")
        self.search_btn.connect("clicked", self.on_search_clicked)
        self.header_bar.pack_start(self.search_btn)
        
        # Header bar menu button (end)
        self.menu = Gio.Menu()
        self.menu_btn = Gtk.MenuButton()
        self.menu_btn.set_icon_name("open-menu-symbolic")
        self.menu_btn.set_menu_model(self.menu)
        self.header_bar.pack_end(self.menu_btn)
        
        # Register window actions for the menu items
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
        
        # Stack for different app states: loading, content, error
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
            
            # Label suffix for time
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
        
        # Set main child
        toolbar_view.set_content(self.stack)
        self.set_content(toolbar_view)
        
        # Apply initial translations
        self.update_translations()
        
        # Initial load
        self.load_data()
        
        # Start the countdown timer
        self.timer_id = GLib.timeout_add_seconds(1, self.update_tick)
        
        # Hide window on close-request instead of destroying it to keep it running in the background
        self.connect("close-request", self.on_close_request)
        
        # Initialize libnotify for reliable system notifications
        try:
            Notify.init(i18n.get_string("app_title"))
        except Exception as e:
            print(f"Failed to initialize libnotify: {e}")

    def update_translations(self):
        lang = settings.get_setting("language", "id")
        
        # Window & Header Bar
        self.title_widget.set_title(i18n.get_string("app_title", lang))
        self.search_btn.set_tooltip_text(i18n.get_string("search_tooltip", lang))
        self.menu_btn.set_tooltip_text(i18n.get_string("menu_tooltip", lang))
        
        # Menu
        self.menu.remove_all()
        self.menu.append(i18n.get_string("refresh_tooltip", lang), "win.refresh")
        self.menu.append(i18n.get_string("preferences", lang), "win.preferences")
        self.menu.append(i18n.get_string("about", lang), "win.about")
        
        # Loading Page
        self.loading_label.set_label(i18n.get_string("loading_data", lang))
        
        # Prayer Group (Today's Schedule)
        self.prayer_group.set_title(i18n.get_string("today_schedule", lang))
        for api_name, (row, time_lbl) in self.rows.items():
            row.set_title(i18n.get_prayer_name(api_name, lang))
            
        # Error Page
        self.error_page.set_title(i18n.get_string("failed_load_schedule", lang))
        self.error_page.set_description(i18n.get_string("check_connection", lang))
        self.retry_btn.set_label(i18n.get_string("retry_btn", lang))
        
        # Re-render date / active info
        self.update_ui()

    def on_close_request(self, window):
        self.set_visible(False)
        return True  # Prevent the default close handler from destroying the window

    def load_data(self):
        self.stack.set_visible_child_name("loading")
        
        # Read settings
        city = settings.get_setting("city")
        country = settings.get_setting("country")
        lat = settings.get_setting("latitude")
        lon = settings.get_setting("longitude")
        method = settings.get_setting("method")
        myquran_id = settings.get_setting("myquran_id")
        
        # Update title details
        self.title_widget.set_subtitle(f"{city}, {country}")
        
        now = datetime.datetime.now()
        month = now.month
        year = now.year
        
        # Check cache first
        cached = settings.get_cached_timings(city, month, year)
        if cached:
            print("Loading prayer times from cache")
            self.on_data_loaded(cached, None)
        else:
            print(f"Fetching prayer times online for {city} ({lat}, {lon}), MyQuran ID: {myquran_id}")
            api.fetch_prayer_times_async(lat, lon, method, month, year, myquran_id, self.on_data_loaded)

    def on_data_loaded(self, data, error):
        if error:
            print(f"Error loading prayer data: {error}")
            # If we don't have any data on screen, show error page
            if not self.prayer_data:
                lang = settings.get_setting("language", "id")
                desc = i18n.get_string("search_error", lang)
                self.error_page.set_description(f"{desc}: {error}")
                self.stack.set_visible_child_name("error")
            return
            
        # Cache data if not already cached
        city = settings.get_setting("city")
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
            if day['date']['gregorian']['date'] == today_str:
                today_data = day
                break
                
        if not today_data:
            # Data for today not found in cache (e.g. month changed)
            # Re-fetch online
            self.load_data()
            return
            
        timings = today_data['timings']
        self.today_timings = timings
        hijri = today_data['date']['hijri']
        greg = today_data['date']['gregorian']
        
        # Format Masehi Date
        g_day = greg['day']
        g_month = greg['month']['en']
        g_year = greg['year']
        g_weekday = greg['weekday']['en']
        
        lang = settings.get_setting("language", "id")
        formatted_date = i18n.format_gregorian_date(g_day, g_month, g_year, g_weekday, lang)
        self.lbl_gregorian_date.set_label(formatted_date)
        
        # Format Hijri Date
        h_day = hijri['day']
        h_month = hijri['month']['en']
        h_year = hijri['year']
        hijri_suffix = "AH" if lang == "en" else "H"
        self.lbl_hijri_date.set_label(f"{h_day} {h_month} {h_year} {hijri_suffix}")
        
        # Update row values
        for api_name, (row, time_lbl) in self.rows.items():
            time_raw = timings.get(api_name, "")
            # Clean up time (e.g. "04:34 (WIB)" -> "04:34")
            time_clean = time_raw.split()[0]
            time_lbl.set_label(time_clean)
            
        # Calculate next prayer
        self.recalculate_next_prayer(timings)

    def parse_time(self, time_str):
        # Format HH:MM
        time_clean = time_str.split()[0]
        h, m = map(int, time_clean.split(':'))
        return h, m

    def get_current_iqamah_prayer(self, timings):
        """
        Checks if we are within the configured post-adhan window for any prayer.
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
        now = datetime.datetime.now()
        today_date = now.date()
        
        for display_name, api_name in prayers:
            time_str = timings.get(api_name)
            if time_str:
                h, m = self.parse_time(time_str)
                p_dt = datetime.datetime.combine(today_date, datetime.time(h, m))
                
                key = iqamah_keys.get(api_name)
                duration = settings.get_setting(key, 10) if key else 0
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
        
        # Check if iqamah is active right now
        iqamah_active = self.get_current_iqamah_prayer(today_timings)
        if iqamah_active:
            api_name, p_dt = iqamah_active
            translated_name = i18n.get_prayer_name(api_name)
            self.lbl_next_prayer.set_label(f"{i18n.get_string('prayer_time_active')}: {translated_name}")
            self.highlight_active_row(api_name)
            
            is_night = (api_name in ["Fajr", "Maghrib", "Isha"])
            self.card_box.remove_css_class("countdown-card")
            self.card_box.remove_css_class("countdown-card-night")
            if is_night:
                self.card_box.add_css_class("countdown-card-night")
            else:
                self.card_box.add_css_class("countdown-card")
        
        upcoming = []
        for api_name in i18n.PRAYER_ICONS.keys():
            time_str = today_timings.get(api_name)
            if time_str:
                h, m = self.parse_time(time_str)
                p_dt = datetime.datetime.combine(today_date, datetime.time(h, m))
                if p_dt > now:
                    upcoming.append((api_name, p_dt))
                    
        # Check tomorrow's Fajr if all today's prayers have passed
        if not upcoming:
            tomorrow_str = tomorrow_date.strftime("%d-%m-%Y")
            tomorrow_data = None
            for day in self.prayer_data:
                if day['date']['gregorian']['date'] == tomorrow_str:
                    tomorrow_data = day
                    break
            
            tomorrow_fajr_str = None
            if tomorrow_data:
                tomorrow_fajr_str = tomorrow_data['timings'].get('Fajr')
            else:
                # Fallback to today's Fajr if tomorrow not fetched yet
                tomorrow_fajr_str = today_timings.get('Fajr')
                
            if tomorrow_fajr_str:
                h, m = self.parse_time(tomorrow_fajr_str)
                p_dt = datetime.datetime.combine(tomorrow_date, datetime.time(h, m))
                upcoming.append(('Fajr', p_dt))
                
        if upcoming:
            # Sort by datetime
            upcoming.sort(key=lambda x: x[1])
            next_name_api, next_dt = upcoming[0]
            self.next_prayer_api_name = next_name_api
            self.next_prayer_time = next_dt
            
            # Only update the countdown card labels if not actively in iqamah
            if not iqamah_active:
                translated_name = i18n.get_prayer_name(next_name_api)
                self.lbl_next_prayer.set_label(f"{i18n.get_string('next_prayer')}: {translated_name}")
                self.highlight_active_row(next_name_api)
                
                is_night = (next_name_api == "Fajr")
                self.card_box.remove_css_class("countdown-card")
                self.card_box.remove_css_class("countdown-card-night")
                if is_night:
                    self.card_box.add_css_class("countdown-card-night")
                else:
                    self.card_box.add_css_class("countdown-card")

    def highlight_active_row(self, active_api_name):
        for api_name, (row, time_lbl) in self.rows.items():
            row.remove_css_class("active-prayer-row")
            if api_name == active_api_name:
                row.add_css_class("active-prayer-row")

    def update_tick(self):
        now = datetime.datetime.now()
        
        # 1. Check if we are in the 15-minute iqamah count-up window
        if self.today_timings:
            iqamah_active = self.get_current_iqamah_prayer(self.today_timings)
            if iqamah_active:
                api_name, p_dt = iqamah_active
                elapsed = now - p_dt
                seconds = int(elapsed.total_seconds())
                minutes = seconds // 60
                secs = seconds % 60
                
                translated_name = i18n.get_prayer_name(api_name)
                self.lbl_next_prayer.set_label(f"{i18n.get_string('prayer_time_active')}: {translated_name}")
                self.lbl_countdown.set_label(f"+{minutes:02d}:{secs:02d}")
                self.highlight_active_row(api_name)
                
                is_night = (api_name in ["Fajr", "Maghrib", "Isha"])
                self.card_box.remove_css_class("countdown-card")
                self.card_box.remove_css_class("countdown-card-night")
                if is_night:
                    self.card_box.add_css_class("countdown-card-night")
                else:
                    self.card_box.add_css_class("countdown-card")
                    
                return True
                
        # 2. Otherwise, normal countdown to the next prayer
        if not self.next_prayer_time:
            return True
            
        diff = self.next_prayer_time - now
        
        # Countdown completed
        if diff.total_seconds() <= 0:
            # Trigger notification
            self.trigger_prayer_notification()
            
            # Recalculate
            self.load_data()
            return True
            
        # Format countdown
        seconds = int(diff.total_seconds())
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        self.lbl_countdown.set_label(f"{hours:02d}:{minutes:02d}:{secs:02d}")
        return True

    def trigger_prayer_notification(self):
        # Prevent double notification
        if self.last_notified_prayer == self.next_prayer_time:
            return
            
        self.last_notified_prayer = self.next_prayer_time
        
        try:
            time_str = self.next_prayer_time.strftime("%H:%M")
            lang = settings.get_setting("language", "id")
            title = i18n.get_string("notif_title", lang)
            prayer_name = i18n.get_prayer_name(self.next_prayer_api_name, lang)
            body = i18n.get_string("notif_body", lang).format(prayer_name, time_str)
            
            notification = Notify.Notification.new(
                title,
                body,
                "alarm-symbolic"
            )
            notification.set_urgency(Notify.Urgency.NORMAL)
            notification.show()
            print(f"Sent notification for {prayer_name} at {time_str}")
        except Exception as e:
            print(f"Error sending notification via libnotify: {e}")
            
        # Play audio alert if enabled
        if settings.get_setting("enable_audio", True):
            try:
                import subprocess
                subprocess.Popen(["canberra-gtk-play", "--id", "complete"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                print(f"Error playing audio chime: {e}")

    def on_search_clicked(self, btn):
        dialog = LocationDialog(self, self.on_location_selected)
        dialog.present(self)
        
    def on_location_selected(self, location_data):
        print(f"Location selected: {location_data['city']}, {location_data['country']}")
        settings.set_setting("city", location_data["city"])
        settings.set_setting("country", location_data["country"])
        settings.set_setting("latitude", location_data["lat"])
        settings.set_setting("longitude", location_data["lon"])
        
        # Clear cache to force fresh fetch for the new location
        config = settings.load_settings()
        config["cache"] = {}
        settings.save_settings(config)
        
        # Resolve MyQuran City ID asynchronously if the location is in Indonesia
        if location_data["country"] == "Indonesia":
            self.stack.set_visible_child_name("loading")
            api.get_myquran_id_async(location_data, self.on_myquran_id_resolved)
        else:
            settings.set_setting("myquran_id", None)
            self.load_data()
            
    def on_myquran_id_resolved(self, myquran_id):
        print(f"MyQuran ID resolved: {myquran_id}")
        settings.set_setting("myquran_id", myquran_id)
        self.load_data()

    def on_refresh_clicked(self, widget_or_action=None, param=None):
        # Clear cache for current month to force refresh
        city = settings.get_setting("city")
        now = datetime.datetime.now()
        key = settings.get_cache_key(city, now.month, now.year)
        
        config = settings.load_settings()
        if "cache" in config and key in config["cache"]:
            config["cache"].pop(key)
            settings.save_settings(config)
            
        self.load_data()

    def on_preferences_clicked(self, action, param):
        dialog = PreferencesWindow(self)
        dialog.present()

    def on_about_clicked(self, action, param):
        lang = settings.get_setting("language", "id")
        about = Adw.AboutWindow(
            transient_for=self,
            application_name=i18n.get_string("app_title", lang),
            application_icon="alarm-symbolic",
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
