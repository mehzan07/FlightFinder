from datetime import datetime
import requests
#import os
#from dotenv import load_dotenv
from mock_data import mock_kiwi_response
import time
import json
import hashlib

#load_dotenv()
from config import get_logger
logger = get_logger(__name__)

from config import AFFILIATE_MARKER, API_TOKEN,HOST,USER_IP,USE_REAL_API, FEATURED_FLIGHT_LIMIT,DEBUG_MODE


def search_flights(origin_code, destination_code, date_from_str, date_to_str, trip_type, adults=1, children=0,infants=0, cabin_class="economy", limit=None, direct_only=False):
    if USE_REAL_API:
        return search_flights_api(origin_code, destination_code, date_from_str, date_to_str, trip_type, adults, children, infants, cabin_class,limit=limit, direct_only=direct_only)
    else:
        return search_flights_mock(origin_code, destination_code, date_from_str, date_to_str, trip_type,limit=limit, direct_only=direct_only)

def map_cabin_class(cabin_class):
    return {
        "economy": "Y",
        "business": "C",
        "first": "F"
    }.get(cabin_class.lower(), "Y")

def generate_flight_id(link, airline, departure):
    raw = f"{airline}_{departure}_{link}"
    return hashlib.md5(raw.encode()).hexdigest()

def generate_signature(token, marker, host, user_ip, locale, trip_class, passengers, segments):
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
    print("🔐 Raw signature string:", raw_string)
    # Hash it
    return hashlib.md5(raw_string.encode("utf-8")).hexdigest()

def search_flights_api(origin_code, destination_code, date_from_str, date_to_str=None, trip_type="round-trip", adults=1, children=0, infants=0, cabin_class="economy", limit=None, direct_only=False):
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
        print(f"🧭 Trip type: {trip_type}")
        print(f"🧳 Segments sent: {json.dumps(segments, indent=2)}")

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
    print("🔑 signature:", signature)

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

    print(f"🌐 Initiating search: {init_url}")
    print("📦 Final JSON payload:")
    print(json.dumps(payload, indent=2))

    try:
        if DEBUG_MODE:
            print("\n📤 Sending POST request to Travelpayouts API")
            print(f"🔗 Endpoint: {init_url}")
            print("🧾 Headers:")
            print(headers)
            print("📦 Payload:")
            print(json.dumps(payload, indent=2))

        response = requests.post(init_url, json=payload, headers=headers)
        if response.status_code != 200:
            print(f"❌ API error: {response.status_code}")
            return []
        search_id = response.json().get("search_id") or response.json().get("uuid")
        print(f"🔗 search_id: {search_id}")
        if not search_id:
            print("❌ No search_id returned")
            return []
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return []

    results_url = f"https://api.travelpayouts.com/v1/flight_search_results?uuid={search_id}"
    print(f"📄 Polling results from: {results_url}")

    raw_proposals = []
    for attempt in range(5):
        try:
            time.sleep(3)
            results_response = requests.get(results_url)
            print(f"🔗 results_response.status_code: {results_response.status_code}")
            if results_response.status_code == 200:
                proposals_chunks = results_response.json()
                for chunk in proposals_chunks:
                    chunk_proposals = chunk.get("proposals", [])
                    if chunk_proposals:
                        raw_proposals.extend(chunk_proposals)
                if raw_proposals:
                    break
            else:
                print(f"⚠️ Attempt {attempt+1}: Status {results_response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"❌ Polling failed: {e}")
            return []
    else:
        print("❌ No results after polling")
        return []

    filtered = []
    print(f"\n🌐 API returned {len(raw_proposals)} proposals")

    for proposal in raw_proposals:
        terms = proposal.get("terms", {})
        for gate_id, term_data in terms.items():
            price = term_data.get("price")
            currency = term_data.get("currency")
            

            raw_url = term_data.get("deep_link") or term_data.get("url")

            if isinstance(raw_url, str) and raw_url.startswith("http"):
                booking_link = raw_url
                print(f"🔗 Final booking link: {booking_link}")
            elif isinstance(raw_url, int) or (isinstance(raw_url, str) and raw_url.isdigit()):
                booking_link = f"https://www.travelpayouts.com/redirect/{raw_url}"
                print(f"🔗 Final booking link: {booking_link}") 
            else:
                if DEBUG_MODE:
                    print(f"⛔ Skipping invalid booking link: {raw_url}")
                continue
            
            segment = proposal.get("segment", [])
            all_flights = []
            for seg in segment:
                all_flights.extend(seg.get("flight", []))

            if not all_flights:
                continue

            first_leg = all_flights[0]
            last_leg = all_flights[-1] if len(all_flights) > 1 else first_leg

            airline = first_leg.get("marketing_carrier", "Unknown")
            flight_number = first_leg.get("number", "Not available")
            departure = f"{first_leg.get('departure_date', '')} {first_leg.get('departure_time', '')}".strip()
            arrival = f"{last_leg.get('arrival_date', '')} {last_leg.get('arrival_time', '')}".strip()
            origin = first_leg.get("departure", "")
            destination = last_leg.get("arrival", "")
            duration = sum(f.get("duration", 0) for f in all_flights)
            stops = len(all_flights) - 1

            if not booking_link or not departure or not price:
                if DEBUG_MODE:
                    print("⛔ Skipping incomplete proposal")
                continue

            filtered.append({
                "id": generate_flight_id(booking_link, airline, departure),
                "airline": airline or "Airline not specified",
                "flight_number": flight_number or "Not available",
                "depart": departure,
                "return": arrival,
                "origin": origin,
                "destination": destination,
                "duration": duration,
                "stops": stops,
                "price": price,
                "currency": currency,
                "vendor": "Travelpayouts",
                "link": booking_link,
                "trip_type": trip_type,
                "cabin_class": cabin_class
            })

    if direct_only:
        filtered = [f for f in filtered if f.get("stops", 0) == 0]

    if not filtered:
        print("\n⚠️ No flights matched the criteria.")
        return []

    filtered.sort(key=lambda x: x.get("price", float("inf")))
    limit = limit or FEATURED_FLIGHT_LIMIT
    featured_flights = filtered[:limit]

    print(f"\n🎯 Total matching flights from API: {len(filtered)}")
    print(f"🌟 Featured (top {FEATURED_FLIGHT_LIMIT} cheapest):")
    for flight in featured_flights:
        print(f"\n  ✈️   {flight}")

    return featured_flights











# this function is only for demo
def search_flights_mock(origin_code, destination_code, date_from_str, date_to_str, trip_type, limit=None, only_direct=False):
    try:
        date_from = datetime.strptime(date_from_str, "%Y-%m-%d").date()
        date_to = datetime.strptime(date_to_str, "%Y-%m-%d").date() if date_to_str else None
    except ValueError:
        print("❌ Invalid date format. Use YYYY-MM-DD.")
        return []

    flights = mock_kiwi_response()
    filtered = []
    skipped_flights = []

    print(f"\n🔍 Searching flights from {origin_code} to {destination_code}")
    print(f"📅 Departure date: {date_from}" + (f" | Return date: {date_to}" if date_to else " (One-way trip)"))

    for flight in flights:
        flight_origin = flight.get("origin")
        flight_destination = flight.get("destination")
        departure_date = flight.get("departure").date() if flight.get("departure") else None
        return_date = flight.get("return").date() if trip_type == "round-trip" and flight.get("return") else None
        flight_price = flight.get("price")
        deep_link = flight.get("deep_link")

        if flight_origin != origin_code or flight_destination != destination_code:
            continue
        if not departure_date or departure_date != date_from:
            continue
        if date_to and (not return_date or return_date != date_to):
            continue

        if not deep_link or not isinstance(deep_link, str) or deep_link.strip() == "":
            print(f"⚠️ Skipping flight with missing or invalid deep_link: {flight}")
            skipped_flights.append(flight)
            continue
        if not deep_link.startswith("http"):
            deep_link = "https://" + deep_link.strip()

        missing_fields = [key for key in ["flight_number", "duration", "stops", "cabin_class"] if key not in flight]
        if missing_fields:
            print(f"⚠️ Missing fields in flight {flight.get('id', 'Unknown')}: {missing_fields}")

        print(f"✅ Flight link: {deep_link}")

        filtered.append({
            "id": generate_flight_id(deep_link, flight.get("airlines", ["Unknown"])[0], flight.get("departure")),
            "airlines": flight.get("airlines", ["Unknown"]),
            "flight_number": flight.get("flight_number", "N/A"),
            "duration": flight.get("duration", "N/A"),
            "stops": flight.get("stops", 0),
            "cabin_class": flight.get("cabin_class", "Economy"),
            "price": flight_price,
            "departure": flight.get("departure"),
            "return": flight.get("return") if trip_type == "round-trip" else None,
            "vendor": flight.get("vendor", "MockVendor"),
            "deep_link": deep_link,
            "trip_type": trip_type
        })  
    print(f"\n🎯 Total matching flights: {len(filtered)}")
    filtered.sort(key=lambda x: x.get("price", float("inf")))
    featured_flights = filtered[:limit or FEATURED_FLIGHT_LIMIT]

    if skipped_flights:
            print(f"\n🚫 Total skipped flights due to invalid deep_link: {len(skipped_flights)}")
            for i, f in enumerate(skipped_flights, 1):
                print(f"{i}. {f}")
                
    print(f"\n🎯 Total featured_flights: {len(featured_flights)}")
                
    return featured_flights