def geocode_place(place_query: str):
    """
    Make a GET request to Nominatim with the free-form query.
    Return lat/lon from the top match if found, plus the full display_name.
    """
    base_url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": place_query,
        "format": "json",
        "limit": 1
    }
    headers = {
        "User-Agent": "YourAppName/1.0 (contact@yourdomain.com)"
    }
    try:
        response = requests.get(base_url, headers=headers, params=params)
        data = response.json()
    except Exception as e:
        print(f"Nominatim request error: {e}")
        return None

    if not data:
        return None

    top = data[0]
    lat = float(top["lat"])
    lon = float(top["lon"])
    display_name = top.get("display_name", "")
    return {
        "latitude": lat,
        "longitude": lon,
        "display_name": display_name
    }