import threading
import datetime
import requests
from gi.repository import GLib

def fetch_prayer_times_async(latitude, longitude, method, month, year, myquran_id, callback):
    """
    Fetches prayer times for a whole month by coordinates (from Aladhan).
    If myquran_id is provided, fetches official Kemenag times and overrides Aladhan times,
    keeping Gregorian and Hijri calendar structures intact.
    """
    def run():
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
            r = requests.get(aladhan_url, params=aladhan_params, timeout=10)
            if r.status_code != 200:
                GLib.idle_add(callback, None, f"Aladhan API Error: Status {r.status_code}")
                return
                
            data = r.json().get("data", [])
            
            # 2. If it is an Indonesian city with MyQuran ID, merge Kemenag times
            if myquran_id:
                try:
                    myquran_url = f"https://api.myquran.com/v2/sholat/jadwal/{myquran_id}/{year}/{month:02d}"
                    rq = requests.get(myquran_url, timeout=10)
                    if rq.status_code == 200:
                        res = rq.json()
                        if res.get("status"):
                            # Map date -> Kemenag timings
                            q_timings_map = {}
                            for day in res["data"]["jadwal"]:
                                q_timings_map[day["date"]] = {
                                    "Fajr": day["subuh"],
                                    "Sunrise": day["terbit"],
                                    "Dhuhr": day["dzuhur"],
                                    "Asr": day["ashar"],
                                    "Maghrib": day["maghrib"],
                                    "Isha": day["isya"],
                                    "Imsak": day["imsak"]
                                }
                            
                            # Merge Kemenag times into Aladhan calendar
                            for day in data:
                                greg_date = day["date"]["gregorian"]["date"]
                                d_obj = datetime.datetime.strptime(greg_date, "%d-%m-%Y")
                                lookup_key = d_obj.strftime("%Y-%m-%d")
                                
                                if lookup_key in q_timings_map:
                                    day["timings"].update(q_timings_map[lookup_key])
                except Exception as ex:
                    print(f"Error merging MyQuran data: {ex}")
            
            GLib.idle_add(callback, data, None)
            
        except Exception as e:
            GLib.idle_add(callback, None, str(e))
            
    threading.Thread(target=run, daemon=True).start()

def search_location_async(query, callback):
    """
    Searches for a location using OpenStreetMap's Nominatim geocoding.
    Runs in a background thread and calls callback(results, error) on the main GLib thread.
    """
    def run():
        try:
            url = "https://nominatim.openstreetmap.org/search"
            headers = {"User-Agent": "PrayerTimeApp/1.0"}
            params = {
                "q": query,
                "format": "json",
                "limit": 5,
                "addressdetails": 1
            }
            r = requests.get(url, params=params, headers=headers, timeout=10)
            if r.status_code == 200:
                results = r.json()
                # Parse search results to extract clean names
                parsed_results = []
                for item in results:
                    name = item.get("display_name")
                    # Try to get city, town or suburb
                    address = item.get("address", {})
                    city = address.get("city") or address.get("town") or address.get("village") or address.get("suburb") or address.get("municipality")
                    state = address.get("state")
                    country = address.get("country")
                    
                    if not city:
                        city = name.split(",")[0]
                    
                    # Generate administrative candidates for MyQuran lookup (most specific to least specific)
                    candidates = []
                    keys = ["city", "town", "municipality", "county", "regency", "state", "suburb", "village"]
                    seen = set()
                    for key in keys:
                        val = address.get(key)
                        if val and val not in seen:
                            candidates.append(val)
                            seen.add(val)
                    
                    parsed_results.append({
                        "display_name": name,
                        "city": city,
                        "country": country,
                        "addresstype": item.get("addresstype", ""),
                        "lat": float(item.get("lat")),
                        "lon": float(item.get("lon")),
                        "candidates": candidates
                    })
                GLib.idle_add(callback, parsed_results, None)
            else:
                GLib.idle_add(callback, None, f"Search Error: Status {r.status_code}")
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
        try:
            # Handle both string (for backwards compatibility) and dict input
            if isinstance(location_data, dict):
                city_name = location_data.get("city", "")
                candidates = location_data.get("candidates", [])
                if not candidates:
                    candidates = [city_name]
            else:
                city_name = str(location_data)
                candidates = [city_name]
                
            is_kab_hint = any(x in city_name.upper() for x in ["KAB", "KABUPATEN", "REGENCY"])
            
            for name in candidates:
                # Clean name
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
                    # Ignore trivial keywords like directionals to avoid false positives
                    if kw.upper() in {"UTARA", "SELATAN", "TIMUR", "BARAT", "PUSAT"}:
                        continue
                        
                    url = f"https://api.myquran.com/v2/sholat/kota/cari/{kw}"
                    r = requests.get(url, timeout=5)
                    if r.status_code == 200:
                        res = r.json()
                        if res.get("status") and res.get("data"):
                            valid_items = []
                            for item in res["data"]:
                                lokasi = item["lokasi"].upper()
                                # Clean lokasi words to check word boundaries
                                lok_clean = "".join(c if c.isalnum() or c.isspace() else " " for c in lokasi)
                                lok_words = lok_clean.split()
                                kw_words = kw.upper().split()
                                # Enforce strict matching: all keyword words must be whole words in the lokasi
                                if all(w in lok_words for w in kw_words):
                                    valid_items.append(item)
                                    
                            if not valid_items:
                                continue
                                
                            best_id = valid_items[0]["id"]
                            best_score = -1
                            for item in valid_items:
                                lokasi = item["lokasi"].upper()
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
            GLib.idle_add(callback, None)
        except Exception:
            GLib.idle_add(callback, None)
            
    threading.Thread(target=run, daemon=True).start()
