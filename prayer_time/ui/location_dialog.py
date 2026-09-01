from gi.repository import Gtk, Adw, GLib
from prayer_time import api
from prayer_time import settings
from prayer_time import i18n

# Base class compatibility for Libadwaita
DialogBase = Adw.Dialog if hasattr(Adw, "Dialog") else Adw.Window


class LocationDialog(DialogBase):
    def __init__(self, parent_window, on_location_selected):
        if DialogBase == Adw.Window:
            super().__init__(transient_for=parent_window, modal=True)
            self.set_default_size(450, 420)
        else:
            super().__init__()
            self.set_content_width(450)
            self.set_content_height(420)

        self.parent_window = parent_window
        self.on_location_selected = on_location_selected

        self.search_timeout_id = None
        self.search_results = []

        lang = settings.get_setting("language", "id")
        self.set_title(i18n.get_string("loading_dialog_title", lang))

        # Main layout
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        vbox.add_css_class("dialog-content")

        # Search Entry Row
        self.search_entry = Adw.EntryRow()
        self.search_entry.set_title(i18n.get_string("search_entry_title", lang))
        self.search_entry.connect("changed", self.on_search_changed)

        # Preferences group for nice boxed styling
        pref_group = Adw.PreferencesGroup()
        pref_group.add(self.search_entry)
        vbox.append(pref_group)

        # Loader spinner
        self.spinner = Adw.Spinner()
        self.spinner.set_halign(Gtk.Align.CENTER)
        self.spinner.set_visible(False)
        vbox.append(self.spinner)

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

        # Ensure timeout source is removed when dialog is closed
        self.connect("unrealize", self.on_unrealize)

    def on_unrealize(self, widget):
        if self.search_timeout_id:
            GLib.source_remove(self.search_timeout_id)
            self.search_timeout_id = None

    def on_search_changed(self, entry):
        if self.search_timeout_id:
            GLib.source_remove(self.search_timeout_id)
            self.search_timeout_id = None

        query = entry.get_text().strip()
        if len(query) < 3:
            self.spinner.set_visible(False)
            self.clear_results()
            return

        # Schedule debounced search (400ms)
        self.search_timeout_id = GLib.timeout_add(400, self.do_search, query)

    def do_search(self, query):
        self.search_timeout_id = None
        self.spinner.set_visible(True)
        self.clear_results()
        api.search_location_async(query, self.on_search_results)
        return False

    def clear_results(self):
        self.search_results = []
        while True:
            row = self.results_list.get_row_at_index(0)
            if not row:
                break
            self.results_list.remove(row)

    def on_search_results(self, results, error):
        self.spinner.set_visible(False)
        lang = settings.get_setting("language", "id")

        if error:
            row = Adw.ActionRow()
            row.set_title(i18n.get_string("search_error", lang))
            row.set_subtitle(str(error))
            row.set_activatable(False)
            self.results_list.append(row)
            return

        if not results:
            row = Adw.ActionRow()
            row.set_title(i18n.get_string("search_not_found", lang))
            row.set_activatable(False)
            self.results_list.append(row)
            return

        self.search_results = results

        addresstype_map = {
            "en": {
                "city": "City", "district": "District", "village": "Village",
                "town": "Town", "suburb": "Suburb", "state": "State",
                "country": "Country", "municipality": "Municipality", "regency": "Regency"
            },
            "id": {
                "city": "Kota", "district": "Kecamatan", "village": "Kelurahan/Desa",
                "town": "Kota", "suburb": "Kelurahan/Desa", "state": "Provinsi",
                "country": "Negara", "municipality": "Kotamadya", "regency": "Kabupaten"
            }
        }
        current_map = addresstype_map.get(lang, addresstype_map["id"])

        for item in results:
            row = Adw.ActionRow()
            row.set_activatable(True)

            city_name = item.get("city", "Unknown")
            country_name = item.get("country", "")

            addr_type = item.get("addresstype", "")
            type_label = current_map.get(addr_type, addr_type.capitalize() if addr_type else "")

            suffix = f" ({type_label})" if type_label else ""
            title_text = f"{city_name}{suffix}, {country_name}" if country_name else f"{city_name}{suffix}"

            row.set_title(title_text)
            row.set_subtitle(item.get("display_name", ""))
            self.results_list.append(row)

    def on_row_activated(self, list_box, row):
        index = row.get_index()
        if 0 <= index < len(self.search_results):
            selected_data = self.search_results[index]
            self.on_location_selected(selected_data)
            if hasattr(self, "close"):
                self.close()
            elif hasattr(self, "destroy"):
                self.destroy()
