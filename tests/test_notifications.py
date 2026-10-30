import unittest
import datetime as dt_mod
from datetime import datetime
from unittest.mock import patch, MagicMock
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('Notify', '0.7')
from prayer_time import i18n, settings
from prayer_time.ui.window import PrayerWindow


class TestNotificationMessages(unittest.TestCase):
    def test_notification_strings_not_redundant_en(self):
        body = i18n.get_string("notif_body", "en").format("17:52")
        self.assertEqual(body, "It's time to pray (17:52).")
        self.assertNotIn("prayer time", body.lower())

        sunrise_title = i18n.get_string("notif_sunrise_title", "en")
        self.assertEqual(sunrise_title, "Sunrise")

        sunrise_body = i18n.get_string("notif_sunrise_body", "en").format("05:45")
        self.assertEqual(sunrise_body, "Fajr time has ended (05:45).")

    def test_notification_strings_not_redundant_id(self):
        body = i18n.get_string("notif_body", "id").format("17:52")
        self.assertEqual(body, "Saatnya menunaikan salat (17:52).")
        self.assertNotIn("waktu salat", body.lower())

        sunrise_title = i18n.get_string("notif_sunrise_title", "id")
        self.assertEqual(sunrise_title, "Terbit Matahari")

        sunrise_body = i18n.get_string("notif_sunrise_body", "id").format("05:45")
        self.assertEqual(sunrise_body, "Waktu Subuh telah berakhir (05:45).")

    @patch("prayer_time.ui.window.Notify.Notification.new")
    def test_trigger_prayer_notification_title_and_body(self, mock_notif_new):
        # Create a mock window instance to test trigger_prayer_notification logic
        win = MagicMock(spec=PrayerWindow)
        win.last_notified_prayer = None
        win.next_prayer_time = datetime(2026, 10, 30, 17, 52)
        win.next_prayer_api_name = "Maghrib"

        # Bind the actual method to the mock
        win.trigger_prayer_notification = PrayerWindow.trigger_prayer_notification.__get__(win, PrayerWindow)

        with patch("prayer_time.settings.get_setting") as mock_get_setting:
            # Test English
            mock_get_setting.side_effect = lambda k, default=None: "en" if k == "language" else default
            win.trigger_prayer_notification()

            mock_notif_new.assert_called_once_with("Maghrib", "It's time to pray (17:52).", "alarm-symbolic")

        mock_notif_new.reset_mock()
        win.last_notified_prayer = None
        win.next_prayer_api_name = "Sunrise"
        win.next_prayer_time = datetime(2026, 10, 31, 5, 45)

        with patch("prayer_time.settings.get_setting") as mock_get_setting:
            # Test Sunrise in Indonesian
            mock_get_setting.side_effect = lambda k, default=None: "id" if k == "language" else default
            win.trigger_prayer_notification()

            mock_notif_new.assert_called_once_with(
                "Terbit Matahari",
                "Waktu Subuh telah berakhir (05:45).",
                "alarm-symbolic"
            )

    def test_update_tick_iqamah_to_countdown_transition(self):
        # Create a mock PrayerWindow to test update_tick transition
        win = MagicMock()
        win.current_day_str = "30-10-2026"
        win.today_timings = {
            "Fajr": "04:12",
            "Sunrise": "05:26",
            "Dhuhr": "11:43",
            "Asr": "14:57",
            "Maghrib": "17:52",
            "Isha": "19:03",
        }
        win.next_prayer_api_name = "Isha"
        win.next_prayer_time = datetime(2026, 10, 30, 19, 3)
        win.get_visible.return_value = True

        lbl_next_prayer_val = [""]
        win.lbl_next_prayer.get_label.side_effect = lambda: lbl_next_prayer_val[0]
        def set_label_mock(v):
            lbl_next_prayer_val[0] = v
        win.lbl_next_prayer.set_label.side_effect = set_label_mock

        # Bind methods
        win.parse_time = PrayerWindow.parse_time.__get__(win, PrayerWindow)
        win.get_current_iqamah_prayer = PrayerWindow.get_current_iqamah_prayer.__get__(win, PrayerWindow)
        win.update_tick = PrayerWindow.update_tick.__get__(win, PrayerWindow)

        # 1. During Iqamah at 17:55 (within 10-minute window for Maghrib)
        with patch("prayer_time.ui.window.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = datetime(2026, 10, 30, 17, 55, 0)
            mock_dt.datetime.combine = datetime.combine
            mock_dt.datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            mock_dt.timedelta = dt_mod.timedelta
            mock_dt.time = dt_mod.time

            with patch("prayer_time.settings.get_setting") as mock_get_setting:
                mock_get_setting.side_effect = lambda k, default=None: "en" if k == "language" else default
                win.update_tick()

                self.assertEqual(win.lbl_next_prayer.get_label(), "Prayer Time: Maghrib")
                win.lbl_countdown.set_label.assert_called_with("+03:00")
                win.highlight_active_row.assert_called_with("Maghrib")

        # 2. After Iqamah at 18:03 (Iqamah has ended, counting down to Isha 19:03)
        win.lbl_countdown.reset_mock()
        win.highlight_active_row.reset_mock()

        with patch("prayer_time.ui.window.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = datetime(2026, 10, 30, 18, 3, 0)
            mock_dt.datetime.combine = datetime.combine
            mock_dt.datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            mock_dt.timedelta = dt_mod.timedelta
            mock_dt.time = dt_mod.time

            with patch("prayer_time.settings.get_setting") as mock_get_setting:
                mock_get_setting.side_effect = lambda k, default=None: "en" if k == "language" else default
                win.update_tick()

                # Text must be updated to Isha, NOT still Maghrib!
                self.assertEqual(win.lbl_next_prayer.get_label(), "Next Prayer: Isha")
                win.lbl_countdown.set_label.assert_called_with("01:00:00")
                win.highlight_active_row.assert_called_with("Isha")


if __name__ == "__main__":
    unittest.main()
