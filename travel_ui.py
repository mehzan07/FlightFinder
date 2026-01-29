from flask import Blueprint, redirect, render_template, request, jsonify, url_for, session
import requests
from travel import travel_chatbot
from datetime import datetime
import config  # Simple and clean

from urllib.parse import urlparse  # Required for cleaning the 404 links

# Then use it like this:
if config.IS_LOCAL:
    print("Running locally")

limit = config.FEATURED_FLIGHT_LIMIT


import json
import traceback
import os
from utils import get_city_name, get_airline_name

# Database imports commented out as requested
# from database import db
# from models import Booking, db
# from db import save_booking

from utils import extract_travel_entities, extract_iata, build_flight_deeplink
from flight_search import get_combined_flight_results, search_flights as search_flights_func
from iata_codes import city_to_iata
from travel import generate_booking_reference, travel_form_handler

from urllib.parse import urlencode 
from config import get_logger, AFFILIATE_MARKER, API_TOKEN
logger = get_logger(__name__)

from dotenv import load_dotenv
load_dotenv()

offers_db = {}
travel_bp = Blueprint("travel", __name__) 

# === Helper Functions ===

def format_datetime(dt_str):
    try:
        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
        return dt.strftime("%b %d, %H:%M")
    except Exception:
        return "Not available"

def format_time_only(dt_str):
    try:
        if ' ' in dt_str:
            return dt_str.split(' ')[1][:5]
        return dt_str
    except Exception:
        return "--:--"

def format_date_only(dt_str):
    try:
        if ' ' in dt_str:
            return dt_str.split(' ')[0]
        return dt_str
    except Exception:
        return ""

def is_token_match(token, airport):
    return (
        airport["city"].lower().startswith(token) or
        airport["name"].lower().startswith(token) or
        airport["iata"].lower().startswith(token)
    )

# === Routes ===

@travel_bp.route("/travel-ui", methods=["GET", "POST"])
def travel_ui():
    """Main entry point for travel search form and results display"""
    logger.info("travel_ui route hit")
    form_data = {}
    flights = []
    errors = []

    if request.method == "POST":
        limit = int(request.form.get("limit", 4))
        origin_code = request.form.get("origin_code", "").strip()
        destination_code = request.form.get("destination_code", "").strip()
        date_from_raw = request.form.get("date_from", "").strip()
        date_to_raw = request.form.get("date_to", "").strip()
        passengers_raw = request.form.get("passengers", "1").strip()
        cabin_class = request.form.get("cabin_class", "economy").strip()
        trip_type = request.form.get("trip_type", "round-trip").strip()
        direct_only = request.form.get("direct_only") == "on"

        form_data = request.form.copy()
        form_data["direct_only"] = direct_only

        if not origin_code: errors.append("Origin airport is required.")
        if not destination_code: errors.append("Destination airport is required.")
        if not date_from_raw: errors.append("Departure date is required.")
        if trip_type == "one-way":
        # One-Way URL: No return date allowed
            aviasales_url = f"https://www.aviasales.com/search/{origin}{date_from_formatted}{destination}1"
        else:
            # Round-Trip URL: Must include return date
            aviasales_url = f"https://www.aviasales.com/search/{origin}{date_from_formatted}{destination}{date_to_formatted}1"

        if errors:
            return render_template("travel_form.html", errors=errors, form_data=form_data)

        user_input = f"Fly from {origin_code} to {destination_code} from {date_from_raw}"
        
        try:
            result = travel_chatbot(user_input, trip_type=trip_type, limit=limit, direct_only=direct_only)
            offers_db.clear()
            trip_info = result.get("trip_info", {})
            flights = result.get("flights", [])

            for pf in flights:
                pf["origin"] = trip_info.get("origin", origin_code)
                pf["destination"] = trip_info.get("destination", destination_code)
                if pf.get("depart"):
                    pf["depart_formatted"] = format_datetime(pf["depart"])
                    pf["depart_time"] = format_time_only(pf["depart"])
                    pf["depart_date"] = format_date_only(pf["depart"])
                offers_db[pf["id"]] = pf

            return render_template(
                "search_results.html",
                flights=flights[:limit],
                origin=origin_code,
                destination=destination_code,
                depart_date=date_from_raw,
                return_date=date_to_raw if trip_type == "round-trip" else None,
                currency="EUR",
                direct_only=direct_only,
                message=result.get("message"),
                summary=result.get("summary"),
                trip_info=trip_info
            )
        except Exception as e:
            logger.error(f"Error: {e}")
            return render_template("travel_form.html", errors=[str(e)], form_data=form_data)

    return render_template("travel_form.html", form_data=form_data, flights=flights, errors=errors)



@travel_bp.route("/search-flights", methods=["POST"])
def search_flights():
    """Handler for the flight search form submission"""
    logger.info("search_flights route hit")
    
    # 1. Get Form Data
    origin_raw = extract_iata(request.form.get("origin_code", ""))
    dest1_raw = extract_iata(request.form.get("destination_code", ""))
    dest2_raw = extract_iata(request.form.get("destination_code_2", ""))
    
    depart_date = request.form.get("date_from", "")
    depart_date_2 = request.form.get("date_from_2")
    return_date = request.form.get("date_to", "")
    trip_type = request.form.get("trip_type", "round-trip")
    passengers = request.form.get("passengers", "1")
    cabin_class = request.form.get("cabin_class", "economy")
    
    limit = int(request.form.get("limit", config.FEATURED_FLIGHT_LIMIT))
    direct_only = request.form.get("direct_only") == "on"

    # 2. Display Names for Header
    display_origin = get_city_name(origin_raw)
    display_dest1 = get_city_name(dest1_raw)
    display_dest2 = get_city_name(dest2_raw) if dest2_raw else None

    if not origin_raw or not dest1_raw or not depart_date:
        return render_template("travel_form.html", 
                               errors=["Please provide origin, destination, and departure date"],
                               form_data=request.form)

    try:
        # 3. Perform the API Search
        flights = search_flights_func(
            origin_raw, dest1_raw, depart_date,
            return_date if trip_type == "round-trip" else None,
            trip_type=trip_type, adults=int(passengers),
            cabin_class=cabin_class, limit=limit, direct_only=direct_only
        )

        safe_flights = []

        # 4. Process Each Flight for the Template
        for flight in flights:
            if isinstance(flight, dict):
                # A. Inject basic trip data
                flight["trip_type"] = trip_type
                flight["passengers"] = passengers
                
                # B. CAPTURE AND CLEAN AIRLINE CODE
                # We check multiple possible keys from different APIs
                raw_code = (
                    flight.get("airline_code") or 
                    flight.get("airline") or 
                    flight.get("carrierCode") or 
                    "XX"
                )
                clean_code = str(raw_code).strip().upper()[:2]
                flight["airline_code"] = clean_code

                # C. DEFINE AIRLINE DISPLAY (The translation step)
                # This adds the 'airline_display' key to the flight dictionary
                flight["airline_display"] = get_airline_name(clean_code)

                # D. Handle Multi-City specific data
                if trip_type in ['multi-city', 'multi_city']:
                    flight["origin_2"] = request.form.get("origin_code_2")
                    flight["destination_2"] = request.form.get("destination_code_2")
                    flight["depart_date_2"] = request.form.get("date_from_2")

                # E. REBUILD AND CLEAN DEEPLINK (Fixes the 404 error)
                raw_link = build_flight_deeplink(flight, config.AFFILIATE_MARKER)
                parsed = urlparse(raw_link)
                clean_link = parsed.path
                if parsed.query:
                    clean_link += f"?{parsed.query}"
                
                if not clean_link.startswith("/"):
                    clean_link = "/" + clean_link

                flight["deeplink"] = clean_link
                safe_flights.append(flight)
        
        # 5. Render Template with Processed Data
        return render_template(
            "search_results.html",
            flights=safe_flights[:limit],
            origin=display_origin,
            destination=display_dest1,
            destination_2=display_dest2,  
            depart_date=depart_date,
            depart_date_2=depart_date_2,    
            return_date=return_date,
            trip_type=trip_type,
            currency="SEK",  # Hardcoded for your requirement
            direct_only=direct_only
        )

    except Exception as e:
        logger.error(f"Search error: {traceback.format_exc()}")
        return render_template("travel_form.html", 
                               errors=[f"Search failed: {str(e)}"], 
                               form_data=request.form)

@travel_bp.route('/flights/results', methods=['GET'])
def flight_results():
    # 1. Capture inputs
    origin = request.args.get('origin', '').upper()
    destination = request.args.get('destination', '').upper()
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    trip_type = request.args.get('trip_type', 'one-way')
    origin_2 = request.args.get('origin_2', '').upper()
   # destination_2 = request.args.get('destination_2', '').upper()
    destination_2 = (request.form.get('destination_code_2') or request.args.get('destination_2')).upper()
    date_from_2 = request.args.get('date_from_2')
    
    currency = request.args.get('currency', 'EUR')
    adults = request.args.get('adults', type=int) or 1

    if not all([origin, destination, date_from]):
        return redirect('/')

    try:
        # 2. Call your search logic
        final_flights = get_combined_flight_results(
            origin_code=origin,
            destination_code=destination,
            date_from_str=date_from,
            date_to_str=date_to,
            adults=adults
        )

        # 3. THE FIX: Process results (Logic from commit 4e0f30e)
        processed_flights = []
        for flight in final_flights:
            if isinstance(flight, dict):
                # Ensure trip info is attached for the UI labels
                flight["origin"] = origin
                flight["destination"] = destination
                flight["trip_type"] = trip_type

                # Handle Multi-City data injection
                if trip_type == 'multi-city':
                    flight["origin_2"] = origin_2 if origin_2 else destination
                    flight["destination_2"] = destination_2
                    flight["depart_date_2"] = date_from_2
                
                # Re-build the deeplink with the full data
                # marker is imported from utils
                flight["deeplink"] = build_flight_deeplink(flight, marker, currency)
                
                processed_flights.append(flight)

        # 4. Render with explicit variables for the Header
        return render_template(
            'search_results.html', 
            flights=processed_flights,
            origin=origin,
            destination=destination,
            destination_2=destination_2,
            depart_date=date_from,
            return_date=date_to if trip_type == 'round-trip' else None,
            trip_type=trip_type,
            currency=currency
        )

    except Exception as e:
        logger.error(f"Flight search route failed: {e}")
        return render_template('search_results.html', error=f"Error: {e}", flights=[])
    
    
    
@travel_bp.route('/search/<path:search_code>')
def redirect_to_aviasales(search_code):
    raw_qs = request.query_string.decode('utf-8')
    
    if search_code == "multi":
        # Multi-city MUST go to search.aviasales.com/flights/ with segments
        target_url = f"https://search.aviasales.com/flights/?{raw_qs}"
    else:
        # Standard one-way/round-trip
        target_url = f"https://www.aviasales.com/search/{search_code}?{raw_qs}"
        
    return redirect(target_url)
 

@travel_bp.route("/book-flight")
def book_flight():
    """
    Safely captures the booking URL and airline info, then shows the loading page.
    """
    # Use .get() with defaults to prevent KeyErrors which can cause 500/502 errors
    target_url = request.args.get("url", "")
    destination_name = request.args.get("dest", "your destination")
    airline_name = request.args.get("airline", "our partner")
    
    if not target_url:
        logger.error("book_flight called without a target URL")
        return redirect(url_for("travel.travel_ui"))

    return render_template("redirect.html", 
                           url=target_url, 
                           destination=destination_name, 
                           airline=airline_name)

@travel_bp.route("/autocomplete-airports")
def autocomplete_airports():
    query = request.args.get("query", "").strip().lower()
    try:
        with open("airports.json", "r", encoding="utf-8") as f:
            airports = json.load(f)
        tokens = query.split()
        matches = [a for a in airports if any(is_token_match(t, a) for t in tokens)]
        return jsonify([{"value": f'{a["city"]} ({a["iata"]})', "label": f'{a["name"]} — {a["city"]} ({a["iata"]})'} for a in matches])
    except: return jsonify([])

@travel_bp.route("/finalize-booking", methods=["GET", "POST"])
def finalize_booking():
    flight = session.get("flight", {})
    passenger = session.get("passenger", {})
    reference = generate_booking_reference()
    # save_booking(reference, passenger, json.dumps(flight)) # DB Commented
    return render_template("booking_success.html", reference=reference, passenger=passenger, flight=flight)

@travel_bp.route("/booking-history", methods=["GET"])
def booking_history():
    return render_template("booking_history.html", bookings=[])

@travel_bp.route("/", methods=["GET"])
def home_page():
    return redirect(url_for("travel.travel_ui"))

@travel_bp.route("/flightfinder", methods=["GET", "POST"])
def flightfinder():
    return redirect(url_for("travel.travel_ui"))



@travel_bp.route('/search-airports')
def search_airports():
    logger.info("search_airports route hit")
    query = request.args.get('term', '')
    if len(query) < 2:
        return jsonify([])
    
    # Your server makes the request (No CORS issues here)
    url = f"https://autocomplete.travelpayouts.com/places2?term={query}&locale=en&types[]=city&types[]=airport"
    try:
        response = requests.get(url, timeout=5)
        return jsonify(response.json())
    except Exception as e:
        print(f"Autocomplete Error: {e}")
        return jsonify([])
    
    

@travel_bp.route("/health", methods=["GET"])
def health():
    return jsonify({'status': 'ok', 'timestamp': datetime.utcnow().isoformat(), 'service': 'FlightFinder'})