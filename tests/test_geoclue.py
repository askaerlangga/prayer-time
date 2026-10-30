import unittest
import tempfile
import shutil
import os
import time
from unittest.mock import MagicMock, patch
from gi.repository import GLib
from prayer_time import settings, geoclue, api


def wait_for_glib(predicate, timeout_iters=50, sleep_sec=0.02):
    """Processes pending GLib events until predicate() returns True or timeout is reached."""
    for _ in range(timeout_iters):
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        if predicate():
            return True
        time.sleep(sleep_sec)
    return predicate()


class TestGeoclue(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.orig_config_dir = settings.CONFIG_DIR
        self.orig_config_file = settings.CONFIG_FILE
        settings.CONFIG_DIR = self.test_dir
        settings.CONFIG_FILE = os.path.join(self.test_dir, 'settings.json')
        settings._settings_cache = None
        settings._settings_mtime = None

    def tearDown(self):
        settings.CONFIG_DIR = self.orig_config_dir
        settings.CONFIG_FILE = self.orig_config_file
        settings._settings_cache = None
        settings._settings_mtime = None
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_haversine_distance_calculation(self):
        # 1. Equator test: ~111 km per degree latitude
        d1 = geoclue._haversine_km(0.0, 100.0, 1.0, 100.0)
        self.assertAlmostEqual(d1, 111.19, delta=0.5)

        # 2. High latitude test (London ~51.5°N, 1 degree longitude is ~69 km, not 111 km)
        d2 = geoclue._haversine_km(51.5074, 0.0, 51.5074, 1.0)
        self.assertAlmostEqual(d2, 69.2, delta=1.0)

        # 3. Small movement (<5 km)
        d3 = geoclue._haversine_km(-6.2088, 106.8456, -6.2100, 106.8460)
        self.assertLess(d3, 0.2)

    def test_default_auto_location_setting(self):
        s = settings.load_settings()
        self.assertIn("auto_location", s)
        self.assertFalse(s["auto_location"])
        self.assertFalse(settings.get_setting("auto_location"))

        settings.set_setting("auto_location", True)
        self.assertTrue(settings.get_setting("auto_location"))

    def test_geoclue_available_check(self):
        # On this system, geoclue should return a boolean
        avail = geoclue.is_geoclue_available()
        self.assertIsInstance(avail, bool)

    def test_geoclue_service_singleton(self):
        svc1 = geoclue.GeoclueService.get_default()
        svc2 = geoclue.GeoclueService.get_default()
        self.assertIs(svc1, svc2)

    def test_geoclue_distance_check(self):
        svc = geoclue.GeoclueService()
        notified = []

        def callback(lat, lon):
            notified.append((lat, lon))

        svc._on_location_changed_callback = callback
        svc._last_coords = None

        # First coordinate update should notify
        svc._check_and_notify(-6.2088, 106.8456)
        self.assertEqual(len(notified), 1)
        self.assertEqual(notified[0], (-6.2088, 106.8456))

        # Small movement (~100m) should not notify
        svc._check_and_notify(-6.2090, 106.8458)
        self.assertEqual(len(notified), 1)

        # Significant movement (> 5km) should notify
        svc._check_and_notify(-6.3000, 106.8456)
        self.assertEqual(len(notified), 2)
        self.assertEqual(notified[1], (-6.3000, 106.8456))

        svc.stop_monitoring()
        self.assertIsNone(svc._on_location_changed_callback)

    @patch("prayer_time.api._get_session")
    def test_reverse_geocode_async(self, mock_get_session):
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        # Simulates a reverse geocode on a building/street POI
        mock_response.json.return_value = {
            "place_id": 12345,
            "lat": "-6.1005",
            "lon": "106.1605",
            "name": "Kantor Walikota",
            "display_name": "Kantor Walikota, Jalan Sudirman, Serang, Banten, Indonesia",
            "addresstype": "building",
            "address": {
                "building": "Kantor Walikota",
                "road": "Jalan Sudirman",
                "city": "Serang",
                "state": "Banten",
                "country": "Indonesia"
            }
        }
        mock_session.get.return_value = mock_response
        mock_get_session.return_value = mock_session

        result_container = []

        def cb(loc_data, err):
            result_container.append((loc_data, err))

        # Run reverse geocode with specific GPS coords
        api.reverse_geocode_async(-6.1000, 106.1600, cb)

        self.assertTrue(wait_for_glib(lambda: len(result_container) > 0))

        self.assertEqual(len(result_container), 1)
        data, err = result_container[0]
        self.assertIsNone(err)
        self.assertIsNotNone(data)
        # Administrative city must be prioritized for reverse geocode, not building name
        self.assertEqual(data["city"], "Serang")
        self.assertEqual(data["country"], "Indonesia")
        # GPS coordinates must be preserved exactly as given
        self.assertEqual(data["lat"], -6.1000)
        self.assertEqual(data["lon"], 106.1600)
        self.assertIn("Serang", data["candidates"])

    @patch("prayer_time.api._get_session")
    def test_reverse_geocode_async_error(self, mock_get_session):
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_session.get.return_value = mock_response
        mock_get_session.return_value = mock_session

        result_container = []

        def cb(loc_data, err):
            result_container.append((loc_data, err))

        api.reverse_geocode_async(-6.1000, 106.1600, cb)

        self.assertTrue(wait_for_glib(lambda: len(result_container) > 0))

        self.assertEqual(len(result_container), 1)
        data, err = result_container[0]
        self.assertIsNone(data)
        self.assertIsNotNone(err)
        self.assertIn("500", err)

    def test_geoclue_service_unavailable(self):
        svc = geoclue.GeoclueService()
        result_container = []

        with patch("prayer_time.geoclue.GEOCLUE_AVAILABLE", False):
            svc.get_location_async(lambda lat, lon, err: result_container.append((lat, lon, err)))
            self.assertEqual(len(result_container), 1)
            self.assertIsNone(result_container[0][0])
            self.assertIn("not available", result_container[0][2])
