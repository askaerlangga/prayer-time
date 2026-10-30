from gi.repository import Gtk, Adw, GLib
from prayer_time import api
from prayer_time import settings
from prayer_time import i18n
from prayer_time import geoclue

# Base class compatibility for Libadwaita
DialogBase = Adw.Dialog if hasattr(Adw, "Dialog") else Adw.Window

ADDRESSTYPE_MAP = {
    "en": {
        "city": "City", "district": "District", "village": "Village",
        "town": "Town", "suburb": "Suburb", "state": "State",
        "country": "Country", "municipality": "Municipality", "regency": "Regency",
        "city_district": "City District", "railway": "Railway Station", "station": "Station"
    },
    "id": {
        "city": "Kota", "district": "Kecamatan", "village": "Kelurahan/Desa",
        "town": "Kota", "suburb": "Kecamatan", "state": "Provinsi",
        "country": "Negara", "municipality": "Kecamatan", "regency": "Kabupaten",
        "city_district": "Kota Administrasi", "railway": "Stasiun Kereta", "station": "Stasiun"
    }
}


class LocationDialog(DialogBase):
    def __init__(self, parent_window, on_location_selected):
        if DialogBase == Adw.Window:
            super().__init__(transient_for=parent_window, modal=True)
            self.set_default_size(450, 450)
        else:
            super().__init__()
            self.set_content_width(450)
            self.set_content_height(450)

        self.parent_window = parent_window
        self.on_location_selected = on_location_selected

        self.search_timeout_id = None
        self.displayed_items = []
        self.is_history_mode = True
        self._deleting = False

        lang = settings.get_setting("language", "id")
        self.set_title(i18n.get_string("loading_dialog_title", lang))

        # Main layout
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vbox.add_css_class("dialog-content")

        # Search Entry Row
        self.search_entry = Adw.EntryRow()
        self.search_entry.set_title(i18n.get_string("search_entry_title", lang))
        self.search_entry.connect("changed", self.on_search_changed)

        # Geoclue Use Current Location Row
        self.current_loc_row = Adw.ActionRow()
        self.current_loc_row.set_icon_name("find-location-symbolic")
        self.current_loc_row.set_title(i18n.get_string("use_current_location", lang))
        self.current_loc_row.set_subtitle(i18n.get_string("use_current_location_sub", lang))
        self.current_loc_row.set_activatable(True)
        self.current_loc_row.connect("activated", self.on_use_current_location_activated)

        self.current_loc_spinner = Adw.Spinner()
        self.current_loc_spinner.set_visible(False)
        self.current_loc_row.add_suffix(self.current_loc_spinner)

        if not geoclue.is_geoclue_available():
            self.current_loc_row.set_sensitive(False)
            self.current_loc_row.set_subtitle(i18n.get_string("geoclue_not_available", lang))

        # Preferences group for nice boxed styling
        pref_group = Adw.PreferencesGroup()
        pref_group.add(self.search_entry)
        pref_group.add(self.current_loc_row)
        vbox.append(pref_group)

        # Loader spinner
        self.spinner = Adw.Spinner()
        self.spinner.set_halign(Gtk.Align.CENTER)
        self.spinner.set_visible(False)
        vbox.append(self.spinner)

        # Section header bar (Title + Clear button)
        self.header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.header_box.set_margin_start(4)
        self.header_box.set_margin_end(4)

        self.section_label = Gtk.Label()
        self.section_label.add_css_class("heading")
        self.section_label.set_halign(Gtk.Align.START)
        self.section_label.set_hexpand(True)

        self.clear_btn = Gtk.Button()
        self.clear_btn.add_css_class("flat")
        self.clear_btn.add_css_class("caption")
        self.clear_btn.connect("clicked", self.on_clear_all_clicked)

        self.header_box.append(self.section_label)
        self.header_box.append(self.clear_btn)
        vbox.append(self.header_box)

        # Results container
        self.results_list = Gtk.ListBox()
        self.results_list.add_css_class("boxed-list")
        self.results_list.set_activate_on_single_click(True)
        self.results_list.connect("row-activated", self.on_row_activated)

        # Scroll area for results
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_child(self.results_list)
        vbox.append(scrolled)

        if DialogBase == Adw.Window:
            header = Adw.HeaderBar()
            outer_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            outer_box.append(header)
            outer_box.append(vbox)
            self.set_content(outer_box)
        else:
            self.set_child(vbox)

        # Initial display: show recent locations
        self.show_history()

        # Ensure timeout source is removed when dialog is closed
        self.connect("unrealize", self.on_unrealize)

    def on_unrealize(self, widget):
        if self.search_timeout_id:
            GLib.source_remove(self.search_timeout_id)
            self.search_timeout_id = None

    def clear_results(self):
        self.displayed_items = []
        while True:
            row = self.results_list.get_row_at_index(0)
            if not row:
                break
            self.results_list.remove(row)

    def show_history(self, filter_query=""):
        self.is_history_mode = True
        self.clear_results()
        lang = settings.get_setting("language", "id")

        self.section_label.set_label(i18n.get_string("recent_locations", lang))

        all_history = settings.get_location_history()

        if filter_query:
            q = filter_query.lower()
            history = [
                item for item in all_history
                if q in item.get("city", "").lower() or q in item.get("display_name", "").lower()
            ]
        else:
            history = all_history

        self.displayed_items = list(history)

        if all_history and not filter_query:
            self.clear_btn.set_label(i18n.get_string("clear_history", lang))
            self.clear_btn.set_tooltip_text(i18n.get_string("clear_history_tooltip", lang))
            self.clear_btn.set_visible(True)
        else:
            self.clear_btn.set_visible(False)

        if not history:
            row = Adw.ActionRow()
            row.set_icon_name("document-open-recent-symbolic")
            row.set_title(i18n.get_string("no_history", lang))
            row.set_subtitle(i18n.get_string("no_history_sub", lang))
            row.set_activatable(False)
            self.results_list.append(row)
            return

        current_map = ADDRESSTYPE_MAP.get(lang, ADDRESSTYPE_MAP["id"])

        for item in history:
            row = Adw.ActionRow()
            row.set_activatable(True)
            row.set_icon_name("document-open-recent-symbolic")

            city_name = item.get("city", "Unknown")
            country_name = item.get("country", "")
            addr_type = item.get("addresstype", "")
            type_label = current_map.get(addr_type, addr_type.capitalize() if addr_type else "")

            suffix = f" ({type_label})" if type_label else ""
            title_text = f"{city_name}{suffix}, {country_name}" if country_name else f"{city_name}{suffix}"

            row.set_title(title_text)
            row.set_subtitle(item.get("display_name", ""))

            del_btn = Gtk.Button(icon_name="edit-delete-symbolic")
            del_btn.add_css_class("flat")
            del_btn.add_css_class("circular")
            del_btn.set_valign(Gtk.Align.CENTER)
            del_btn.set_tooltip_text(i18n.get_string("delete_history_item_tooltip", lang))

            original_idx = all_history.index(item) if item in all_history else 0
            del_btn.connect("clicked", self.on_delete_item_clicked, original_idx)
            row.add_suffix(del_btn)

            self.results_list.append(row)

    def on_delete_item_clicked(self, btn, index):
        self._deleting = True
        settings.remove_location_history(index)
        query = self.search_entry.get_text().strip()
        self.show_history(filter_query=query if len(query) < 3 else "")

    def on_clear_all_clicked(self, btn):
        settings.clear_location_history()
        self.show_history()

    def on_search_changed(self, entry):
        if self.search_timeout_id:
            GLib.source_remove(self.search_timeout_id)
            self.search_timeout_id = None

        query = entry.get_text().strip()
        if not query:
            self.spinner.set_visible(False)
            self.show_history()
            return

        if len(query) < 3:
            self.spinner.set_visible(False)
            self.show_history(filter_query=query)
            return

        # Schedule debounced search (400ms)
        self.search_timeout_id = GLib.timeout_add(400, self.do_search, query)

    def do_search(self, query):
        self.search_timeout_id = None
        self.is_history_mode = False
        self.spinner.set_visible(True)
        self.clear_results()
        lang = settings.get_setting("language", "id")
        self.section_label.set_label(i18n.get_string("search_results", lang))
        self.clear_btn.set_visible(False)
        api.search_location_async(query, self.on_search_results)
        return False

    def on_search_results(self, results, error):
        self.spinner.set_visible(False)
        if self.is_history_mode:
            return

        lang = settings.get_setting("language", "id")

        if error:
            self.displayed_items = []
            row = Adw.ActionRow()
            row.set_icon_name("dialog-error-symbolic")
            row.set_title(i18n.get_string("search_error", lang))
            row.set_subtitle(str(error))
            row.set_activatable(False)
            self.results_list.append(row)
            return

        if not results:
            self.displayed_items = []
            row = Adw.ActionRow()
            row.set_icon_name("system-search-symbolic")
            row.set_title(i18n.get_string("search_not_found", lang))
            row.set_activatable(False)
            self.results_list.append(row)
            return

        self.displayed_items = list(results)
        current_map = ADDRESSTYPE_MAP.get(lang, ADDRESSTYPE_MAP["id"])

        for item in results:
            row = Adw.ActionRow()
            row.set_activatable(True)
            row.set_icon_name("mark-location-symbolic")

            city_name = item.get("city", "Unknown")
            country_name = item.get("country", "")

            addr_type = item.get("addresstype", "")
            type_label = current_map.get(addr_type, addr_type.capitalize() if addr_type else "")

            suffix = f" ({type_label})" if type_label else ""
            title_text = f"{city_name}{suffix}, {country_name}" if country_name else f"{city_name}{suffix}"

            row.set_title(title_text)
            row.set_subtitle(item.get("display_name", ""))
            self.results_list.append(row)

    def on_use_current_location_activated(self, row):
        if not geoclue.is_geoclue_available():
            return

        self.current_loc_row.set_sensitive(False)
        self.current_loc_spinner.set_visible(True)
        lang = settings.get_setting("language", "id")
        self.current_loc_row.set_subtitle(i18n.get_string("detecting_location", lang))

        geoclue.GeoclueService.get_default().get_location_async(self.on_current_coordinates_received)

    def on_current_coordinates_received(self, lat, lon, error):
        lang = settings.get_setting("language", "id")
        if error or lat is None or lon is None:
            self.current_loc_spinner.set_visible(False)
            self.current_loc_row.set_sensitive(True)
            self.current_loc_row.set_subtitle(i18n.get_string("location_detect_failed", lang).format(error or "Error"))
            return

        api.reverse_geocode_async(lat, lon, self.on_current_address_resolved)

    def on_current_address_resolved(self, location_data, error):
        self.current_loc_spinner.set_visible(False)
        self.current_loc_row.set_sensitive(True)
        lang = settings.get_setting("language", "id")
        self.current_loc_row.set_subtitle(i18n.get_string("use_current_location_sub", lang))

        if error or not location_data:
            self.current_loc_row.set_subtitle(i18n.get_string("location_detect_failed", lang).format(error or "Error"))
            return

        location_data["is_geoclue"] = True
        self.on_location_selected(location_data)
        if hasattr(self, "close"):
            self.close()
        elif hasattr(self, "destroy"):
            self.destroy()

    def on_row_activated(self, list_box, row):
        if self._deleting:
            self._deleting = False
            return

        index = row.get_index()
        if 0 <= index < len(self.displayed_items):
            selected_data = dict(self.displayed_items[index])
            selected_data["is_geoclue"] = False
            self.on_location_selected(selected_data)
            if hasattr(self, "close"):
                self.close()
            elif hasattr(self, "destroy"):
                self.destroy()
