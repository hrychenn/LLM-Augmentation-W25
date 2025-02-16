import os
from flask import Flask, render_template, request, redirect, url_for, session
from dotenv import load_dotenv

# Import your agents
from apis.flight_api import guess_airport_code, find_flights
from apis.activities_api import find_activities
from apis.hotel_api import get_hotel_offers, get_hotels_in_city
from apis.geolocate_api import geocode_place

# Import your helpers
from helpers.llm_helpers_sol import (
    parse_location,
    process_user_input
)
from helpers.flight_functions import call_parse_flight_options

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(16)

# -------------------------------------------------------------------------
# HELPER: Initialize session defaults
# -------------------------------------------------------------------------
def init_session():
    """Initialize needed session keys if they aren't set."""
    # We'll use a single 'current_cost' field now.
    if "current_cost" not in session:
        session["current_cost"] = 0.0

    if "origin_code" not in session:
        session["origin_code"] = ""
    if "destination_code" not in session:
        session["destination_code"] = ""
    if "flight_choice" not in session:
        session["flight_choice"] = None
    if "hotel_choice" not in session:
        session["hotel_choice"] = None
    if "activity_choices" not in session:
        session["activity_choices"] = []
    if "depart_date" not in session:
        session["depart_date"] = ""
    if "return_date" not in session:
        session["return_date"] = ""
    if "location_raw" not in session:
        session["location_raw"] = ""
    if "location_parsed" not in session:
        session["location_parsed"] = {}
    if "city" not in session:
        session["city"] = ""
    if "coordinate_search" not in session:
        session["coordinate_search"] = ""
    
    # Single service flag: "vacation", "flight", "hotel", or "activities"
    if "service" not in session:
        session["service"] = "vacation"

def get_summary_context(step_num=1):
    """Collect data for the summary portion, including the single current_cost."""
    return {
        "origin_code": session.get("origin_code", ""),
        "destination_code": session.get("destination_code", ""),
        "depart_date": session.get("depart_date", ""),
        "return_date": session.get("return_date", ""),
        "flight_choice": session.get("flight_choice", None),
        "hotel_choice": session.get("hotel_choice", None),
        "activity_choices": session.get("activity_choices", []),
        "current_price": session.get("current_cost", 0.0),
        "current_step": step_num,
        "service": session.get("service", "vacation"),
    }

@app.route("/clear", methods=["POST"])
def clear_session():
    """Clears the session and redirects to the index."""
    session.clear()
    return redirect(url_for("index"))

# -------------------------------------------------------------------------
# STEP 1: Index (classify user intent)
# -------------------------------------------------------------------------
@app.route("/", methods=["GET"])
def index():
    """Renders index.html (step1)."""
    session.clear()
    init_session()
    return render_template("index.html")

@app.route("/process_input", methods=["POST"])
def process_input_route():
    init_session()
    user_text = request.form.get("user_query", "").strip()
    if not user_text:
        return redirect(url_for("index"))

    # Classify the user request
    intent = process_user_input(user_text)  # "flight", "hotel", "activities", or "vacation"
    session["service"] = intent

    # Next step -> Step2: get location
    return redirect(url_for("step2"))


# -------------------------------------------------------------------------
# STEP 2: Get Location
# -------------------------------------------------------------------------
@app.route("/step2", methods=["GET", "POST"])
def step2():
    init_session()
    if request.method == "POST":
        loc_input = request.form.get("location", "").strip()
        if not loc_input:
            error = "Please enter a location."
            return render_template("location.html", error=error, summary=get_summary_context(2))
        session["location_raw"] = loc_input
        # Example: set a default origin code
        session["origin_code"] = "DTW"

        # Next: Step3 (confirm_location)
        return redirect(url_for("step3"))
    
    return render_template("location.html", summary=get_summary_context(2))


# -------------------------------------------------------------------------
# STEP 3: Confirm Location
# -------------------------------------------------------------------------
@app.route("/step3", methods=["GET", "POST"])
def step3():
    init_session()
    if not session["location_raw"]:
        return redirect(url_for("step2"))

    # parse location
    loc_parsed = parse_location(session["location_raw"])
    session["location_parsed"] = loc_parsed
    session["city"] = loc_parsed.get("city", "")
    state = loc_parsed.get("state", "")
    country = loc_parsed.get("country", "")
    clarifications = loc_parsed.get("clarifications", "")
    session["coordinate_search"] = f"{session['city']} {state}, {country}"

    if request.method == "POST":
        service = session["service"]
        # Next steps vary by service
        if service in ["vacation", "flight"]:
            return redirect(url_for("step4"))
        elif service == "hotel":
            return redirect(url_for("step5"))
        elif service == "activities":
            return redirect(url_for("step8"))
    return render_template(
        "confirm_location.html",
        city=session["city"],
        state=state,
        country=country,
        clarifications=clarifications,
        summary=get_summary_context(3)
    )


# -------------------------------------------------------------------------
# STEP 4: Confirm Airport Codes
# -------------------------------------------------------------------------
@app.route("/step4", methods=["GET", "POST"])
def step4():
    init_session()
    if not session["city"]:
        return redirect(url_for("step3"))

    service = session["service"]
    # If user is "hotel" or "activities", skip step4
    if service == "hotel":
        return redirect(url_for("step5"))
    elif service == "activities":
        return redirect(url_for("step8"))

    # Guess code
    guessed_code = guess_airport_code(session["city"])

    if request.method == "POST":
        session["destination_code"] = guessed_code or ""
        # Next -> step5 (dates) for flight or vacation
        return redirect(url_for("step5"))

    return render_template(
        "airport.html",
        origin_code=session["origin_code"],
        guessed_code=guessed_code,
        summary=get_summary_context(4)
    )


# -------------------------------------------------------------------------
# STEP 5: Travel Dates
# -------------------------------------------------------------------------
@app.route("/step5", methods=["GET", "POST"])
def step5():
    init_session()
    if not session["city"]:
        return redirect(url_for("step3"))

    service = session["service"]
    # "activities" users skip 4..7 => step8
    if service == "activities":
        return redirect(url_for("step8"))

    if request.method == "POST":
        dep = request.form.get("dep_date", "")
        ret = request.form.get("ret_date", "")
        session["depart_date"] = dep or ""
        if ret and ret != dep:
            session["return_date"] = ret
        else:
            session["return_date"] = ""

        if service in ["vacation", "flight"]:
            return redirect(url_for("step6_options"))  # search flights
        else:  # "hotel"
            return redirect(url_for("step7"))

    return render_template("dates.html", summary=get_summary_context(5))


# -------------------------------------------------------------------------
# STEP 6: Search Flights
# -------------------------------------------------------------------------


@app.route("/step6_options", methods=["GET", "POST"])
def step6_options():
    """
    Step 6 Options:
    - Ask user for optional flight parameters, e.g. '2 adults, business class, non-stop...'
    - Force LLM to parse them into JSON (adults, travelClass, nonStop, maxPrice).
    - Store them in the session, then redirect to step6 (flight search).
    """
    init_session()

    if request.method == "POST":
        user_input = request.form.get("flight_extras", "").strip()
        if user_input:
            extras = call_parse_flight_options(user_input)
            # e.g. extras = {"adults":2, "travelClass":"BUSINESS", "nonStop":True, "maxPrice":400}

            session["adults"] = extras.get("adults", 1)
            session["travel_class"] = extras.get("travelClass")
            session["non_stop"] = extras.get("nonStop", False)
            session["max_price"] = extras.get("maxPrice")

        # Next: step6 => flight search
        return redirect(url_for("step6"))

    # If GET, just show a form to gather flight extras
    return render_template("flight_options.html", summary=get_summary_context(6))

@app.route("/step6", methods=["GET", "POST"])
def step6():
    """
    Step 6: Perform the flight search using previously gathered data
    (origin_code, destination_code, depart_date, return_date)
    plus optional fields (adults, travel_class, non_stop, max_price)
    if the user provided them in step6_options.
    """
    init_session()
    service = session["service"]

    if service == "hotel":
        return redirect(url_for("step7"))
    elif service == "activities":
        return redirect(url_for("step8"))

    # Required Data
    origin = session["origin_code"]
    dest = session["destination_code"]
    dep = session["depart_date"]
    ret = session["return_date"] or None

    # Optional Fields
    adults = session.get("adults", 1)
    travel_class = session.get("travel_class", None)  # Economy, Business, etc.
    non_stop = session.get("non_stop", False)
    max_price = session.get("max_price", None)

    # Fetch Flight Offers
    flights_data = find_flights(
        origin, dest, dep, ret, max_price=max_price, adults=adults, travel_class=travel_class, non_stop=non_stop
    )

    # If no flights found, retry with default values
    if not flights_data:
        flights_data = find_flights(
            origin, dest, dep, ret, max_price=None, adults=1, travel_class=None, non_stop=False
        )

    # Format Flight Options
    flight_options = []
    flight_prices = []

    if flights_data:
        for f in flights_data:
            flight_id = f.get("id", "UnknownID")
            price_str = f.get("price", {}).get("grandTotal", "0")
            currency = f.get("price", {}).get("currency", "USD")
            num_seats = f.get("numberOfBookableSeats", "N/A")
            validating_airlines = ", ".join(f.get("validatingAirlineCodes", ["N/A"]))

            try:
                price_val = float(price_str)
            except:
                price_val = 0.0

            summary_lines = [
                f"Flight ID: {flight_id}",
                f"Price: {currency} {price_str}",
                f"Seats Available: {num_seats}",
                f"Validating Airline: {validating_airlines}",
            ]

            for i, itin in enumerate(f.get("itineraries", []), start=1):
                summary_lines.append(f"  Itinerary {i}: Duration {itin.get('duration', 'N/A')}")
                for j, seg in enumerate(itin.get("segments", []), start=1):
                    dep_iata = seg.get("departure", {}).get("iataCode", "")
                    dep_time = seg.get("departure", {}).get("at", "N/A")
                    arr_iata = seg.get("arrival", {}).get("iataCode", "")
                    arr_time = seg.get("arrival", {}).get("at", "N/A")
                    carrier = seg.get("carrierCode", "N/A")
                    flight_num = seg.get("number", "N/A")
                    aircraft = seg.get("aircraft", {}).get("code", "N/A")
                    duration = seg.get("duration", "N/A")

                    # Get Travel Class & Baggage Info
                    travel_class_name = "N/A"
                    baggage_info = "N/A"

                    for traveler in f.get("travelerPricings", []):
                        for fare_details in traveler.get("fareDetailsBySegment", []):
                            if fare_details.get("segmentId") == seg.get("id"):
                                travel_class_name = fare_details.get("cabin", "N/A")
                                baggage_info = f"{fare_details.get('includedCheckedBags', {}).get('weight', 'N/A')} {fare_details.get('includedCheckedBags', {}).get('weightUnit', 'KG')}"

                    seg_line = (
                        f"    Segment {j}: {dep_iata} ({dep_time}) → {arr_iata} ({arr_time})\n"
                        f"      - Carrier: {carrier}, Flight {flight_num}, Aircraft {aircraft}, Duration: {duration}\n"
                        f"      - Travel Class: {travel_class_name}, Checked Baggage: {baggage_info}"
                    )
                    summary_lines.append(seg_line)

            flight_summary = "\n".join(summary_lines)
            flight_options.append(flight_summary)
            flight_prices.append(price_val)

    # Handle User Selection
    if request.method == "POST":
        chosen_index = int(request.form.get("chosen_flight_index", "-1"))
        if 0 <= chosen_index < len(flight_options):
            session["flight_choice"] = flight_options[chosen_index]
            session["current_cost"] = session.get("current_cost", 0.0) + flight_prices[chosen_index]

        return redirect(url_for("step7_options") if service == "vacation" else url_for("step8"))

    return render_template("flights.html", flights=flight_options, summary=get_summary_context(6))



# -------------------------------------------------------------------------
# STEP 7: Hotels
# -------------------------------------------------------------------------

@app.route("/step7_options", methods=["GET", "POST"])
def step7_options():
    """
    Similar to flight extras, gather optional hotel info: adults, rooms, priceRange.
    """
    init_session()

    if request.method == "POST":
        user_input = request.form.get("hotel_extras", "")
        from helpers.hotel_functions import call_parse_hotel_options
        extras = call_parse_hotel_options(user_input)
        # e.g. {"adults":2, "rooms":2, "priceRange":"-300"}

        session["hotel_adults"] = extras.get("adults", 1)
        session["hotel_rooms"] = extras.get("rooms", 1)
        session["hotel_price_range"] = extras.get("priceRange")

        return redirect(url_for("step7"))  # Now run the main step7

    return render_template("hotel_options.html", summary=get_summary_context(7))

@app.route("/step7", methods=["GET", "POST"])
def step7():
    init_session()
    service = session["service"]

    if service == "flight":
        return redirect(url_for("step8"))
    elif service == "activities":
        return redirect(url_for("step8"))

    dest_code = session["destination_code"]
    hotels_data = get_hotels_in_city(dest_code, radius_km=10)
    hotel_names, hotel_ids = [], []

    if hotels_data:
        for h in hotels_data:
            hname = h.get("name", "Unknown Hotel")
            hid = h.get("hotelId", "")
            label = f"{hname} ({hid})"
            hotel_names.append(label)
            hotel_ids.append(hid)

    if request.method == "POST":
        if "see_offers" in request.form:
            idx = int(request.form.get("selected_hotel", "-1"))
            if 0 <= idx < len(hotel_ids):
                selected_id = hotel_ids[idx]

                # Fetch offers using user preferences
                offers_data = get_hotel_offers(
                    [selected_id],
                    check_in=session["depart_date"],
                    check_out=session["return_date"] or None,
                    adults=session.get("adults", 1),
                    rooms=session.get("rooms", 1),
                    price_range=session.get("price_range")
                )

                # If no offers found, retry with default values
                if not offers_data:
                    offers_data = get_hotel_offers(
                        [selected_id],
                        check_in=session["depart_date"],
                        check_out=session["return_date"] or None,
                        adults=1,
                        rooms=1,
                        price_range=None
                    )

                # Store offers in session with correct details
                session["current_offers"] = []
                if offers_data:
                    for item in offers_data:
                        if "offers" in item:
                            for o in item["offers"]:
                                session["current_offers"].append({
                                    "id": o.get("id", "N/A"),
                                    "price": o.get("price", {}).get("total", "0"),
                                    "check_in": o.get("checkInDate", "N/A"),
                                    "check_out": o.get("checkOutDate", "N/A"),
                                    "rooms": o.get("room", {}).get("typeEstimated", {}).get("category", "N/A"),
                                    "guests": o.get("guests", {}).get("adults", "N/A")
                                })

            return redirect(url_for("step7"))

        elif "confirm_hotel_offer" in request.form:
            offer_idx = int(request.form.get("chosen_offer_index", "-1"))
            if "current_offers" in session and 0 <= offer_idx < len(session["current_offers"]):
                chosen_offer = session["current_offers"][offer_idx]
                price_str = chosen_offer["price"]
                try:
                    price_val = float(price_str)
                except:
                    price_val = 0.0
                session["current_cost"] = session.get("current_cost", 0.0) + price_val
                session["hotel_choice"] = (
                    f"Hotel Offer {chosen_offer['id']} - ${price_str}, "
                    f"Check-in: {chosen_offer['check_in']}, Check-out: {chosen_offer['check_out']}, "
                    f"Rooms: {chosen_offer['rooms']}, Guests: {chosen_offer['guests']} adults"
                )

            if service == "vacation":
                return redirect(url_for("step8"))
            else:
                return redirect(url_for("step9"))

    offers = session.get("current_offers", [])
    return render_template(
        "hotels.html",
        hotel_names=hotel_names,
        hotel_ids=hotel_ids,
        offers=offers,
        summary=get_summary_context(7)
    )


# -------------------------------------------------------------------------
# STEP 8: Activities
# -------------------------------------------------------------------------
@app.route("/step8", methods=["GET", "POST"])
def step8():
    init_session()
    service = session["service"]
    # flight => steps 2..6,8 => done after 8
    # vacation => 2..9 => next step9
    # activities => 2,3,8,9 => next step9
    # hotel => skip 8 => go step9

    if service == "hotel":
        return redirect(url_for("step9"))

    # geocode
    lat, lon = None, None
    if session["coordinate_search"]:
        geo = geocode_place(session["coordinate_search"])
        if geo:
            lat = geo["latitude"]
            lon = geo["longitude"]

    activities = []
    if lat and lon:
        acts_data = find_activities(lat, lon, radius_km=5)
        if acts_data:
            for i, act in enumerate(acts_data):
                aname = act.get("name", "Unknown Activity")
                price_str = act.get("price", {}).get("amount", "0")
                try:
                    price_val = float(price_str)
                except:
                    price_val = 0.0
                activities.append({
                    "index": i,
                    "label": f"{aname} (${price_str})",
                    "price": price_val
                })

    if request.method == "POST":
        chosen_indices = request.form.getlist("activity_choice")
        total_extra = 0.0
        chosen_list = []
        for idx_str in chosen_indices:
            idx_int = int(idx_str)
            if 0 <= idx_int < len(activities):
                chosen_list.append(activities[idx_int]["label"])
                total_extra += activities[idx_int]["price"]

        session["activity_choices"] = chosen_list
        session["current_cost"] = session.get("current_cost", 0.0) + total_extra

        # next step
        if service in ["vacation", "activities"]:
            return redirect(url_for("step9"))
        else:
            # flight => done after 8
            return render_template("done.html", summary=get_summary_context(8))

    return render_template(
        "activities.html",
        activities=activities,
        summary=get_summary_context(8)
    )


# -------------------------------------------------------------------------
# STEP 9: Final Summary
# -------------------------------------------------------------------------
@app.route("/step9", methods=["GET", "POST"])
def step9():
    init_session()
    # Only for vacation or activities (or if you want to show final summary for hotel).
    return render_template("final.html", summary=get_summary_context(9))


# -------------------------------------------------------------------------
# Run the Flask app
# -------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
