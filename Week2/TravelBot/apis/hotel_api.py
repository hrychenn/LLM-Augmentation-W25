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

#https://developers.amadeus.com/self-service/category/hotels/api-doc/hotel-list/api-reference
def get_hotels_in_city(city_code: str, radius_km=10):
    """
    Use reference_data.locations.hotels.by_city to list hotels in that city.
    Returns a list of hotels (each has a 'hotelId').
    """
    amadeus = init_amadeus()
    try:
        response = amadeus.reference_data.locations.hotels.by_city.get(
            cityCode=city_code,
            radius=radius_km,
            radiusUnit="KM"
        )
        return response.data  # list of hotels
    except ResponseError as e:
        print(f"Error retrieving hotels by city: {e}")
        return []
    
#https://developers.amadeus.com/self-service/category/hotels/api-doc/hotel-search/api-reference
def get_hotel_offers(
    hotel_ids,
    check_in,
    check_out,
    adults=1,
    rooms=1,
    price_range=None
):
    """
    Fetch actual offers for the given hotel(s) using the v3 Hotel Search endpoint.
    Optional:
      - adults: number of adult guests (1-9)
      - rooms: number of rooms (1-9)
      - price_range: string, e.g. "200-300", "-300", or "100" 
                    (must include currency if the API requires it)
    """
    amadeus = init_amadeus()
    if not hotel_ids:
        return []

    try:
        params = {
            "hotelIds": ",".join(hotel_ids),
            "checkInDate": check_in,
            "checkOutDate": check_out,
            "adults": adults,
            "roomQuantity": rooms,
            "currency": "USD"  # or "currencyCode": "USD" if needed
        }
        # If the user specifies a price range (like "200-300")
        if price_range:
            params["priceRange"] = price_range  # e.g., "200-300"

        response = amadeus.shopping.hotel_offers_search.get(**params)
        return response.data
    except ResponseError as e:
        print(f"Error retrieving hotel offers: {e}")
        return []