import unittest
import tempfile
import shutil
import os
import json
from unittest.mock import patch, MagicMock
from tests.test_geoclue import wait_for_glib
from prayer_time import settings, api


class TestSettingsAndApi(unittest.TestCase):
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

    def test_in_memory_caching_and_zero_repeated_disk_reads(self):
        # Create initial file first so load_settings reads from disk
        settings.save_settings(dict(settings.DEFAULT_SETTINGS))
        settings._settings_cache = None
        settings._settings_mtime = None

        with patch("prayer_time.settings.json.load", wraps=json.load) as mock_load:
            s1 = settings.load_settings()
            self.assertEqual(s1["city"], "Jakarta")
            self.assertEqual(mock_load.call_count, 1)

            # Subsequent get_setting calls MUST NOT call json.load again
            for _ in range(10):
                c = settings.get_setting("city")
                self.assertEqual(c, "Jakarta")
            self.assertEqual(mock_load.call_count, 1)

    def test_deep_copy_isolation_in_settings_cache(self):
        s1 = settings.load_settings()
        # Mutate nested dictionary in caller's copy
        s1["cache"]["test_key"] = "test_val"
        s1["location_history"].append({"city": "Hacked"})

        # Subsequent load_settings must remain completely unpolluted
        s2 = settings.load_settings()
        self.assertNotIn("test_key", s2["cache"])
        self.assertEqual(len(s2["location_history"]), 1)
        self.assertEqual(s2["location_history"][0]["city"], "Jakarta")

    def test_apply_location_selection_single_write(self):
        # Ensure initial settings file exists
        settings.save_settings(dict(settings.DEFAULT_SETTINGS))

        loc = {
            "city": "Semarang",
            "country": "Indonesia",
            "lat": -6.99,
            "lon": 110.42,
            "myquran_id": "1203"
        }

        with patch("prayer_time.settings.save_settings", wraps=settings.save_settings) as mock_save:
            settings.apply_location_selection(loc, auto_location=True)
            self.assertEqual(mock_save.call_count, 1)

        s = settings.load_settings()
        self.assertEqual(s["city"], "Semarang")
        self.assertEqual(s["latitude"], -6.99)
        self.assertTrue(s["auto_location"])
        self.assertEqual(s["myquran_id"], "1203")
        self.assertEqual(s["location_history"][0]["city"], "Semarang")
        self.assertEqual(s["cache"], {})

    def test_cache_key_standardization_and_eviction(self):
        key = settings.get_cache_key("Kota Bandung!", 10, 2026)
        self.assertEqual(key, "kotabandung_10_2026")

        # Set 6 caches to verify eviction limit of 5
        for i in range(6):
            settings.set_cached_timings(f"City{i}", 10, 2026, {"sample": i})

        s = settings.load_settings()
        self.assertLessEqual(len(s["cache"]), 5)
        self.assertIn("city5_10_2026", s["cache"])
        self.assertNotIn("city0_10_2026", s["cache"])

        # Test invalidate_cached_timings
        settings.invalidate_cached_timings("City5", 10, 2026)
        s_after = settings.load_settings()
        self.assertNotIn("city5_10_2026", s_after["cache"])

    @patch("prayer_time.api._get_session")
    def test_fetch_prayer_times_async_merges_myquran(self, mock_get_session):
        mock_session = MagicMock()

        # Mock 1: Aladhan response
        aladhan_resp = MagicMock()
        aladhan_resp.status_code = 200
        aladhan_resp.json.return_value = {
            "data": [{
                "date": {
                    "gregorian": {"date": "30-10-2026"},
                    "hijri": {"day": "18", "month": {"en": "Rabi' al-Thani"}}
                },
                "timings": {
                    "Fajr": "04:30", "Sunrise": "05:40", "Dhuhr": "11:50",
                    "Asr": "15:10", "Maghrib": "17:55", "Isha": "19:05"
                }
            }]
        }

        # Mock 2: MyQuran Kemenag response
        myquran_resp = MagicMock()
        myquran_resp.status_code = 200
        myquran_resp.json.return_value = {
            "status": True,
            "data": {
                "jadwal": [{
                    "date": "2026-10-30",
                    "subuh": "04:12",
                    "terbit": "05:28",
                    "dzuhur": "11:41",
                    "ashar": "14:55",
                    "maghrib": "17:48",
                    "isya": "18:59",
                    "imsak": "04:02"
                }]
            }
        }

        def fake_get(url, **kwargs):
            if "aladhan" in url:
                return aladhan_resp
            return myquran_resp

        mock_session.get.side_effect = fake_get
        mock_get_session.return_value = mock_session

        results = []

        def callback(data, error, req_id):
            results.append((data, error, req_id))

        api.fetch_prayer_times_async(-6.2, 106.8, 20, 10, 2026, "1301", callback, request_id=101)

        self.assertTrue(wait_for_glib(lambda: len(results) > 0))

        self.assertEqual(len(results), 1)
        data, err, req_id = results[0]
        self.assertIsNone(err)
        self.assertEqual(req_id, 101)
        self.assertEqual(len(data), 1)

        day_timings = data[0]["timings"]
        # Official Kemenag times must override Aladhan times
        self.assertEqual(day_timings["Fajr"], "04:12")
        self.assertEqual(day_timings["Dhuhr"], "11:41")
        self.assertEqual(day_timings["Asr"], "14:55")
        self.assertEqual(day_timings["Maghrib"], "17:48")
        self.assertEqual(day_timings["Isha"], "18:59")
        # Hijri calendar structure from Aladhan must remain intact
        self.assertEqual(data[0]["date"]["hijri"]["day"], "18")

    @patch("prayer_time.api._get_session")
    def test_get_myquran_id_async_url_quoted(self, mock_get_session):
        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "status": True,
            "data": [
                {"id": "1301", "lokasi": "KOTA JAKARTA PUSAT"}
            ]
        }
        mock_session.get.return_value = mock_resp
        mock_get_session.return_value = mock_session

        results = []
        loc_data = {"city": "Jakarta Pusat", "candidates": ["Jakarta Pusat"]}
        api.get_myquran_id_async(loc_data, lambda cid: results.append(cid))

        self.assertTrue(wait_for_glib(lambda: len(results) > 0))

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], "1301")


if __name__ == "__main__":
    unittest.main()


if __name__ == "__main__":
    unittest.main()
