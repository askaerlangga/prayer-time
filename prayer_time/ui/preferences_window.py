from gi.repository import Gtk, Adw
from prayer_time import settings
from prayer_time import i18n


class PreferencesWindow(Adw.PreferencesWindow):
    def __init__(self, parent):
        super().__init__(transient_for=parent)
        self.parent_window = parent
        self.set_default_size(380, 480)
        self.set_search_enabled(False)
        
        page = Adw.PreferencesPage()
        self.add(page)
        
        # General Preferences Group
        self.general_group = Adw.PreferencesGroup()
        page.add(self.general_group)
        
        # Autostart Switch
        self.autostart_row = Adw.SwitchRow()
        self.autostart_row.set_active(settings.get_setting("autostart", False))
        self.autostart_row.connect("notify::active", self.on_autostart_changed)
        self.general_group.add(self.autostart_row)
        
        # Audio Alert Switch
        self.audio_row = Adw.SwitchRow()
        self.audio_row.set_active(settings.get_setting("enable_audio", True))
        self.audio_row.connect("notify::active", self.on_audio_changed)
        self.general_group.add(self.audio_row)
        
        # Language Preferences Group
        self.lang_group = Adw.PreferencesGroup()
        page.add(self.lang_group)
        
        self.lang_row = Adw.ComboRow()
        lang_model = Gtk.StringList.new(["Bahasa Indonesia", "English"])
        self.lang_row.set_model(lang_model)
        current_lang = settings.get_setting("language", "id")
        self.lang_row.set_selected(0 if current_lang == "id" else 1)
        self.lang_row.connect("notify::selected", self.on_lang_changed)
        self.lang_group.add(self.lang_row)
        
        # Iqamah Preferences Group
        self.iqamah_group = Adw.PreferencesGroup()
        page.add(self.iqamah_group)
        
        self.prayers = [
            ("Fajr", "fajr_iqamah", 15),
            ("Dhuhr", "dhuhr_iqamah", 10),
            ("Asr", "asr_iqamah", 10),
            ("Maghrib", "maghrib_iqamah", 10),
            ("Isha", "isha_iqamah", 10),
        ]
        
        self.iqamah_rows = {}
        self.iqamah_key_to_api_name = {}
        
        for api_name, key, default in self.prayers:
            row = Adw.ActionRow()
            self.iqamah_rows[key] = row
            self.iqamah_key_to_api_name[key] = api_name
            val = settings.get_setting(key, default)
            adj = Gtk.Adjustment(value=val, lower=0, upper=60, step_increment=1)
            spin = Gtk.SpinButton(adjustment=adj, climb_rate=1, digits=0)
            spin.set_valign(Gtk.Align.CENTER)
            spin.connect("value-changed", self.on_iqamah_changed, key)
            row.add_suffix(spin)
            self.iqamah_group.add(row)
            
        self.update_preferences_translations()
            
    def on_autostart_changed(self, row, pspec):
        settings.set_setting("autostart", row.get_active())
        
    def on_audio_changed(self, row, pspec):
        settings.set_setting("enable_audio", row.get_active())
        
    def on_iqamah_changed(self, spin, key):
        settings.set_setting(key, int(spin.get_value()))
        
    def on_lang_changed(self, combo_row, pspec):
        selected = combo_row.get_selected()
        new_lang = "id" if selected == 0 else "en"
        if settings.get_setting("language", "id") != new_lang:
            settings.set_setting("language", new_lang)
            self.update_preferences_translations()
            if self.parent_window:
                self.parent_window.update_translations()
                
    def update_preferences_translations(self):
        lang = settings.get_setting("language", "id")
        self.set_title(i18n.get_string("preferences", lang))
        self.general_group.set_title(i18n.get_string("pref_general", lang))
        self.autostart_row.set_title(i18n.get_string("pref_autostart", lang))
        self.autostart_row.set_subtitle(i18n.get_string("pref_autostart_sub", lang))
        self.audio_row.set_title(i18n.get_string("pref_audio", lang))
        self.audio_row.set_subtitle(i18n.get_string("pref_audio_sub", lang))
        self.iqamah_group.set_title(i18n.get_string("pref_iqamah_group", lang))
        self.lang_group.set_title(i18n.get_string("pref_lang", lang))
        self.lang_row.set_title(i18n.get_string("pref_lang", lang))
        self.lang_row.set_subtitle(i18n.get_string("pref_lang_sub", lang))
        
        for key, row in self.iqamah_rows.items():
            api_name = self.iqamah_key_to_api_name[key]
            row.set_title(i18n.get_prayer_name(api_name, lang))
