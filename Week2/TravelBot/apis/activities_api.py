import os
from amadeus import Client, ResponseError

def init_amadeus():
    amadeus_api_key = os.getenv("AMADEUS_API_KEY")
    amadeus_api_secret = os.getenv("AMADEUS_API_SECRET")
    
    amadeus = Client(
        client_id=amadeus_api_key,
        client_secret=amadeus_api_secret,
        hostname ="production"
    )
    return amadeus

def find_activities(lat, lon, radius_km=3):
    """
    Use Amadeus Tours & Activities around a lat/lon.
    """
    amadeus = init_amadeus()
    try:
        response = amadeus.shopping.activities.get(
            latitude=lat,
            longitude=lon,
            radius=radius_km
        )
        return response.data
    except ResponseError as e:
        print(f"Amadeus Activities Query Error: {e}")
        return []