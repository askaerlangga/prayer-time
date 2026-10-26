import unittest
import tempfile
import shutil
import os
from prayer_time import settings, i18n


class TestLocationHistory(unittest.TestCase):
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

    def test_initial_history(self):
        history = settings.get_location_history()
        self.assertIsInstance(history, list)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['city'], 'Jakarta')

    def test_add_and_deduplicate(self):
        settings.add_location_history({
            'city': 'Bandung',
            'country': 'Indonesia',
            'lat': -6.9175,
            'lon': 107.6191,
            'display_name': 'Kota Bandung, Jawa Barat, Indonesia'
        })
        history = settings.get_location_history()
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]['city'], 'Bandung')
        self.assertEqual(history[1]['city'], 'Jakarta')

        # Add Surabaya
        settings.add_location_history({
            'city': 'Surabaya',
            'country': 'Indonesia',
            'lat': -7.2575,
            'lon': 112.7521,
            'display_name': 'Kota Surabaya, Jawa Timur, Indonesia'
        })
        history = settings.get_location_history()
        self.assertEqual(len(history), 3)
        self.assertEqual(history[0]['city'], 'Surabaya')

        # Re-add Bandung -> moves to index 0, length remains 3
        settings.add_location_history({
            'city': 'Bandung',
            'country': 'Indonesia',
            'lat': -6.9175,
            'lon': 107.6191,
            'display_name': 'Kota Bandung, Jawa Barat, Indonesia'
        })
        history = settings.get_location_history()
        self.assertEqual(len(history), 3)
        self.assertEqual(history[0]['city'], 'Bandung')
        self.assertEqual(history[1]['city'], 'Surabaya')
        self.assertEqual(history[2]['city'], 'Jakarta')

    def test_myquran_id_retention_and_update(self):
        settings.add_location_history({
            'city': 'Bandung',
            'country': 'Indonesia',
            'lat': -6.9175,
            'lon': 107.6191,
            'display_name': 'Kota Bandung, Jawa Barat, Indonesia'
        })
        settings.update_latest_history_myquran_id('1206')
        history = settings.get_location_history()
        self.assertEqual(history[0]['myquran_id'], '1206')

        # Re-adding Bandung without myquran_id preserves the existing myquran_id
        settings.add_location_history({
            'city': 'Bandung',
            'country': 'Indonesia',
            'lat': -6.9175,
            'lon': 107.6191,
            'display_name': 'Kota Bandung, Jawa Barat, Indonesia'
        })
        history = settings.get_location_history()
        self.assertEqual(history[0]['myquran_id'], '1206')

    def test_max_items_limit(self):
        for i in range(15):
            settings.add_location_history({
                'city': f'City_{i}',
                'country': 'Country',
                'lat': float(i),
                'lon': float(i),
                'display_name': f'City_{i}, Country'
            }, max_items=10)
        history = settings.get_location_history()
        self.assertEqual(len(history), 10)
        self.assertEqual(history[0]['city'], 'City_14')

    def test_remove_item(self):
        settings.clear_location_history()
        settings.add_location_history({'city': 'A', 'country': 'X', 'lat': 1.0, 'lon': 1.0, 'display_name': 'A, X'})
        settings.add_location_history({'city': 'B', 'country': 'X', 'lat': 2.0, 'lon': 2.0, 'display_name': 'B, X'})
        # History is [B, A]
        settings.remove_location_history(0)  # Remove B
        history = settings.get_location_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['city'], 'A')

    def test_clear_history(self):
        settings.clear_location_history()
        history = settings.get_location_history()
        self.assertEqual(len(history), 0)

    def test_i18n_keys(self):
        keys = [
            'recent_locations', 'search_results', 'clear_history',
            'clear_history_tooltip', 'delete_history_item_tooltip',
            'no_history', 'no_history_sub'
        ]
        for lang in ['id', 'en']:
            for key in keys:
                s = i18n.get_string(key, lang)
                self.assertNotEqual(s, key, f'Missing translation for {key} in {lang}')


if __name__ == '__main__':
    unittest.main()
