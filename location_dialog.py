from gi.repository import Gtk, Adw, GObject, GLib
import api
import settings
import i18n

class LocationDialog(Adw.Dialog):
    def __init__(self, parent_window, on_location_selected):
        super().__init__()
        self.parent_window = parent_window
        self.on_location_selected = on_location_selected
        
        self.search_timeout_id = None
        self.search_results = []  # Index-based list to map Gtk.ListBox row indices safely
        
        lang = settings.get_setting("language", "id")
        self.set_title(i18n.get_string("loading_dialog_title", lang))
        self.set_content_width(450)
        self.set_content_height(400)
        
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
        self.results_list.set_activate_on_single_click(False)  # Require double-click to activate
        self.results_list.connect("row-activated", self.on_row_activated)
        
        # Scroll area for results
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_child(self.results_list)
        vbox.append(scrolled)
        
        self.set_child(vbox)

    def on_search_changed(self, entry):
        # Cancel any pending search timeout to debounce requests
        if self.search_timeout_id:
            GLib.source_remove(self.search_timeout_id)
            self.search_timeout_id = None
            
        query = entry.get_text().strip()
        
        # Don't trigger search for empty or extremely short queries
        if len(query) < 3:
            self.spinner.set_visible(False)
            self.clear_results()
            return
            
        # Schedule the search 500ms after the user stops typing
        self.search_timeout_id = GLib.timeout_add(500, self.do_search, query)

    def do_search(self, query):
        self.search_timeout_id = None
        self.spinner.set_visible(True)
        self.clear_results()
        api.search_location_async(query, self.on_search_results)
        return False  # Return False so the timeout runs only once

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
        
        if lang == "en":
            addresstype_map = {
                "city": "City",
                "district": "District",
                "village": "Village",
                "town": "Town",
                "suburb": "Suburb",
                "state": "State",
                "country": "Country",
                "municipality": "Municipality",
                "regency": "Regency"
            }
        else:
            addresstype_map = {
                "city": "Kota",
                "district": "Kecamatan",
                "village": "Kelurahan/Desa",
                "town": "Kota",
                "suburb": "Kelurahan/Desa",
                "state": "Provinsi",
                "country": "Negara",
                "municipality": "Kotamadya",
                "regency": "Kabupaten"
            }
        
        for item in results:
            row = Adw.ActionRow()
            row.set_activatable(True)  # Make sure the row can be activated via double click
            
            city_name = item.get("city", "Tidak Diketahui" if lang == "id" else "Unknown")
            country_name = item.get("country", "")
            
            # Extract and translate addresstype
            addr_type = item.get("addresstype", "")
            type_label = addresstype_map.get(addr_type, addr_type.capitalize() if addr_type else "")
            
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
            self.close()
