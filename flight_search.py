# flight_search.py:
from datetime import datetime
import requests
import time
import hashlib
import json as json_module
import traceback # ✅ FIX: Added missing import

from config import get_logger
logs = get_logger(__name__)
# The logger instance is named 'logs' here, but 'logger' is used below.
# Assuming 'logger = logs' is intended or implicit for the rest of the file.
logger = logs # Added to prevent NameError if logs is not used later

from config import AFFILIATE_MARKER, API_TOKEN, HOST, USER_IP, USE_REAL_API, FEATURED_FLIGHT_LIMIT, DEBUG_MODE

from config import USE_AMADEUS, AMADEUS_API_KEY

# Import Amadeus if available
AMADEUS_AVAILABLE = False
if USE_AMADEUS and AMADEUS_API_KEY:
    try:
        from amadeus_search import search_flights_amadeus
        AMADEUS_AVAILABLE = True
        logger.info("✅ Amadeus module loaded")
    except ImportError as e:
        logger.warning(f"Amadeus module not available: {e}")

# At the very top, after imports
FORCE_AMADEUS = True  # ✅ Add this line

def search_flights(origin_code, destination_code, date_from_str, date_to_str, 
                   trip_type, adults=1, children=0, infants=0, cabin_class="economy", 
                   limit=None, direct_only=False):
    """Main entry point for flight search"""
    
    # Force Amadeus for debugging
    if FORCE_AMADEUS:  # ✅ Change this line
        logger.info("🔍 FORCING Amadeus API")
        try:
            from amadeus_search import search_flights_amadeus
            flights = search_flights_amadeus(
                origin=origin_code,
                destination=destination_code,
                date_from=date_from_str,
                date_to=date_to_str,
                trip_type=trip_type,
                adults=adults,
                children=children,
                infants=infants,
                cabin_class=cabin_class,
                limit=limit,
                direct_only=direct_only
            )
            
            if flights:
                logger.info(f"✅ Amadeus returned {len(flights)} flights")
                return flights
            else:
                logger.warning("⚠️ Amadeus returned empty")
        except Exception as e:
            logger.error(f"❌ Amadeus ERROR: {e}")
            import traceback # ✅ FIX: Typo corrected (was 'Import Traceback')
            traceback.print_exc()
    
    # Original code continues...
    
    # Fallback to Travelpayouts
    logger.info("🔍 Using Travelpayouts API")
    if USE_REAL_API:
        return search_flights_api(origin_code, destination_code, date_from_str, date_to_str, trip_type, adults, children, infants, cabin_class, limit=limit, direct_only=direct_only)
    else:
        return search_flights_mock(origin_code, destination_code, date_from_str, date_to_str, trip_type, limit=limit, direct_only=direct_only)


# ... (rest of the file is unchanged)



def map_cabin_class(cabin_class):
    """Convert cabin class names to API codes"""
    return {
        "economy": "Y",
        "business": "C",
        "first": "F"
    }.get(cabin_class.lower(), "Y")


def generate_flight_id(link, airline, departure):
    """Generate unique flight ID"""
    raw = f"{airline}_{departure}_{link}"
    return hashlib.md5(raw.encode()).hexdigest()


def format_flight_datetime(date_str, time_str):
    """
    Convert API date/time strings to standardized format.
    
    API returns:
    - date: "2025-01-15" (YYYY-MM-DD)
    - time: "14:30" or "14:30:00" (HH:MM or HH:MM:SS)
    
    Returns: "2025-01-15 14:30" (YYYY-MM-DD HH:MM)
    """
    if not date_str or not time_str:
        return ""
    
    try:
        # Remove seconds if present
        time_parts = time_str.split(":")
        time_formatted = f"{time_parts[0]}:{time_parts[1]}"
        return f"{date_str} {time_formatted}"
    except Exception as e:
        logger.warning(f"Time formatting error: {e}")
        return f"{date_str} {time_str}"


def calculate_duration_minutes(all_flights):
    """Calculate total flight duration in minutes"""
    total = sum(f.get("duration", 0) for f in all_flights)
    return total


def format_duration(minutes):
    """Convert minutes to human-readable format (e.g., '5h 30m')"""
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
    """Generate MD5 signature for API authentication"""
    outbound = segments[0]

    if len(segments) == 1:
        # One-way format
        raw_string = (
            f"{token}:{host}:{locale}:{marker}:"
            f"{passengers['adults']}:{passengers['children']}:{passengers['infants']}:"
            f"{outbound['date']}:{outbound['destination']}:{outbound['origin']}:"
            f"{trip_class}:{user_ip}"
        )
    else:
        # Round-trip format
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
    """Search real-time flights using Travelpayouts API"""
    
    init_url = "https://api.travelpayouts.com/v1/flight_search"

    # Build segments
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
    
    if DEBUG_MODE:
        print(f"🧭 Trip type: {trip_type}")
        print(f"🧳 Segments: {json_module.dumps(segments, indent=2)}")

    # Prepare passengers
    passengers = {
        "adults": int(adults),
        "children": int(children),
        "infants": int(infants)
    }
    
    trip_class_code = map_cabin_class(cabin_class)

    # Generate signature
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

    # Build payload
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

    if DEBUG_MODE:
        print(f"\n📤 POST {init_url}")
        print(f"📦 Payload: {json_module.dumps(payload, indent=2)}")

    # Initiate search
    try:
        response = requests.post(init_url, json=payload, headers=headers, timeout=10)
        
        if response.status_code != 200:
            logger.error(f"API error: {response.status_code} - {response.text}")
            return []
        
        search_id = response.json().get("search_id") or response.json().get("uuid")
        
        if not search_id:
            logger.error("No search_id returned from API")
            return []
        
        logger.info(f"🔗 Search initiated: {search_id}")
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        return []

    # Poll for results
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
        return []

    # Parse proposals
    filtered = []
    
    if DEBUG_MODE:
        logger.info("=" * 60)
        logger.info("SAMPLE PROPOSAL (first one):")
        if raw_proposals:
            logger.info(json_module.dumps(raw_proposals[0], indent=2))
        logger.info("=" * 60)
    
    for proposal in raw_proposals:
        terms = proposal.get("terms", {})
        
        for gate_id, term_data in terms.items():
            price = term_data.get("price")
            currency = term_data.get("currency")
            
            # Get booking link
            raw_url = term_data.get("deep_link", "")
            
            if raw_url and isinstance(raw_url, str) and raw_url.startswith("http"):
                # API provided a link - use it
                if AFFILIATE_MARKER and "marker=" not in raw_url:
                    separator = "&" if "?" in raw_url else "?"
                    booking_link = f"{raw_url}{separator}marker={AFFILIATE_MARKER}"
                else:
                    booking_link = raw_url
                
                if DEBUG_MODE:
                    logger.info(f"🔗 Using API deep_link: {booking_link}")
            else:
                # API didn't provide link - build it manually
                if DEBUG_MODE:
                    logger.debug(f"No deep_link for gate {gate_id}, building manually")
                
                # Get flight details to build link
                segment = proposal.get("segment", [])
                if not segment:
                    continue
                
                outbound = segment[0]
                outbound_flights = outbound.get("flight", [])
                if not outbound_flights:
                    continue
                
                first_flight = outbound_flights[0]
                last_flight = outbound_flights[-1]
                
                # Build search code: ORIGIN+DDMM+DESTINATION+DDMM (for round-trip)
                origin = first_flight.get("departure", "")
                destination = last_flight.get("arrival", "")
                depart_date = first_flight.get("departure_date", "")
                depart_time = first_flight.get("departure_time", "")
                
                # Format date to DDMM
                def to_ddmm(date_str):
                    if not date_str or len(date_str) < 10:
                        return ""
                    return date_str[8:10] + date_str[5:7]  # YYYY-MM-DD -> DDMM
                
                search_code = f"{origin}{to_ddmm(depart_date)}{destination}"
                
                # Add return date if round-trip
                if len(segment) > 1:
                    return_seg = segment[1]
                    return_flights = return_seg.get("flight", [])
                    if return_flights:
                        return_first = return_flights[0]
                        return_date = return_first.get("departure_date", "")
                        search_code += to_ddmm(return_date)
                
                # Build URL with ALL relevant parameters to preserve search
                booking_link = (
                    f"https://www.aviasales.com/search/{search_code}"
                    f"?marker={AFFILIATE_MARKER}"
                    f"&adults={passengers['adults']}"
                    f"&children={passengers['children']}"
                    f"&infants={passengers['infants']}"
                    f"&trip_class={trip_class_code}"
                )
                
                # Add gate_id to redirect to specific booking site
                if gate_id:
                    booking_link += f"&gate_id={gate_id}"
                
                # Add direct_only filter if requested
                if direct_only:
                    booking_link += "&transfers=0"
                    booking_link += "&direct=true"
                
                if DEBUG_MODE:
                    logger.info(f"🔨 Built manual link: {booking_link}")
            
            # Parse flight segments
            segments_data = proposal.get("segment", [])
            
            if not segments_data:
                continue
            
            # OUTBOUND FLIGHT (always exists)
            outbound_segment = segments_data[0]
            outbound_flights = outbound_segment.get("flight", [])
            
            if not outbound_flights:
                continue
            
            first_flight = outbound_flights[0]
            last_flight = outbound_flights[-1]
            
            # Extract outbound details
            airline = first_flight.get("marketing_carrier", "Unknown")
            flight_number = first_flight.get("number", "N/A")
            
            # FORMAT TIMES PROPERLY
            depart_datetime = format_flight_datetime(
                first_flight.get("departure_date", ""),
                first_flight.get("departure_time", "")
            )
            
            arrive_datetime = format_flight_datetime(
                last_flight.get("arrival_date", ""),
                last_flight.get("arrival_time", "")
            )
            
            origin = first_flight.get("departure", "")
            destination = last_flight.get("arrival", "")
            duration_minutes = calculate_duration_minutes(outbound_flights)
            stops = len(outbound_flights) - 1
            
            # RETURN FLIGHT (for round-trips)
            return_depart_datetime = None
            return_arrive_datetime = None
            
            if trip_type == "round-trip" and len(segments_data) > 1:
                return_segment = segments_data[1]
                return_flights = return_segment.get("flight", [])
                
                if return_flights:
                    return_first = return_flights[0]
                    return_last = return_flights[-1]
                    
                    return_depart_datetime = format_flight_datetime(
                        return_first.get("departure_date", ""),
                        return_first.get("departure_time", "")
                    )
                    
                    return_arrive_datetime = format_flight_datetime(
                        return_last.get("arrival_date", ""),
                        return_last.get("arrival_time", "")
                    )
            
            # Validate required fields
            if not booking_link or not depart_datetime or not price:
                if DEBUG_MODE:
                    logger.debug("⛔ Skipping incomplete proposal")
                continue
            
            # Build flight object
            flight_data = {
                "id": generate_flight_id(booking_link, airline, depart_datetime),
                "airline": airline,
                "flight_number": flight_number,
                "depart": depart_datetime,
                "return": return_arrive_datetime if trip_type == "round-trip" else arrive_datetime,
                "return_depart": return_depart_datetime,
                "origin": origin,
                "destination": destination,
                "duration": format_duration(duration_minutes),
                "duration_minutes": duration_minutes,
                "stops": stops,
                "price": price,
                "currency": currency,
                "vendor": "Travelpayouts",
                "link": booking_link,
                "trip_type": trip_type,
                "cabin_class": cabin_class
            }
            
            filtered.append(flight_data)
    
    # Apply filters
    if direct_only:
        filtered = [f for f in filtered if f.get("stops", 0) == 0]
    
    if not filtered:
        logger.warning("No flights matched criteria")
        return []
    
    # Sort by price
    filtered.sort(key=lambda x: x.get("price", float("inf")))
    
    # Limit results
    limit = limit or FEATURED_FLIGHT_LIMIT
    featured_flights = filtered[:limit]
    
    logger.info(f"🎯 Returning {len(featured_flights)} flights (from {len(filtered)} total)")
    
   # return featured_flights
    return deep_link_map # <-- CHANGE: Return the map for matching!

def search_flights_mock(origin_code, destination_code, date_from_str, date_to_str, trip_type, limit=None, direct_only=False):
    """Mock flight search for testing (uses mock_data.py)"""
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