import unittest
import tempfile
import shutil
import os
from unittest.mock import MagicMock, patch
from prayer_time import settings, geoclue, api


class TestGeoclue(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.orig_config_dir = settings.CONFIG_DIR
        self.orig_config_file = settings.CONFIG_FILE
        settings.CONFIG_DIR = self.test_dir
        settings.CONFIG_FILE = os.path.join(self.test_dir, 'settings.json')

    def tearDown(self):
        settings.CONFIG_DIR = self.orig_config_dir
        settings.CONFIG_FILE = self.orig_config_file
        shutil.rmtree(self.test_dir, ignore_errors=True)

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

        svc.start_monitoring(callback)

        # First coordinate update should notify
        svc._check_and_notify(-6.2088, 106.8456)
        self.assertEqual(len(notified), 1)
        self.assertEqual(notified[0], (-6.2088, 106.8456))

        # Small movement (~100m) should not notify
        svc._check_and_notify(-6.2090, 106.8458)
        self.assertEqual(len(notified), 1)

        # Significant movement (> 5km, ~0.05 deg) should notify
        svc._check_and_notify(-6.3000, 106.8456)
        self.assertEqual(len(notified), 2)
        self.assertEqual(notified[1], (-6.3000, 106.8456))

        svc.stop_monitoring()
        self.assertIsNone(svc._on_location_changed_callback)

    @patch("prayer_time.api.requests.get")
    def test_reverse_geocode_async(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "place_id": 12345,
            "lat": "-6.1000",
            "lon": "106.1600",
            "display_name": "Serang, Banten, Indonesia",
            "addresstype": "city",
            "address": {
                "city": "Serang",
                "state": "Banten",
                "country": "Indonesia"
            }
        }
        mock_get.return_value = mock_response

        result_container = []

        def cb(loc_data, err):
            result_container.append((loc_data, err))

        # Run reverse geocode
        api.reverse_geocode_async(-6.1000, 106.1600, cb)

        # Wait for thread and process GLib idle events
        from gi.repository import GLib
        import time
        for _ in range(50):
            while GLib.MainContext.default().pending():
                GLib.MainContext.default().iteration(False)
            if result_container:
                break
            time.sleep(0.05)

        self.assertEqual(len(result_container), 1)
        data, err = result_container[0]
        self.assertIsNone(err)
        self.assertIsNotNone(data)
        self.assertEqual(data["city"], "Serang")
        self.assertEqual(data["country"], "Indonesia")
        self.assertEqual(data["lat"], -6.1000)
        self.assertEqual(data["lon"], 106.1600)
        self.assertIn("Serang", data["candidates"])

    @patch("prayer_time.api.requests.get")
    def test_reverse_geocode_async_error(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        result_container = []

        def cb(loc_data, err):
            result_container.append((loc_data, err))

        api.reverse_geocode_async(-6.1000, 106.1600, cb)

        from gi.repository import GLib
        import time
        for _ in range(50):
            while GLib.MainContext.default().pending():
                GLib.MainContext.default().iteration(False)
            if result_container:
                break
            time.sleep(0.05)

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
