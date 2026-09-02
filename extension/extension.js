import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import St from 'gi://St';
import Clutter from 'gi://Clutter';
import GObject from 'gi://GObject';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const PRAYER_NAMES = {
    en: {
        Fajr: 'Fajr',
        Sunrise: 'Sunrise',
        Dhuhr: 'Dhuhr',
        Asr: 'Asr',
        Maghrib: 'Maghrib',
        Isha: 'Isha',
    },
    id: {
        Fajr: 'Subuh',
        Sunrise: 'Terbit',
        Dhuhr: 'Zuhur',
        Asr: 'Asar',
        Maghrib: 'Magrib',
        Isha: 'Isya',
    },
};

const PRAYER_ICONS = {
    Fajr: 'weather-clear-night-symbolic',
    Sunrise: 'weather-few-clouds-symbolic',
    Dhuhr: 'weather-clear-symbolic',
    Asr: 'weather-few-clouds-symbolic',
    Maghrib: 'weather-clear-night-symbolic',
    Isha: 'weather-clear-night-symbolic',
};

const IQAMAH_KEYS = {
    Fajr: 'fajr_iqamah',
    Dhuhr: 'dhuhr_iqamah',
    Asr: 'asr_iqamah',
    Maghrib: 'maghrib_iqamah',
    Isha: 'isha_iqamah',
};

const PrayerSection = GObject.registerClass(
class PrayerSection extends St.Button {
    _init(extension) {
        super._init({
            style_class: 'world-clocks-button prayer-section-button',
            can_focus: true,
            x_expand: true,
        });
        this._extension = extension;

        const mainBox = new St.BoxLayout({
            orientation: Clutter.Orientation.VERTICAL,
            style_class: 'prayer-section-box',
            x_expand: true,
        });

        // Header (Title on left, City on right)
        const headerBox = new St.BoxLayout({
            style_class: 'prayer-section-header-box',
            x_expand: true,
        });

        this._headerLabel = new St.Label({
            style_class: 'world-clocks-header',
            text: 'Waktu Salat',
            x_align: Clutter.ActorAlign.START,
        });

        this._cityLabel = new St.Label({
            style_class: 'world-clocks-timezone',
            text: '',
            x_align: Clutter.ActorAlign.END,
            x_expand: true,
            y_align: Clutter.ActorAlign.CENTER,
        });

        headerBox.add_child(this._headerLabel);
        headerBox.add_child(this._cityLabel);
        mainBox.add_child(headerBox);

        // Grid for timings (2 columns of 3 rows)
        this._gridLayout = new Clutter.GridLayout();
        this._grid = new St.Widget({
            style_class: 'world-clocks-grid prayer-timings-grid',
            x_expand: true,
            layout_manager: this._gridLayout,
        });
        this._gridLayout.hookup_style(this._grid);
        mainBox.add_child(this._grid);

        this.child = mainBox;
        this.update();
    }

    vfunc_clicked() {
        this._extension._openPrayerApp();
        Main.overview.hide();
        Main.panel.closeCalendar();
    }

    update() {
        this._grid.destroy_all_children();

        const settings = this._extension._settings || {};
        const lang = settings.language || 'id';
        const city = settings.city || 'Jakarta';
        const timings = this._extension._todayTimings;
        const nextPrayerName = this._extension._nextPrayerName;

        this._headerLabel.text = lang === 'en' ? 'Prayer Times' : 'Waktu Salat';
        this._cityLabel.text = city;

        if (!timings) {
            return;
        }

        const prayerList = [
            { key: 'Fajr', col: 0, row: 0 },
            { key: 'Sunrise', col: 0, row: 1 },
            { key: 'Dhuhr', col: 0, row: 2 },
            { key: 'Asr', col: 1, row: 0 },
            { key: 'Maghrib', col: 1, row: 1 },
            { key: 'Isha', col: 1, row: 2 },
        ];

        for (const item of prayerList) {
            const timeStr = timings[item.key] ? timings[item.key].split(' ')[0] : '--:--';
            const name = PRAYER_NAMES[lang]?.[item.key] || item.key;
            const isNext = item.key === nextPrayerName;

            const itemBox = new St.BoxLayout({
                style_class: isNext ? 'prayer-item-box prayer-item-capsule' : 'prayer-item-box',
                x_expand: true,
                y_align: Clutter.ActorAlign.CENTER,
            });

            const nameLabel = new St.Label({
                style_class: 'prayer-name-label',
                text: name,
                x_align: Clutter.ActorAlign.START,
                y_align: Clutter.ActorAlign.CENTER,
            });

            const timeLabel = new St.Label({
                style_class: 'world-clocks-time prayer-time-val',
                text: timeStr,
                x_align: Clutter.ActorAlign.END,
                y_align: Clutter.ActorAlign.CENTER,
                x_expand: true,
            });

            itemBox.add_child(nameLabel);
            itemBox.add_child(timeLabel);

            this._gridLayout.attach(itemBox, item.col, item.row, 1, 1);
        }
    }
});

export default class PrayerTimeClockExtension extends Extension {
    enable() {
        this._settingsPath = GLib.build_filenamev([GLib.get_home_dir(), '.config', 'prayer-time', 'settings.json']);
        this._settings = {};
        this._todayTimings = null;
        this._nextPrayerTime = null;
        this._nextPrayerName = '';
        this._lastCheckedDay = null;
        this._currentIconName = 'alarm-symbolic';
        this._timerId = null;
        this._fileMonitor = null;
        this._fileMonitorId = null;
        this._clockBox = null;
        this._clockDisplay = null;
        this._prayerSection = null;

        // Create UI components for top bar clock (non-reactive display only)
        this._indicatorBox = new St.BoxLayout({
            style_class: 'prayer-clock-indicator-box',
            reactive: false,
            can_focus: false,
        });

        this._icon = new St.Icon({
            icon_name: 'alarm-symbolic',
            style_class: 'prayer-clock-indicator-icon system-status-icon',
            reactive: false,
            can_focus: false,
        });

        this._label = new St.Label({
            text: '',
            y_align: Clutter.ActorAlign.CENTER,
            style_class: 'prayer-clock-indicator-label',
            reactive: false,
            can_focus: false,
        });

        this._indicatorBox.add_child(this._icon);
        this._indicatorBox.add_child(this._label);

        // Insert into GNOME Shell DateMenu top bar pill
        this._attachToDateMenu();

        // Load settings and calculate initial prayer time
        this._loadSettings();
        this._recalculateNextPrayer();

        // Insert Prayer Times Section inside DateMenu Calendar dropdown (like World Clocks)
        this._attachPrayerSection();

        // Monitor settings.json changes
        this._setupFileMonitor();

        // Start 1-second update loop
        this._updateDisplay();
        this._timerId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 1, () => {
            this._updateDisplay();
            return GLib.SOURCE_CONTINUE;
        });
    }

    disable() {
        if (this._timerId) {
            GLib.Source.remove(this._timerId);
            this._timerId = null;
        }

        if (this._fileMonitor) {
            if (this._fileMonitorId) {
                this._fileMonitor.disconnect(this._fileMonitorId);
                this._fileMonitorId = null;
            }
            this._fileMonitor.cancel();
            this._fileMonitor = null;
        }

        // Clean up top bar indicator
        if (this._clockBox && this._indicatorBox) {
            this._clockBox.remove_child(this._indicatorBox);
            this._clockBox.remove_style_class_name('prayer-unified-clock-box');
            this._clockBox.remove_style_class_name('clock');
            if (this._clockDisplay) {
                this._clockDisplay.add_style_class_name('clock');
            }
            this._clockBox = null;
            this._clockDisplay = null;
        } else if (this._indicatorBox) {
            const parent = this._indicatorBox.get_parent();
            if (parent) {
                parent.remove_child(this._indicatorBox);
            }
        }

        if (this._indicatorBox) {
            this._indicatorBox.destroy();
            this._indicatorBox = null;
        }

        // Clean up DateMenu dropdown section
        if (this._prayerSection) {
            const parent = this._prayerSection.get_parent();
            if (parent) {
                parent.remove_child(this._prayerSection);
            }
            this._prayerSection.destroy();
            this._prayerSection = null;
        }

        this._icon = null;
        this._label = null;
        this._settings = null;
        this._todayTimings = null;
    }

    _attachToDateMenu() {
        const dateMenu = Main.panel.statusArea.dateMenu;
        if (!dateMenu) {
            return;
        }

        this._dateMenu = dateMenu;
        this._clockDisplay = dateMenu._clockDisplay;

        if (this._clockDisplay) {
            this._clockBox = this._clockDisplay.get_parent();
            if (this._clockBox && this._clockBox.add_child) {
                this._clockDisplay.remove_style_class_name('clock');
                this._clockBox.add_style_class_name('clock');
                this._clockBox.add_style_class_name('prayer-unified-clock-box');
                this._clockBox.add_child(this._indicatorBox);
                return;
            }
        }

        if (dateMenu.add_child) {
            dateMenu.add_child(this._indicatorBox);
        }
    }

    _attachPrayerSection() {
        const dateMenu = Main.panel.statusArea.dateMenu;
        if (!dateMenu) return;

        const displaysBox = dateMenu._displaysSection ? dateMenu._displaysSection.child : null;
        if (displaysBox && displaysBox.add_child) {
            this._prayerSection = new PrayerSection(this);
            if (dateMenu._clocksItem) {
                displaysBox.insert_child_above(this._prayerSection, dateMenu._clocksItem);
            } else {
                displaysBox.add_child(this._prayerSection);
            }
        }
    }

    _loadSettings() {
        try {
            const file = Gio.File.new_for_path(this._settingsPath);
            if (!file.query_exists(null)) {
                this._settings = {};
                return;
            }

            const [success, contents] = file.load_contents(null);
            if (success) {
                const decoder = new TextDecoder('utf-8');
                this._settings = JSON.parse(decoder.decode(contents));
            }
        } catch (e) {
            console.error(`[PrayerTimeClock] Error loading settings: ${e.message}`);
            this._settings = {};
        }
    }

    _setupFileMonitor() {
        try {
            const file = Gio.File.new_for_path(this._settingsPath);
            this._fileMonitor = file.monitor_file(Gio.FileMonitorFlags.NONE, null);
            this._fileMonitorId = this._fileMonitor.connect('changed', (monitor, file, otherFile, eventType) => {
                if (
                    eventType === Gio.FileMonitorEvent.CHANGES_DONE_HINT ||
                    eventType === Gio.FileMonitorEvent.CHANGED ||
                    eventType === Gio.FileMonitorEvent.CREATED
                ) {
                    this._loadSettings();
                    this._recalculateNextPrayer();
                    this._updateDisplay();
                    if (this._prayerSection) {
                        this._prayerSection.update();
                    }
                }
            });
        } catch (e) {
            console.error(`[PrayerTimeClock] Error setting up file monitor: ${e.message}`);
        }
    }

    _formatDate(date) {
        const day = String(date.getDate()).padStart(2, '0');
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const year = date.getFullYear();
        return `${day}-${month}-${year}`;
    }

    _getCacheKey(city, month, year) {
        const normalizedCity = (city || 'Jakarta').toLowerCase().replace(/[^a-z0-9]/g, '');
        return `${normalizedCity}_${String(month).padStart(2, '0')}_${year}`;
    }

    _parseTime(timeStr) {
        if (!timeStr) return [0, 0];
        const clean = timeStr.split(' ')[0];
        const parts = clean.split(':').map(Number);
        return [parts[0] || 0, parts[1] || 0];
    }

    _recalculateNextPrayer() {
        this._nextPrayerTime = null;
        this._nextPrayerName = '';
        this._todayTimings = null;

        if (!this._settings) {
            return;
        }

        const city = this._settings.city || 'Jakarta';
        const cache = this._settings.cache || {};

        const now = new Date();
        const month = now.getMonth() + 1;
        const year = now.getFullYear();

        const cacheKey = this._getCacheKey(city, month, year);
        let data = cache[cacheKey];

        if (!data) {
            const keys = Object.keys(cache);
            if (keys.length > 0) {
                data = cache[keys[0]];
            }
        }

        if (!data || !Array.isArray(data)) {
            return;
        }

        const todayStr = this._formatDate(now);
        const tomorrow = new Date(now.getTime() + 24 * 60 * 60 * 1000);
        const tomorrowStr = this._formatDate(tomorrow);

        let todayData = null;
        let tomorrowData = null;

        for (const day of data) {
            const gDate = day?.date?.gregorian?.date;
            if (gDate === todayStr) {
                todayData = day;
            } else if (gDate === tomorrowStr) {
                tomorrowData = day;
            }
        }

        if (!todayData) {
            todayData = data[0] || null;
        }

        if (!todayData || !todayData.timings) {
            return;
        }

        this._todayTimings = todayData.timings;

        const prayerKeys = ['Fajr', 'Sunrise', 'Dhuhr', 'Asr', 'Maghrib', 'Isha'];
        const upcoming = [];

        for (const pName of prayerKeys) {
            const timeStr = this._todayTimings[pName];
            if (timeStr) {
                const [h, m] = this._parseTime(timeStr);
                const pDate = new Date(now.getFullYear(), now.getMonth(), now.getDate(), h, m, 0);
                if (pDate > now) {
                    upcoming.push({ name: pName, date: pDate });
                }
            }
        }

        if (upcoming.length === 0) {
            let tomorrowFajrStr = null;
            if (tomorrowData && tomorrowData.timings) {
                tomorrowFajrStr = tomorrowData.timings.Fajr;
            } else {
                tomorrowFajrStr = this._todayTimings.Fajr;
            }

            if (tomorrowFajrStr) {
                const [h, m] = this._parseTime(tomorrowFajrStr);
                const pDate = new Date(tomorrow.getFullYear(), tomorrow.getMonth(), tomorrow.getDate(), h, m, 0);
                upcoming.push({ name: 'Fajr', date: pDate });
            }
        }

        if (upcoming.length > 0) {
            upcoming.sort((a, b) => a.date - b.date);
            this._nextPrayerName = upcoming[0].name;
            this._nextPrayerTime = upcoming[0].date;
        }
    }

    _getCurrentIqamahPrayer(now) {
        if (!this._todayTimings || !this._settings) return null;

        const prayers = ['Fajr', 'Dhuhr', 'Asr', 'Maghrib', 'Isha'];
        for (const pName of prayers) {
            const timeStr = this._todayTimings[pName];
            if (!timeStr) continue;

            const [h, m] = this._parseTime(timeStr);
            const pDate = new Date(now.getFullYear(), now.getMonth(), now.getDate(), h, m, 0);

            const durationKey = IQAMAH_KEYS[pName];
            const durationMinutes = (durationKey && this._settings[durationKey] !== undefined) ? this._settings[durationKey] : 10;
            if (durationMinutes <= 0) continue;

            const endDate = new Date(pDate.getTime() + durationMinutes * 60 * 1000);
            if (now >= pDate && now <= endDate) {
                return { name: pName, date: pDate };
            }
        }

        return null;
    }

    _getTranslatedName(pName, lang) {
        const langMap = PRAYER_NAMES[lang] || PRAYER_NAMES.id;
        return langMap[pName] || pName;
    }

    _updateDisplay() {
        if (!this._label || !this._icon) return;

        const now = new Date();
        const dayStr = this._formatDate(now);
        if (dayStr !== this._lastCheckedDay) {
            this._lastCheckedDay = dayStr;
            this._recalculateNextPrayer();
            if (this._prayerSection) {
                this._prayerSection.update();
            }
        }

        const lang = (this._settings && this._settings.language) || 'id';

        // Check if countdown ended
        if (this._nextPrayerTime && now >= this._nextPrayerTime) {
            this._recalculateNextPrayer();
            if (this._prayerSection) {
                this._prayerSection.update();
            }
        }

        // 1. Check Iqamah status
        const iqamahActive = this._getCurrentIqamahPrayer(now);
        if (iqamahActive) {
            const elapsedSeconds = Math.floor((now.getTime() - iqamahActive.date.getTime()) / 1000);
            const minutes = Math.floor(elapsedSeconds / 60);
            const seconds = elapsedSeconds % 60;
            const translatedName = this._getTranslatedName(iqamahActive.name, lang);

            const labelText = `${translatedName} +${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
            this._label.set_text(labelText);

            const iconName = PRAYER_ICONS[iqamahActive.name] || 'alarm-symbolic';
            if (iconName !== this._currentIconName) {
                this._currentIconName = iconName;
                this._icon.set_icon_name(iconName);
            }
            return;
        }

        // 2. Countdown to next prayer
        if (!this._nextPrayerTime) {
            this._label.set_text('');
            return;
        }

        const diffSeconds = Math.max(0, Math.floor((this._nextPrayerTime.getTime() - now.getTime()) / 1000));
        const hours = Math.floor(diffSeconds / 3600);
        const minutes = Math.floor((diffSeconds % 3600) / 60);
        const seconds = diffSeconds % 60;

        const translatedName = this._getTranslatedName(this._nextPrayerName, lang);
        const labelText = `${translatedName} - ${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
        this._label.set_text(labelText);

        const iconName = PRAYER_ICONS[this._nextPrayerName] || 'alarm-symbolic';
        if (iconName !== this._currentIconName) {
            this._currentIconName = iconName;
            this._icon.set_icon_name(iconName);
        }
    }

    _openPrayerApp() {
        try {
            const connection = Gio.bus_get_sync(Gio.BusType.SESSION, null);
            connection.call(
                'com.github.aska.PrayerTime',
                '/com/github/aska/PrayerTime',
                'org.gtk.Application',
                'Activate',
                new GLib.Variant('(a{sv})', [{}]),
                null,
                Gio.DBusCallFlags.NONE,
                -1,
                null,
                (conn, res) => {
                    try {
                        conn.call_finish(res);
                    } catch (e) {
                        this._launchAppFallback();
                    }
                }
            );
        } catch (e) {
            this._launchAppFallback();
        }
    }

    _launchAppFallback() {
        try {
            const appInfo = Gio.DesktopAppInfo.new('com.github.aska.PrayerTime.desktop');
            if (appInfo) {
                appInfo.launch([], null);
                return;
            }
        } catch (e) {
            // Ignore and try CLI
        }

        try {
            GLib.spawn_command_line_async('prayer-time');
        } catch (err) {
            try {
                const devMain = GLib.build_filenamev([GLib.get_home_dir(), 'Projects', 'Other', 'prayer-time', 'main.py']);
                if (GLib.file_test(devMain, GLib.FileTest.EXISTS)) {
                    GLib.spawn_command_line_async(`python3 "${devMain}"`);
                }
            } catch (ex) {
                console.error(`[PrayerTimeClock] Error launching app fallback: ${ex.message}`);
            }
        }
    }
}
