import os
import sys
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('Notify', '0.7')
from gi.repository import Gtk, Adw, Gdk, Gio, GLib, Notify
from prayer_time.ui.window import PrayerWindow


class PrayerApplication(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id="com.github.aska.PrayerTime",
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE
        )
        self.add_main_option(
            "background",
            0,
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            "Start in background without presenting window",
            None
        )

    def do_command_line(self, command_line):
        options = command_line.get_options_dict()
        if options.contains("background"):
            self.hold()
            self._ensure_window()
            return 0
        self.activate()
        return 0

    def _ensure_window(self):
        windows = self.get_windows()
        if not windows:
            return PrayerWindow(application=self)
        return windows[0]

    def do_startup(self):
        Adw.Application.do_startup(self)

        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)

        # Register app icon for About dialog and system shell
        icon_theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
        icon_path = os.path.join(project_root, "data", "icons")
        if os.path.exists(icon_path):
            icon_theme.add_search_path(icon_path)

        # Load custom CSS stylesheet
        css_path = os.path.join(project_root, "data", "style.css")
        if os.path.exists(css_path):
            try:
                css_provider = Gtk.CssProvider()
                css_provider.load_from_path(css_path)
                Gtk.StyleContext.add_provider_for_display(
                    Gdk.Display.get_default(),
                    css_provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                )
            except Exception as e:
                print(f"[PrayerTime] Error loading CSS stylesheet: {e}")

        # Initialize desktop notification system
        try:
            Notify.init("Prayer Times")
        except Exception as e:
            print(f"[PrayerTime] Warning: Failed to initialize libnotify: {e}")

    def do_activate(self):
        win = self._ensure_window()
        win.present()

    def do_shutdown(self):
        if Notify.is_initted():
            Notify.uninit()
        Adw.Application.do_shutdown(self)
