import threading
import datetime
import urllib.parse
from typing import Any, Dict, List, Optional
import requests
from gi.repository import GLib
from prayer_time import __version__

REQUEST_TIMEOUT_SECONDS = 10
USER_AGENT = f"PrayerTime/{__version__} (https://github.com/askaerlangga/prayer-time)"

# Thread-local storage to provide safe, independent connection pooling per thread
_thread_local = threading.local()


def _get_session() -> requests.Session:
    """Returns a thread-local requests.Session configured with standard User-Agent."""
    session = getattr(_thread_local, "session", None)
    if session is None:
        session = requests.Session()
        session.headers.update({"User-Agent": USER_AGENT})
        _thread_local.session = session
    return session


def _parse_nominatim_item(
    item: Dict[str, Any],
    is_reverse: bool = False,
    override_lat: Optional[float] = None,
    override_lon: Optional[float] = None
) -> Dict[str, Any]:
    """
    Extracts standardized location attributes and administrative candidates from a Nominatim payload.
    For reverse geocoding (GPS), prioritizes administrative city names over POI/building names,
    and preserves exact GPS coordinates passed in override_lat / override_lon.
    """
    name = item.get("display_name", "")
    address = item.get("address", {})
    addr_type = item.get("addresstype", "city")

    if is_reverse:
        # For GPS reverse geocode, look for administrative boundaries first
        city = (
            address.get("city") or
            address.get("town") or
            address.get("municipality") or
            address.get("regency") or
            address.get("county") or
            item.get("name") or
            address.get(addr_type) or
            address.get("village") or
            address.get("suburb") or
            (name.split(",")[0].strip() if name else "") or
            "Unknown"
        )
    else:
        # For free-text search, prioritize direct match name
        city = (
            item.get("name") or
            address.get(addr_type) or
            (name.split(",")[0].strip() if name else "") or
            address.get("city") or
            address.get("town") or
            address.get("municipality") or
            address.get("regency") or
            address.get("county") or
            address.get("village") or
            address.get("suburb") or
            "Unknown"
        )

    candidates = []
    keys = ["city", "county", "regency", "city_district", "municipality", "town", "state", "suburb", "village"]
    seen = set()
    for key in keys:
        val = address.get(key)
        if val and val not in seen:
            candidates.append(val)
            seen.add(val)

    if override_lat is not None and override_lon is not None:
        lat_val = float(override_lat)
        lon_val = float(override_lon)
    else:
        try:
            lat_val = float(item.get("lat", 0.0))
            lon_val = float(item.get("lon", 0.0))
        except (ValueError, TypeError):
            lat_val, lon_val = 0.0, 0.0

    return {
        "display_name": name,
        "city": city,
        "country": address.get("country", ""),
        "addresstype": addr_type,
        "lat": lat_val,
        "lon": lon_val,
        "candidates": candidates
    }


def fetch_prayer_times_async(latitude, longitude, method, month, year, myquran_id, callback, request_id=None):
    """
    Fetches prayer times for a whole month by coordinates (from Aladhan).
    If myquran_id is provided, fetches official Kemenag times and overrides Aladhan times.
    Optional request_id is passed back to callback(data, error, request_id) if provided.
    """
    def run():
        session = _get_session()
        try:
            # 1. Fetch monthly calendar from Aladhan API
            aladhan_url = "https://api.aladhan.com/v1/calendar"
            aladhan_params = {
                "latitude": latitude,
                "longitude": longitude,
                "method": method,
                "month": month,
                "year": year
            }
            r = session.get(aladhan_url, params=aladhan_params, timeout=REQUEST_TIMEOUT_SECONDS)
            if r.status_code != 200:
                _dispatch_callback(callback, None, f"Aladhan API Error: Status {r.status_code}", request_id)
                return

            response_json = r.json()
            data = response_json.get("data", [])
            if not data:
                _dispatch_callback(callback, None, "No prayer data returned from API", request_id)
                return

            # 2. If it is an Indonesian city with MyQuran ID, merge Kemenag times
            if myquran_id:
                try:
                    safe_id = urllib.parse.quote(str(myquran_id), safe="")
                    myquran_url = f"https://api.myquran.com/v2/sholat/jadwal/{safe_id}/{year}/{month:02d}"
                    rq = session.get(myquran_url, timeout=REQUEST_TIMEOUT_SECONDS)
                    if rq.status_code == 200:
                        res = rq.json()
                        if res.get("status") and "data" in res and "jadwal" in res["data"]:
                            q_timings_map = {}
                            for day in res["data"]["jadwal"]:
                                q_timings_map[day["date"]] = {
                                    "Fajr": day.get("subuh", ""),
                                    "Sunrise": day.get("terbit", ""),
                                    "Dhuhr": day.get("dzuhur", ""),
                                    "Asr": day.get("ashar", ""),
                                    "Maghrib": day.get("maghrib", ""),
                                    "Isha": day.get("isya", ""),
                                    "Imsak": day.get("imsak", "")
                                }

                            # Merge Kemenag times into Aladhan calendar
                            for day in data:
                                greg_date = day.get("date", {}).get("gregorian", {}).get("date")
                                if greg_date:
                                    d_obj = datetime.datetime.strptime(greg_date, "%d-%m-%Y")
                                    lookup_key = d_obj.strftime("%Y-%m-%d")
                                    if lookup_key in q_timings_map:
                                        day["timings"].update(q_timings_map[lookup_key])
                except Exception as ex:
                    print(f"[PrayerTime] Warning: Error merging MyQuran data: {ex}")

            _dispatch_callback(callback, data, None, request_id)

        except requests.exceptions.Timeout:
            _dispatch_callback(callback, None, "Request timed out. Please check your internet connection.", request_id)
        except requests.exceptions.RequestException as e:
            _dispatch_callback(callback, None, f"Network error: {e}", request_id)
        except Exception as e:
            _dispatch_callback(callback, None, str(e), request_id)

    threading.Thread(target=run, daemon=True).start()


def _dispatch_callback(callback, data, error, request_id=None):
    """Safely dispatches callback onto main GLib thread, passing request_id if specified."""
    if request_id is not None:
        GLib.idle_add(callback, data, error, request_id)
    else:
        GLib.idle_add(callback, data, error)


def search_location_async(query, callback, request_id=None):
    """
    Searches for a location using OpenStreetMap's Nominatim geocoding.
    Runs in a background thread and calls callback(results, error, [request_id]) on main thread.
    """
    def run():
        session = _get_session()
        try:
            url = "https://nominatim.openstreetmap.org/search"
            params = {
                "q": query,
                "format": "json",
                "limit": 5,
                "addressdetails": 1
            }
            r = session.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
            if r.status_code != 200:
                _dispatch_callback(callback, None, f"Search Error: Status {r.status_code}", request_id)
                return

            results = r.json()
            parsed_results = [_parse_nominatim_item(item, is_reverse=False) for item in results]
            _dispatch_callback(callback, parsed_results, None, request_id)

        except requests.exceptions.Timeout:
            _dispatch_callback(callback, None, "Location search timed out.", request_id)
        except requests.exceptions.RequestException as e:
            _dispatch_callback(callback, None, f"Network error: {e}", request_id)
        except Exception as e:
            _dispatch_callback(callback, None, str(e), request_id)

    threading.Thread(target=run, daemon=True).start()


def reverse_geocode_async(latitude, longitude, callback):
    """
    Reverse geocodes coordinates (lat, lon) to human-readable address and candidates using Nominatim.
    Runs in a background thread and calls callback(location_data, error) on the main GLib thread.
    """
    def run():
        session = _get_session()
        try:
            url = "https://nominatim.openstreetmap.org/reverse"
            params = {
                "lat": latitude,
                "lon": longitude,
                "format": "json",
                "addressdetails": 1
            }
            r = session.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
            if r.status_code != 200:
                GLib.idle_add(callback, None, f"Reverse Geocode Error: Status {r.status_code}")
                return

            item = r.json()
            if not item or "address" not in item:
                GLib.idle_add(callback, None, "Invalid response from geocoding service")
                return

            location_data = _parse_nominatim_item(
                item,
                is_reverse=True,
                override_lat=float(latitude),
                override_lon=float(longitude)
            )
            GLib.idle_add(callback, location_data, None)

        except requests.exceptions.Timeout:
            GLib.idle_add(callback, None, "Geocoding timed out. Please check your internet connection.")
        except requests.exceptions.RequestException as e:
            GLib.idle_add(callback, None, f"Network error: {e}")
        except Exception as e:
            GLib.idle_add(callback, None, str(e))

    threading.Thread(target=run, daemon=True).start()


def get_myquran_id_async(location_data, callback):
    """
    Searches for a city ID in the MyQuran v2 database.
    Applies a robust multi-step fallback search across administrative candidates
    (city, county, state, etc.) and prefers matches based on the administrative type.
    """
    def run():
        session = _get_session()
        try:
            if isinstance(location_data, dict):
                city_name = location_data.get("city", "")
                candidates = location_data.get("candidates", [])
                if not candidates:
                    candidates = [city_name]
            else:
                city_name = str(location_data)
                candidates = [city_name]

            is_kab_hint = any(x in city_name.upper() for x in ["KAB", "KABUPATEN", "REGENCY"])

            queries_tried = 0
            max_queries = 4

            for name in candidates[:4]:
                if queries_tried >= max_queries:
                    break

                clean_name = "".join(c for c in name if c.isalnum() or c.isspace())
                words = clean_name.upper().split()
                ignored = {"KOTA", "KABUPATEN", "KAB", "KECAMATAN", "KELURAHAN", "DESA", "DAERAH", "KHUSUS", "IBUKOTA"}
                filtered_words = [w for w in words if w not in ignored]

                if not filtered_words:
                    continue

                keywords = [" ".join(filtered_words)]
                if len(filtered_words) > 1:
                    keywords.append(filtered_words[0])

                is_kab = is_kab_hint or any(x in name.upper() for x in ["KAB", "KABUPATEN", "REGENCY", "COUNTY"])

                for kw in keywords:
                    if queries_tried >= max_queries:
                        break
                    if kw.upper() in {"UTARA", "SELATAN", "TIMUR", "BARAT", "PUSAT"}:
                        continue

                    queries_tried += 1
                    safe_kw = urllib.parse.quote(kw.strip(), safe="")
                    url = f"https://api.myquran.com/v2/sholat/kota/cari/{safe_kw}"
                    try:
                        r = session.get(url, timeout=5)
                        if r.status_code == 200:
                            res = r.json()
                            if res.get("status") and res.get("data"):
                                valid_items = []
                                for item in res["data"]:
                                    lokasi = item.get("lokasi", "").upper()
                                    lok_clean = "".join(c if c.isalnum() or c.isspace() else " " for c in lokasi)
                                    lok_words = lok_clean.split()
                                    kw_words = kw.upper().split()
                                    if all(w in lok_words for w in kw_words):
                                        valid_items.append(item)

                                if not valid_items:
                                    continue

                                best_id = valid_items[0]["id"]
                                best_score = -1
                                for item in valid_items:
                                    lokasi = item.get("lokasi", "").upper()
                                    score = 0
                                    if is_kab:
                                        if "KAB" in lokasi or "KABUPATEN" in lokasi:
                                            score += 10
                                    else:
                                        if "KOTA" in lokasi:
                                            score += 10
                                    if score > best_score:
                                        best_score = score
                                        best_id = item["id"]
                                GLib.idle_add(callback, best_id)
                                return
                    except Exception:
                        continue

            GLib.idle_add(callback, None)
        except Exception:
            GLib.idle_add(callback, None)

    threading.Thread(target=run, daemon=True).start()
