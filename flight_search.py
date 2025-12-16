from datetime import datetime
import requests
import time
import hashlib
import json as json_module
import traceback
from typing import List, Dict, Any, Optional

from config import get_logger
logs = get_logger(__name__)
logger = logs

from config import AFFILIATE_MARKER, API_TOKEN, HOST, USER_IP, USE_REAL_API, FEATURED_FLIGHT_LIMIT, DEBUG_MODE
from config import USE_AMADEUS, AMADEUS_API_KEY, FORCE_AMADEUS
from amadeus_search import search_flights_amadeus
from urllib.parse import urlencode

def search_flights(origin_code, destination_code, date_from_str, date_to_str, 
                    trip_type, adults=1, children=0, infants=0, cabin_class="economy", 
                    limit=None, direct_only=False) -> List[Dict]:
    
    if not USE_REAL_API:
        logger.info("🔍 Using Travelpayouts MOCK API (No Deep Link Merge)")
        return search_flights_mock(
            origin_code, destination_code, date_from_str, date_to_str, 
            trip_type, limit=limit, direct_only=direct_only
        )
    
    logger.info("Starting HYBRID REAL API search (Amadeus + Travelpayouts Merge)")
    
    amadeus_flights = []
    travelpayouts_link_map = {}
    
    # 1. Get Flight Details (Amadeus - Primary Source)
    if USE_AMADEUS and AMADEUS_API_KEY:
        try:
            amadeus_flights = search_flights_amadeus(
                origin=origin_code, destination=destination_code, date_from=date_from_str, 
                date_to=date_to_str, trip_type=trip_type, adults=adults, children=children, 
                infants=infants, cabin_class=cabin_class, limit=limit, direct_only=direct_only
            )
            logger.info(f"✅ Amadeus returned {len(amadeus_flights)} flights")
        except Exception as e:
            logger.error(f"❌ Amadeus search failed: {e}")
            traceback.print_exc()
            if FORCE_AMADEUS:
                # If forced, treat failure as critical and exit the entire function
                logger.critical("🚨 FORCE_AMADEUS is True. Cannot proceed without Amadeus data.")
                return [] 
    else:
        logger.warning("Amadeus search skipped: USE_AMADEUS is False or AMADEUS_API_KEY is missing.")

    # 2. Get Deep Links (Travelpayouts - Secondary Source)
    if not amadeus_flights:
        logger.warning("No Amadeus flights found. Skipping Travelpayouts deep link search.")
    else:
        try:
            travelpayouts_link_map = search_flights_api(
                origin_code, destination_code, date_from_str, date_to_str, 
                trip_type, adults, children, infants, cabin_class, limit=limit, direct_only=direct_only
            )
            
            logger.info(f"✅ Travelpayouts link map size: {len(travelpayouts_link_map)}")
            
        except Exception as e:
            logger.error(f"❌ Travelpayouts search failed: {e}")
            traceback.print_exc()

    # 3. Merge Results 
    if not amadeus_flights:
        logger.warning("No Amadeus flight data. Cannot merge. Returning empty list.")
        return []

    final_flights = get_combined_flight_results(
        amadeus_flights, 
        travelpayouts_link_map
    )
    
    logger.info(f"✈️ Returning {len(final_flights)} combined flights.")
    return final_flights


def map_cabin_class(cabin_class):
    return {
        "economy": "Y",
        "business": "C",
        "first": "F"
    }.get(cabin_class.lower(), "Y")


def generate_flight_id(link, airline, departure):
    raw = f"{airline}_{departure}_{link}"
    return hashlib.md5(raw.encode()).hexdigest()


def format_flight_datetime(date_str, time_str):
    if not date_str or not time_str:
        return ""
    
    try:
        time_parts = time_str.split(":")
        time_formatted = f"{time_parts[0]}:{time_parts[1]}"
        return f"{date_str} {time_formatted}"
    except Exception as e:
        logger.warning(f"Time formatting error: {e}")
        return f"{date_str} {time_str}"


def calculate_duration_minutes(all_flights):
    total = sum(f.get("duration", 0) for f in all_flights)
    return total


def format_duration(minutes):
    if not minutes or minutes == 0:
        return "N/A"
    hours = minutes // 60
    mins = minutes % 60
    if hours > 0 and mins > 0:
        return f"{hours}h {mins}m"
    elif hours > 0:
        return f"{hours}h"
    else:
        return f"{mins}m"


def generate_signature(token, marker, host, user_ip, locale, trip_class, passengers, segments):
    outbound = segments[0]

    if len(segments) == 1:
        raw_string = (
            f"{token}:{host}:{locale}:{marker}:"
            f"{passengers['adults']}:{passengers['children']}:{passengers['infants']}:"
            f"{outbound['date']}:{outbound['destination']}:{outbound['origin']}:"
            f"{trip_class}:{user_ip}"
        )
    else:
        return_seg = segments[1]
        raw_string = (
            f"{token}:{host}:{locale}:{marker}:"
            f"{passengers['adults']}:{passengers['children']}:{passengers['infants']}:"
            f"{outbound['date']}:{outbound['destination']}:{outbound['origin']}:"
            f"{return_seg['date']}:{return_seg['destination']}:{return_seg['origin']}:"
            f"{trip_class}:{user_ip}"
        )
    
    if DEBUG_MODE:
        print("🔐 Raw signature string:", raw_string)
    
    return hashlib.md5(raw_string.encode("utf-8")).hexdigest()


def search_flights_api(origin_code, destination_code, date_from_str, date_to_str=None, trip_type="round-trip", adults=1, children=0, infants=0, cabin_class="economy", limit=None, direct_only=False):
    
    def standardize_api_datetime(raw_date: str, raw_time: str) -> str:
        combined_dt_str = f"{raw_date} {raw_time}"
        try:
            dt_object = datetime.strptime(combined_dt_str, "%Y-%m-%d %H:%M")
            return dt_object.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError as e:
            logger.warning(f"Failed to parse Travelpayouts time for key: {e}. Raw data: {combined_dt_str}")
            if len(combined_dt_str) == 16:
                return combined_dt_str + ":00"
            return combined_dt_str 
    
    def to_ddmm(date_str):
        if not date_str or len(date_str) < 10: return ""
        return date_str[8:10] + date_str[5:7]

    init_url = "https://api.travelpayouts.com/v1/flight_search"

    segments = [{
        "date": date_from_str,
        "destination": destination_code,
        "origin": origin_code
    }]
    
    if trip_type == "round-trip" and date_to_str:
        segments.append({
            "date": date_to_str,
            "destination": origin_code,
            "origin": destination_code
        })

    passengers = {
        "adults": int(adults),
        "children": int(children),
        "infants": int(infants)
    }
    
    trip_class_code = map_cabin_class(cabin_class)

    signature = generate_signature(
        token=API_TOKEN,
        marker=AFFILIATE_MARKER,
        host=HOST,
        user_ip=USER_IP,
        locale="en",
        trip_class=trip_class_code,
        passengers=passengers,
        segments=segments
    )

    payload = {
        "marker": AFFILIATE_MARKER,
        "host": HOST,
        "user_ip": USER_IP,
        "locale": "en",
        "trip_class": trip_class_code,
        "passengers": passengers,
        "segments": segments,
        "signature": signature
    }

    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(init_url, json=payload, headers=headers, timeout=10)
        
        if response.status_code != 200:
            logger.error(f"API error: {response.status_code} - {response.text}")
            return {}
        
        search_id = response.json().get("search_id") or response.json().get("uuid")
        
        if not search_id:
            logger.error("No search_id returned from API")
            return {}
        
        logger.info(f"🔗 Search initiated: {search_id}")
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        return {}

    results_url = f"https://api.travelpayouts.com/v1/flight_search_results?uuid={search_id}"
    raw_proposals = []
    
    for attempt in range(5):
        try:
            time.sleep(3)
            results_response = requests.get(results_url, timeout=10)
            
            if results_response.status_code == 200:
                proposals_chunks = results_response.json()
                
                for chunk in proposals_chunks:
                    chunk_proposals = chunk.get("proposals", [])
                    if chunk_proposals:
                        raw_proposals.extend(chunk_proposals)
                
                if raw_proposals:
                    logger.info(f"✅ Got {len(raw_proposals)} proposals")
                    break
            else:
                logger.warning(f"Attempt {attempt+1}: Status {results_response.status_code}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Polling failed: {e}")
            
    if not raw_proposals:
        logger.warning("No results after polling")
        return {}

    deep_link_map = {}
    
    for proposal in raw_proposals:
        
        segments_data = proposal.get("segment", [])
        if not segments_data:
            continue

        outbound_segment = segments_data[0]
        outbound_flights = outbound_segment.get("flight", [])
        if not outbound_flights:
            continue

        first_flight = outbound_flights[0]
        
        airline = first_flight.get("marketing_carrier", "Unknown")

        raw_date = first_flight.get("departure_date", "")
        raw_time = first_flight.get("departure_time", "")
        
        depart_datetime = standardize_api_datetime(raw_date, raw_time)

        match_key = f"{airline}_{depart_datetime}"
        
        terms = proposal.get("terms", {})
        
        for gate_id, term_data in terms.items():
            price = term_data.get("price")
            currency = term_data.get("currency")
            raw_url = term_data.get("deep_link", "")
            booking_link = ""
            
            if raw_url and isinstance(raw_url, str) and raw_url.startswith("http"):
                if AFFILIATE_MARKER and "marker=" not in raw_url:
                    separator = "&" if "?" in raw_url else "?"
                    booking_link = f"{raw_url}{separator}marker={AFFILIATE_MARKER}"
                else:
                    booking_link = raw_url
                
            else:
              # *** FIX: Use the configured HOST instead of hardcoded aviasales.com ***
              # *** Now using urlencode for robust URL parameter handling ***
            
                last_flight = outbound_flights[-1]
                origin = first_flight.get("departure", "")
                destination = last_flight.get("arrival", "")
            
            # 1. Build the Travelpayouts search code
                search_code = f"{origin}{to_ddmm(date_from_str)}{destination}"
            
                if trip_type == "round-trip" and date_to_str:
                    search_code += to_ddmm(date_to_str)
            
            # 2. Collect all URL parameters into a dictionary
                params = {
                    "marker": AFFILIATE_MARKER,
                    "adults": passengers['adults'],
                    "children": passengers['children'],
                    "infants": passengers['infants'],
                    "trip_class": trip_class_code,
                    "gate_id": gate_id,
                }
            
                if direct_only:
                    params["transfers"] = 0
                    params["direct"] = "true" 
            
            # 3. Encode parameters into a URL-safe string
            # IMPORTANT: Ensure 'from urllib.parse import urlencode' is at the top of the file.
                    query_string = urlencode(params)

                    # 4. Construct the final internal link using the encoded string
                    booking_link = (
                      f"http://{HOST}/search/{search_code}?{query_string}" 
                    )

            
            if match_key not in deep_link_map or (price is not None and price < deep_link_map[match_key].get('price', float('inf'))):
                
                if booking_link and price is not None:
                    deep_link_map[match_key] = {
                        'link': booking_link,
                        'price': price,
                        'currency': currency,
                        'vendor_gate_id': gate_id,
                    }
                
    logger.info(f"Generated deep link map with {len(deep_link_map)} unique links.")
    
    return deep_link_map

def get_combined_flight_results(amadeus_flights: List[Dict], travelpayouts_link_map: Dict) -> List[Dict]:
    final_flights = []
    
    logger.info(f"Starting merge process. Amadeus flights: {len(amadeus_flights)}. Deep links available: {len(travelpayouts_link_map)}.")

    logger.debug(f"Deep Link Map Keys: {list(travelpayouts_link_map.keys())}") 

    for amadeus_flight in amadeus_flights:
        
        carrier = amadeus_flight.get("airline", "XX")
        depart_time = amadeus_flight.get("depart", "") 
        match_key = f"{carrier}_{depart_time}"
        
        logger.info(f"🔑 AMADEUS KEY: '{match_key}' (Length: {len(match_key)})")

        if match_key in travelpayouts_link_map:
            link_data = travelpayouts_link_map[match_key]
            
            amadeus_flight["link"] = link_data["link"]
            amadeus_flight["deeplink"] = link_data["link"]
            amadeus_flight["vendor"] = link_data.get("vendor_gate_id", "Travelpayouts")
            
            final_flights.append(amadeus_flight)
            logger.info(f"✅ Q2 Solved: Found Deep Link for {match_key}. Link starts with: {link_data['link'][:50]}...")
            
        else:
            final_flights.append(amadeus_flight) 
            logger.warning(f"❌ Fallback: No deep link match found for {match_key}. Using generic search link.")
            
    return final_flights

def search_flights_mock(origin_code, destination_code, date_from_str, date_to_str, trip_type, limit=None, direct_only=False):
    from mock_data import mock_kiwi_response
    
    try:
        date_from = datetime.strptime(date_from_str, "%Y-%m-%d").date()
        date_to = datetime.strptime(date_to_str, "%Y-%m-%d").date() if date_to_str else None
    except ValueError:
        logger.error("Invalid date format")
        return []

    flights = mock_kiwi_response()
    filtered = []

    for flight in flights:
        if flight.get("origin") != origin_code or flight.get("destination") != destination_code:
            continue
        
        departure_date = flight.get("departure").date() if flight.get("departure") else None
        if not departure_date or departure_date != date_from:
            continue
        
        if date_to:
            return_date = flight.get("return").date() if flight.get("return") else None
            if not return_date or return_date != date_to:
                continue
        
        deep_link = flight.get("deep_link", "")
        if not deep_link or not deep_link.startswith("http"):
            continue
        
        filtered.append({
            "id": generate_flight_id(deep_link, flight.get("airlines", ["Unknown"])[0], str(flight.get("departure"))),
            "airline": flight.get("airlines", ["Unknown"])[0],
            "flight_number": flight.get("flight_number", "N/A"),
            "depart": flight.get("departure").strftime("%Y-%m-%d %H:%M") if flight.get("departure") else "",
            "return": flight.get("return").strftime("%Y-%m-%d %H:%M") if flight.get("return") else "",
            "duration": flight.get("duration", "N/A"),
            "stops": flight.get("stops", 0),
            "cabin_class": flight.get("cabin_class", "Economy"),
            "price": flight.get("price"),
            "currency": "EUR",
            "vendor": flight.get("vendor", "MockVendor"),
            "link": deep_link,
            "trip_type": trip_type
        })
    
    filtered.sort(key=lambda x: x.get("price", float("inf")))
    return filtered[:limit or FEATURED_FLIGHT_LIMIT]