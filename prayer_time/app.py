import os
import subprocess
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gdk, Gio
from prayer_time.ui.window import PrayerWindow

class PrayerApplication(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id="com.github.aska.PrayerTime",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS
        )
        self.tray_process = None

    def do_startup(self):
        Adw.Application.do_startup(self)

        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)

        # Register app icon so it's available to AboutWindow and the shell
        icon_theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
        icon_theme.add_search_path(os.path.join(project_root, "data", "icons"))

        # Load CSS stylesheet relative to project root
        css_provider = Gtk.CssProvider()
        css_path = os.path.join(project_root, "data", "style.css")
        
        if os.path.exists(css_path):
            try:
                css_provider.load_from_path(css_path)
                Gtk.StyleContext.add_provider_for_display(
                    Gdk.Display.get_default(),
                    css_provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                )
                print("Loaded custom CSS successfully")
            except Exception as e:
                print(f"Error loading CSS: {e}")
        else:
            print(f"CSS file not found at: {css_path}")
            
        # Launch tray helper process (with parent PID to allow termination signaling)
        try:
            helper_path = os.path.join(script_dir, "service", "tray_helper.py")
            if os.path.exists(helper_path):
                self.tray_process = subprocess.Popen(
                    ["python3", helper_path, str(os.getpid())],
                    start_new_session=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                print("Launched system tray helper")
        except Exception as e:
            print(f"Failed to launch tray helper: {e}")

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = PrayerWindow(application=self)
        win.present()

    def do_shutdown(self):
        # Terminate tray helper process cleanly
        if self.tray_process:
            try:
                self.tray_process.terminate()
                self.tray_process.wait(timeout=1)
                print("Terminated system tray helper")
            except Exception as e:
                print(f"Error terminating tray helper: {e}")
        Adw.Application.do_shutdown(self)

