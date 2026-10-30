import math
from typing import Callable, Optional, Tuple

try:
    import gi
    gi.require_version("Geoclue", "2.0")
    from gi.repository import Geoclue, GLib
    GEOCLUE_AVAILABLE = True
except (ValueError, ImportError):
    GEOCLUE_AVAILABLE = False


def is_geoclue_available() -> bool:
    """Returns True if Geoclue 2.0 GObject introspection is available on the system."""
    return GEOCLUE_AVAILABLE


class GeoclueService:
    """
    Manages Geoclue 2.0 location discovery.
    Supports one-shot location queries as well as ongoing location monitoring.
    """
    _instance: Optional["GeoclueService"] = None

    def __init__(self, desktop_id: str = "com.github.aska.PrayerTime"):
        self.desktop_id = desktop_id
        self.simple: Optional[Geoclue.Simple] = None
        self.is_locating = False
        self._on_location_changed_callback: Optional[Callable[[float, float], None]] = None
        self._last_coords: Optional[Tuple[float, float]] = None
        self._notify_handler_id = None

    @classmethod
    def get_default(cls) -> "GeoclueService":
        if cls._instance is None:
            cls._instance = GeoclueService()
        return cls._instance

    def get_location_async(self, callback: Callable[[Optional[float], Optional[float], Optional[str]], None]) -> None:
        """
        Fetches the current coordinates asynchronously.
        Callback signature: callback(latitude, longitude, error_message)
        """
        if not GEOCLUE_AVAILABLE:
            callback(None, None, "Geoclue 2.0 is not available on this system.")
            return

        def on_simple_ready(source, result):
            self.is_locating = False
            try:
                simple = Geoclue.Simple.new_finish(result)
                self.simple = simple
                loc = simple.get_location()
                if loc:
                    lat = float(loc.props.latitude)
                    lon = float(loc.props.longitude)
                    self._last_coords = (lat, lon)
                    callback(lat, lon, None)
                    return

                # If location not immediately available, wait for notify::location
                state = {"handler_id": None, "timeout_id": None, "done": False}

                def cleanup():
                    if state["handler_id"] and simple:
                        try:
                            simple.disconnect(state["handler_id"])
                        except Exception:
                            pass
                        state["handler_id"] = None
                    if state["timeout_id"]:
                        GLib.source_remove(state["timeout_id"])
                        state["timeout_id"] = None

                def on_notify(obj, pspec):
                    if state["done"]:
                        return
                    new_loc = simple.get_location()
                    if new_loc:
                        state["done"] = True
                        cleanup()
                        lat = float(new_loc.props.latitude)
                        lon = float(new_loc.props.longitude)
                        self._last_coords = (lat, lon)
                        callback(lat, lon, None)

                def on_timeout():
                    if state["done"]:
                        return False
                    state["done"] = True
                    cleanup()
                    callback(None, None, "Geoclue location request timed out.")
                    return False

                state["handler_id"] = simple.connect("notify::location", on_notify)
                state["timeout_id"] = GLib.timeout_add_seconds(10, on_timeout)

            except Exception as e:
                callback(None, None, str(e))

        self.is_locating = True
        try:
            Geoclue.Simple.new(
                self.desktop_id,
                Geoclue.AccuracyLevel.EXACT,
                None,
                on_simple_ready
            )
        except Exception as e:
            self.is_locating = False
            callback(None, None, str(e))

    def start_monitoring(self, on_location_changed: Callable[[float, float], None]) -> None:
        """
        Starts monitoring location changes with Geoclue.
        Invokes on_location_changed(lat, lon) whenever location shifts noticeably (> 5km).
        """
        if not GEOCLUE_AVAILABLE:
            return

        self._on_location_changed_callback = on_location_changed

        if self.simple:
            self._connect_notify()
            return

        def on_simple_ready(source, result):
            try:
                self.simple = Geoclue.Simple.new_finish(result)
                self._connect_notify()
                loc = self.simple.get_location()
                if loc:
                    self._check_and_notify(float(loc.props.latitude), float(loc.props.longitude))
            except Exception as e:
                print(f"[PrayerTime] Geoclue monitoring error: {e}")

        try:
            Geoclue.Simple.new(
                self.desktop_id,
                Geoclue.AccuracyLevel.EXACT,
                None,
                on_simple_ready
            )
        except Exception as e:
            print(f"[PrayerTime] Geoclue init error: {e}")

    def _connect_notify(self):
        if self.simple and not self._notify_handler_id:
            try:
                client = self.simple.get_client()
                client.props.distance_threshold = 5000
            except Exception:
                pass
            self._notify_handler_id = self.simple.connect("notify::location", self._on_notify_location)

    def _on_notify_location(self, simple, pspec):
        loc = simple.get_location()
        if loc:
            self._check_and_notify(float(loc.props.latitude), float(loc.props.longitude))

    def _check_and_notify(self, lat: float, lon: float):
        if self._last_coords:
            prev_lat, prev_lon = self._last_coords
            dist_deg = math.hypot(lat - prev_lat, lon - prev_lon)
            if dist_deg < 0.045:  # ~5 km
                return

        self._last_coords = (lat, lon)
        if self._on_location_changed_callback:
            self._on_location_changed_callback(lat, lon)

    def stop_monitoring(self):
        if self.simple and self._notify_handler_id:
            try:
                self.simple.disconnect(self._notify_handler_id)
            except Exception:
                pass
            self._notify_handler_id = None
        self._on_location_changed_callback = None
