from flask import Blueprint, redirect, render_template, request, jsonify, url_for, session
import requests
from travel import travel_chatbot
from datetime import datetime
from config import DEBUG_MODE, FEATURED_FLIGHT_LIMIT
import json
from database import db
import traceback
import os

from utils import extract_travel_entities
from flight_search import get_combined_flight_results, search_flights as search_flights_func
from iata_codes import city_to_iata

from travel import generate_booking_reference
from travel import travel_form_handler

from models import Booking, db
from db import save_booking

from utils import extract_iata
from utils import build_flight_deeplink

from urllib.parse import urlencode # You might need this for proper query string handling

from config import get_logger, AFFILIATE_MARKER, API_TOKEN
logger = get_logger(__name__)

import urllib.parse
from dotenv import load_dotenv
load_dotenv()

offers_db = {}
travel_bp = Blueprint("travel", __name__) 


def format_datetime(dt_str):
    """
    Format datetime string from 'YYYY-MM-DD HH:MM' to 'Mon DD, HH:MM'
    """
    try:
        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
        return dt.strftime("%b %d, %H:%M")
    except Exception:
        return "Not available"


def format_time_only(dt_str):
    """
    Extract just the time from 'YYYY-MM-DD HH:MM' format
    Returns: 'HH:MM'
    """
    try:
        if ' ' in dt_str:
            return dt_str.split(' ')[1][:5]  # Get HH:MM
        return dt_str
    except Exception:
        return "--:--"


def format_date_only(dt_str):
    """
    Extract just the date from 'YYYY-MM-DD HH:MM' format
    Returns: 'YYYY-MM-DD'
    """
    try:
        if ' ' in dt_str:
            return dt_str.split(' ')[0]
        return dt_str
    except Exception:
        return ""


def format_ddmm(date_str):
    """Convert YYYY-MM-DD to DDMM format for Aviasales deeplink."""
    try:
        return date_str[8:10] + date_str[5:7]
    except:
        return ""


# === Main Travel UI Route ===
@travel_bp.route("/travel-ui", methods=["GET", "POST"])
def travel_ui():
    """Main entry point for travel search form and results display"""
    logger.info("travel_ui route hit")
    logger.debug(f"Request method: {request.method}")

    # Initialize variables
    form_data = {}
    flights = []
    errors = []

    if request.method == "POST":
        limit = int(request.form.get("limit", 4))  # Changed default to 4
    else:
        limit = int(request.args.get("limit", 4))  # Changed default to 4

    if request.method == "POST":
        origin_code = request.form.get("origin_code", "").strip()
        destination_code = request.form.get("destination_code", "").strip()
        date_from_raw = request.form.get("date_from", "").strip()
        date_to_raw = request.form.get("date_to", "").strip()
        passengers_raw = request.form.get("passengers", "1").strip()
        cabin_class = request.form.get("cabin_class", "economy").strip()
        trip_type = request.form.get("trip_type", "round-trip").strip()
        direct_only = request.form.get("direct_only") == "on"

        # Validate inputs
        errors = []
        if trip_type != "one-way" and not date_to_raw:
            errors.append("Return date is required for round-trip.")

        form_data = request.form.copy()
        form_data["direct_only"] = direct_only

        date_from = date_to = None
        if not origin_code:
            errors.append("Origin airport is required.")
        if not destination_code:
            errors.append("Destination airport is required.")
        if not date_from_raw:
            errors.append("Departure date is required.")
        if trip_type != "one-way" and not date_to_raw:
            errors.append("Return date is required for round-trip.")
        if not cabin_class:
            errors.append("Cabin class is required.")

        try:
            date_from = datetime.strptime(date_from_raw, "%Y-%m-%d")
        except ValueError:
            errors.append("Invalid departure date format.")

        if trip_type != "one-way" and date_to_raw:
            try:
                date_to = datetime.strptime(date_to_raw, "%Y-%m-%d")
                if date_from and date_to and date_from > date_to:
                    errors.append("Return date must be after departure date.")
            except ValueError:
                errors.append("Invalid return date format.")

        try:
            passengers = int(passengers_raw)
            if passengers < 1:
                errors.append("Number of passengers must be at least 1.")
        except ValueError:
            errors.append("Invalid number of passengers.")
            passengers = 1

        if errors:
            return render_template("travel_form.html", errors=errors, form_data=form_data)

        # Build user input string
        if trip_type == "one-way":
            user_input = (
                f"Fly one-way from {origin_code} to {destination_code} on {date_from_raw} "
                f"for {passengers} passengers in {cabin_class} class via {origin_code} to {destination_code}"
            )
        else:
            user_input = (
                f"Fly from {origin_code} to {destination_code} from {date_from_raw} to {date_to_raw} "
                f"for {passengers} passengers in {cabin_class} class via {origin_code} to {destination_code}"
            )

        # Search flights
        try:
            result = travel_chatbot(user_input, trip_type=trip_type, limit=limit, direct_only=direct_only)
        except Exception as e:
            error_msg = f"WARNING: Something went wrong while processing your request: {str(e)}"
            logger.error(f"Error in travel_chatbot: {e}")
            return render_template("travel_form.html", errors=[error_msg], form_data=form_data)

        # Process results
        offers_db.clear()
        trip_info = result.get("trip_info", {})
        flights = result.get("flights", [])

        # Format flight times for display
        for prepared_flight in flights:
            prepared_flight["origin"] = trip_info.get("origin", origin_code)
            prepared_flight["destination"] = trip_info.get("destination", destination_code)
            
            # Format departure and arrival times
            if prepared_flight.get("depart"):
                prepared_flight["depart_formatted"] = format_datetime(prepared_flight["depart"])
                prepared_flight["depart_time"] = format_time_only(prepared_flight["depart"])
                prepared_flight["depart_date"] = format_date_only(prepared_flight["depart"])
            
            if prepared_flight.get("return"):
                prepared_flight["return_formatted"] = format_datetime(prepared_flight["return"])
                prepared_flight["return_time"] = format_time_only(prepared_flight["return"])
                prepared_flight["return_date"] = format_date_only(prepared_flight["return"])
            
            if prepared_flight.get("return_depart"):
                prepared_flight["return_depart_time"] = format_time_only(prepared_flight["return_depart"])
                prepared_flight["return_depart_date"] = format_date_only(prepared_flight["return_depart"])
            
            # Store in offers database for detail view
            offers_db[prepared_flight["id"]] = prepared_flight

        # Apply limit to flights before rendering
        flights = flights[:limit]
        
        logger.info(f"Displaying {len(flights)} flights (limit: {limit})")

        debug_mode = request.args.get("debug") == "true"

        return render_template(
            "search_results.html",  # Changed from travel_results.html
            flights=flights,  # Pass limited flights
            origin=origin_code,
            destination=destination_code,
            depart_date=date_from_raw,
            return_date=date_to_raw if trip_type == "round-trip" else None,
            currency="EUR",
            direct_only=direct_only,
            message=result.get("message"),
            summary=result.get("summary"),
            affiliate_link=result.get("affiliate_link"),
            trip_info=trip_info
        )

    # GET request - show search form
    return render_template("travel_form.html", form_data=form_data, flights=flights, errors=errors)


# === Alternative Search Route (if your form posts here) ===
@travel_bp.route("/search-flights", methods=["POST"])
@travel_bp.route("/search-flights", methods=["POST"])
def search_flights():
    """Alternative search endpoint - uses hybrid Amadeus/Travelpayouts"""
    logger.info("search_flights route hit")
    
    # Get form data
    origin = extract_iata(request.form.get("origin_code", ""))
    destination = extract_iata(request.form.get("destination_code", ""))
    depart_date = request.form.get("date_from", "")
    return_date = request.form.get("date_to", "")
    trip_type = request.form.get("trip_type", "round-trip")
    passengers = request.form.get("passengers", "1")
    cabin_class = request.form.get("cabin_class", "economy")
    limit = int(request.form.get("limit", 4))  # Changed default to 4
    direct_only = request.form.get("direct_only") == "on"

    if not origin or not destination or not depart_date:
        return render_template("travel_form.html", 
                              errors=["Please provide origin, destination, and departure date"],
                              form_data=request.form)

    # ✅ IMPORTANT: Use the main search_flights function (which has Amadeus logic)
    try:
        flights = search_flights_func(  # This now tries Amadeus first!
            origin, 
            destination,
            depart_date,
            return_date if trip_type == "round-trip" else None,
            trip_type=trip_type,
            adults=int(passengers),
            children=0,
            infants=0,
            cabin_class=cabin_class,
            limit=limit,
            direct_only=direct_only
        )

        if not flights:
            return render_template("search_results.html",
                                 flights=[],
                                 origin=origin,
                                 destination=destination,
                                 depart_date=depart_date,
                                 return_date=return_date,
                                 currency="EUR",
                                 direct_only=direct_only)

        # Format flights for display
        marker = AFFILIATE_MARKER or os.getenv("AFFILIATE_MARKER", "")
        
        # --- CRITICAL FIX: Add type guard (isinstance(flight, dict)) ---
        safe_flights = []
        for flight in flights:
            if isinstance(flight, dict):
                
                # Ensure deeplink exists
                if not flight.get("link") and not flight.get("deeplink"):
                    flight["deeplink"] = build_flight_deeplink(flight, marker)
                else:
                    flight["deeplink"] = flight.get("link") or flight.get("deeplink")
                    
                safe_flights.append(flight)
            else:
                logger.error(f"Discarding non-dictionary flight result (Type: {type(flight)}): {flight}")

        # Apply limit here too (in case API returns more)
        flights = safe_flights[:limit]
        
        logger.info(f"Returning {len(flights)} flights (limit: {limit})")

        # Render results
        return render_template(
            "search_results.html",
            flights=flights,
            currency="EUR",
            origin=origin,
            destination=destination,
            depart_date=depart_date,
            return_date=return_date,
            direct_only=direct_only
        )

    except Exception as e:
        logger.error(f"Search error: {e}")
        logger.error(traceback.format_exc())
        return render_template("travel_form.html",
                              errors=[f"Search failed: {str(e)}"],
                              form_data=request.form)




@travel_bp.route("/offer/<offer_id>")
def view_offer(offer_id):
    """View detailed information for a specific flight offer"""
    offer = offers_db.get(offer_id)
    if offer is None:
        error_msg = f"Warning: No offer found for ID: {offer_id}"
        logger.warning(error_msg)
        return render_template("travel_form.html", errors=[error_msg])
    return render_template("travel_offer_details.html", offer=offer)


@travel_bp.route("/autocomplete-airports")
def autocomplete_airports():
    """Autocomplete endpoint for airport search"""
    logger.info("Autocomplete route hit!")
    query = request.args.get("query", "").strip().lower()
    logger.debug(f"Query received: '{query}'")

    with open("airports.json", "r", encoding="utf-8") as f:
        airports = json.load(f)

    tokens = query.replace("(", "").replace(")", "").replace("-", "").split()

    matches = [a for a in airports if any(
        is_token_match(token, a) for token in tokens if len(token) >= 1
    )]

    logger.debug(f"Matched airports: {[a['iata'] for a in matches]}")

    results = [{
        "value": f'{a["city"]} ({a["iata"]})',
        "label": f'{a["name"]} — {a["city"]} ({a["iata"]})'
    } for a in matches]

    return jsonify(results)


def is_token_match(token, airport):
    """Helper function to match search tokens against airport data"""
    return (
        airport["city"].lower().startswith(token) or
        airport["name"].lower().startswith(token) or
        airport["iata"].lower().startswith(token)
    )



@travel_bp.route("/enter-passenger-info", methods=["POST"])
def enter_passenger_info():
    """Collect passenger information for booking"""
    flight_data = request.form.get("flight_data")

    try:
        flight = json.loads(flight_data)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode flight data: {e}")
        return "Invalid flight data", 400

    return render_template("passenger_form.html", flight=flight)


@travel_bp.route("/payment", methods=["POST"])
def payment():
    """Handle payment form display"""
    try:
        flight_data = request.form.get("flight_data")
        flight = json.loads(flight_data) if flight_data else {}

        name = request.form.get("name")
        email = request.form.get("email")
        phone = request.form.get("phone")

        if not all([flight, name, email, phone]):
            raise ValueError("Missing flight or passenger data")

        passenger = {"name": name, "email": email, "phone": phone}

        session["passenger"] = passenger
        session["flight"] = flight

        return render_template("payment_form.html", flight=flight, passenger=passenger)

    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode flight data: {e}")
        return "Invalid flight data", 400
    except Exception as e:
        logger.error("Error in payment route:\n" + traceback.format_exc())
        return "Something went wrong with the payment process", 500


@travel_bp.route("/complete-booking", methods=["POST"])
def complete_booking():
    """Process booking completion and payment"""
    try:
        flight_data = request.form.get("flight_data")
        card_number = request.form.get("card_number")
        expiry = request.form.get("expiry")
        cvv = request.form.get("cvv")

        name = request.form.get("name") or session.get("passenger", {}).get("name")
        email = request.form.get("email") or session.get("passenger", {}).get("email")
        phone = request.form.get("phone") or session.get("passenger", {}).get("phone")

        if not all([flight_data, name, email, phone, card_number, expiry, cvv]):
            raise ValueError("Missing booking or payment data")

        flight = json.loads(flight_data)
        passenger = {"name": name, "email": email, "phone": phone}

        session["passenger"] = passenger
        session["flight"] = flight
        session["card_last4"] = card_number[-4:]
        session["expiry"] = expiry

        logger.info(f"✅ Booking prepared for {name} ({email}, {phone})")
        logger.info(f"💳 Payment info: Card ending in {card_number[-4:]}")

        return redirect(url_for("travel.finalize_booking"))

    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode flight data: {e}")
        return "Invalid flight data", 400
    except Exception as e:
        logger.error("Error during complete_booking:\n" + traceback.format_exc())
        return "Something went wrong during booking completion", 500


@travel_bp.route("/finalize-booking", methods=["GET", "POST"])
def finalize_booking():
    """Finalize booking and generate confirmation"""
    try:
        if request.method == "POST":
            flight_json = request.form.get("flight_data")
            passenger_json = request.form.get("passenger_data")
            
            flight = json.loads(flight_json) if flight_json else {}
            passenger = json.loads(passenger_json) if passenger_json else {}
        else:
            # Get from session
            flight = session.get("flight", {})
            passenger = session.get("passenger", {})

        if not flight or not passenger:
            raise ValueError("Missing booking data")

        # Validate passenger fields
        required_fields = ["name", "email", "phone"]
        for field in required_fields:
            if field not in passenger or not passenger[field]:
                raise ValueError(f"Missing passenger field: {field}")

        # Generate booking reference
        reference = generate_booking_reference()

        # Save to database
        save_booking(reference, passenger, json.dumps(flight))

        logger.info(f"✅ Booking finalized: {reference}")

        return render_template(
            "booking_success.html",
            reference=reference,
            passenger=passenger,
            flight=flight
        )

    except Exception as e:
        logger.error(f"Booking error: {e}")
        logger.error(traceback.format_exc())
        return f"Internal Server Error: {e}", 500


@travel_bp.route("/booking-history", methods=["GET"])
def booking_history():
    """Display booking history"""
    try:
        bookings = Booking.query.order_by(Booking.timestamp.desc()).all()
    except Exception as e:
        logger.error(f"Error loading booking history: {e}")
        bookings = []
    return render_template("booking_history.html", bookings=bookings)


@travel_bp.route("/", methods=["GET"])
def home_page():
    """Redirect root to main search page"""
    return redirect(url_for("travel.travel_ui"))


@travel_bp.route("/flightfinder", methods=["GET", "POST"])
def flightfinder():
    """Legacy FlightFinder route - redirects to main UI"""
    logger.info("FlightFinder legacy route - redirecting to travel_ui")
    return redirect(url_for("travel.travel_ui"))


@travel_bp.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.utcnow().isoformat(),
        'service': 'FlightFinder'
    })
    
    # In your travel_ui.py file:
# Ensure you have the necessary imports at the top:
# from flask import Blueprint, render_template, request, redirect
# from .flight_search import get_combined_flight_results 
# from app import logger # Or whichever way you access the logger

# ... (Existing code for travel_bp definition and other routes) ...

@travel_bp.route('/flights/results', methods=['GET'])
def flight_results():
    """
    Handles the search submission, calls the merging logic, and displays results.
    This is the function that *calls* get_combined_flight_results.
    """
    
    # --- 1. Receive Input (Get parameters from the URL query string) ---
    
    # Use request.args.get() to safely retrieve parameters from the URL
    origin = request.args.get('origin')
    destination = request.args.get('destination')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    # Safely handle other parameters
    # The 'on' check is for checkboxes, assume 'direct_only' comes from a checkbox or explicit value
    direct_only = request.args.get('direct_only') in ['on', 'true'] 
    adults = request.args.get('adults', type=int) or 1
    children = request.args.get('children', type=int) or 0
    infants = request.args.get('infants', type=int) or 0
    cabin_class = request.args.get('cabin_class', 'economy') 
    
    # Simple validation
    if not all([origin, destination, date_from]):
        # Redirect back to home or a form if key parameters are missing
        return redirect('/') 

    logger.info(f"Route Handler calling combined search: {origin} to {destination} on {date_from}")

    try:
        # --- 2. CRITICAL STEP: Call the Merging Logic ---
        # The view function calls your core business logic function.
        final_flights = get_combined_flight_results(
            origin_code=origin, 
            destination_code=destination, 
            date_from_str=date_from, 
            date_to_str=date_to,
            direct_only=direct_only,
            adults=adults,
            children=children,
            infants=infants,
            cabin_class=cabin_class
        ) 
        
        # --- 3. Render Output ---
        return render_template('search_results.html', flights=final_flights)

    except Exception as e:
        logger.error(f"Flight search route failed: {e}")
        # Return an error message to the user
        return render_template('search_results.html', error=f"An error occurred during search: {e}", flights=[])
    
    
    # app.py (Example using Flask)
from flask import Flask, request, redirect, url_for

# travel_ui.py (The function that handles the redirect)
from flask import request, redirect
# Note: Ensure you still have 'from urllib.parse import urlencode' 
# or just 'from urllib.parse import urlencode' if you need it elsewhere, 
# but it's not strictly needed for this modified redirect function.

@travel_bp.route('/search/<path:search_code>')
def redirect_to_aviasales(search_code):
    """
    Handles the internal fallback search URL and redirects the user
    to the external Aviasales site using the raw query string to avoid 400 errors.
    """
    
    # 1. Capture the raw query string from the incoming request (e.g., 'marker=...&direct=true')
    # This avoids any parsing issues Flask might have with individual arguments.
    raw_query_string = request.query_string.decode('utf-8')
    
    # 2. Construct the base external Aviasales URL
    # We use the search_code captured from the path
    base_external_url = f"https://www.aviasales.com/search/{search_code}"
    
    # 3. Combine the base URL with the raw query string
    full_external_url = f"{base_external_url}?{raw_query_string}"

    # 4. Redirect the user's browser to the external search URL
    return redirect(full_external_url, code=302)



@travel_bp.route("/book-flight")
def book_flight():
    # This function handles the redirect to the loading page
    target_url = request.args.get("url")
    destination_name = request.args.get("dest", "your destination")
    airline_name = request.args.get("airline", "our partner")
    
    return render_template("redirect.html", 
                           url=target_url, 
                           destination=destination_name, 
                           airline=airline_name)