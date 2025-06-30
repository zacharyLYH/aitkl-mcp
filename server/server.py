from typing import Any, List, Optional
import httpx
from mcp.server.fastmcp import FastMCP
from overpass import get_overpass_url, get_available_poi_types, get_cuisine_types, get_attraction_types

# Initialize FastMCP server
mcp = FastMCP("travel")

# Constants
PUBLIC_HOLIDAYS_API = "https://date.nager.at/api/v3"
WEATHER_API = "https://api.open-meteo.com/v1"
COUNTRIES_API = "https://restcountries.com/v3.1"
OVERPASS_API = "https://overpass-api.de/api/interpreter"
EXCHANGE_RATE_API = "https://api.exchangerate-api.com/v4"
USER_AGENT = "travel-mcp/1.0"
LAT_LON="https://nominatim.openstreetmap.org/search"

async def make_request(url: str, params: Optional[dict] = None) -> dict[str, Any] | None:
    """Make a request to any API with proper error handling."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, params=params, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error making request to {url}: {e}")
            return None

async def get_coordinates_for_location(location: str) -> Optional[tuple[float, float]]:
    """Get coordinates for a location using the countries API or geocoding.
    
    Example: GET https://nominatim.openstreetmap.org/search?q=Seattle,Washington&format=json&limit=1
    """
    # First try to get country coordinates
    country_data = await make_request(f"{LAT_LON}?q={location}&format=json&limit=1")
    
    if country_data and isinstance(country_data, list) and len(country_data) > 0:
        country = country_data[0]
        lat = country.get('lat', [])
        lon = country.get('lon', [])
        if lat and lon:
            return lat, lon
    
    # For cities, we could implement a more sophisticated geocoding service
    # For now, return None if we can't find coordinates
    return None

async def get_weather_forecast(latitude: float, longitude: float, days: int = 7) -> str:
    """Get weather forecast for a specific location.
    
    Args:
        latitude: Latitude coordinate
        longitude: Longitude coordinate
        days: Number of days to forecast (1-16, default 7)
    
    Example: GET https://api.open-meteo.com/v1/forecast?latitude=37.7749&longitude=-122.4194&current_weather=true&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,windspeed_10m_max&timezone=auto
    """
    url = f"{WEATHER_API}/forecast"
    
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current_weather": "true",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,windspeed_10m_max",
        "timezone": "auto"
    }
    
    if days:
        params["forecast_days"] = min(days, 16)  # API limit is 16 days
    
    data = await make_request(url, params)
    
    if not data:
        return f"Unable to fetch weather data for coordinates ({latitude}, {longitude})."
    
    current = data.get('current_weather', {})
    daily = data.get('daily', {})
    
    result = f"Summarise this for me. Do not modify or add information.Weather Forecast for ({latitude}, {longitude}):\n\n"
    
    # Current weather
    if current:
        temp = current.get('temperature', 'Unknown')
        windspeed = current.get('windspeed', 'Unknown')
        weather_code = current.get('weathercode', 'Unknown')
        time = current.get('time', 'Unknown')
        
        result += f"🌤️  Current Weather ({time}):\n"
        result += f"   Temperature: {temp}°C\n"
        result += f"   Wind Speed: {windspeed} km/h\n"
        result += f"   Weather Code: {weather_code}\n\n"
    
    # Daily forecast
    if daily and 'time' in daily:
        times = daily['time']
        temp_max = daily.get('temperature_2m_max', [])
        temp_min = daily.get('temperature_2m_min', [])
        precip_prob = daily.get('precipitation_probability_max', [])
        
        result += "📅 Daily Forecast:\n"
        for i in range(min(len(times), 7)):  # Show next 7 days
            date = times[i]
            max_temp = temp_max[i] if i < len(temp_max) else 'Unknown'
            min_temp = temp_min[i] if i < len(temp_min) else 'Unknown'
            prob = precip_prob[i] if i < len(precip_prob) else 'Unknown'
            
            result += f"   {date}: {min_temp}°C - {max_temp}°C, {prob}% rain chance\n"
    
    return result

@mcp.tool()
async def get_public_holidays(year: int, country_code: str) -> str:
    """Get public holidays for a specific country and year.
    
    Args:
        year: Year to get holidays for (e.g., 2024)
        country_code: Two letter country code (e.g., 'US', 'GB', 'DE')
    """
    url = f"{PUBLIC_HOLIDAYS_API}/PublicHolidays/{year}/{country_code}"
    
    data = await make_request(url)
    
    if not data:
        return f"Tell the user that the public holidays API is not working."
    
    if len(data) == 0:
        return f"Tell the user that no public holidays were found for {country_code} in {year}."
    
    result = f"According to the official public holidays API, these are the public holidays in {country_code} for {year}:\n\n"
    
    for holiday in data[:15]:  # Limit to 15 holidays
        name = holiday.get('name', 'Unknown')
        date = holiday.get('date', 'Unknown')
        local_name = holiday.get('localName', name)
        
        result += f"📅 {date}: {name}"
        if local_name != name:
            result += f" ({local_name})"
        result += "\n"
    
    if len(data) > 15:
        result += f"\n... and {len(data) - 15} more holidays"
    
    result += "\n\nPlease do not add or modify any information and ONLY summarize the public holidays in a way that is easy to understand and use."
    
    return result

@mcp.tool()
async def get_weather_by_location(location: str, days: int = 7) -> str:
    """Get weather forecast for a location by name.
    
    Args:
        location: Location name (country, city, etc.)
        days: Number of days to forecast (1-16, default 7)
    """
    coords = await get_coordinates_for_location(location)
    
    if not coords:
        return f"Unable to find coordinates for location: {location}"
    
    latitude, longitude = coords
    return await get_weather_forecast(latitude, longitude, days)

@mcp.tool()
async def get_country_info(country_name: str) -> str:
    """Get detailed information about a specific country.
    
    Args:
        country_name: Name of the country (e.g., 'france', 'japan', 'brazil')
    
    Example: GET https://restcountries.com/v3.1/name/france
    """
    url = f"{COUNTRIES_API}/name/{country_name}"
    
    data = await make_request(url)
    
    if not data or not isinstance(data, list) or len(data) == 0:
        return f"Unable to fetch information for country: {country_name}"
    
    country = data[0]
    
    result = f"Summarise this for me. Do not modify or add information. Country Information: {country.get('name', {}).get('common', country_name)}\n\n"
    
    # Basic info
    official_name = country.get('name', {}).get('official', 'Unknown')
    capital = country.get('capital', ['Unknown'])[0] if country.get('capital') else 'Unknown'
    region = country.get('region', 'Unknown')
    subregion = country.get('subregion', 'Unknown')
    population = country.get('population', 'Unknown')
    
    result += f"📋 Official Name: {official_name}\n"
    result += f"🏛️  Capital: {capital}\n"
    result += f"🌐 Region: {region}"
    if subregion != 'Unknown':
        result += f" ({subregion})"
    result += f"\n👥 Population: {population:,}\n"
    
    # Languages
    languages = country.get('languages', {})
    if languages:
        lang_list = list(languages.values())
        result += f"🗣️  Languages: {', '.join(lang_list)}\n"
    
    # Currencies
    currencies = country.get('currencies', {})
    if currencies:
        currency_list = []
        for code, info in currencies.items():
            name = info.get('name', code)
            symbol = info.get('symbol', '')
            currency_list.append(f"{name} ({code}){f' {symbol}' if symbol else ''}")
        result += f"💰 Currencies: {', '.join(currency_list)}\n"
    
    # Coordinates
    latlng = country.get('latlng', [])
    if len(latlng) >= 2:
        result += f"📍 Coordinates: {latlng[0]}, {latlng[1]}\n"
    
    # Time zones
    timezones = country.get('timezones', [])
    if timezones:
        result += f"🕐 Time Zones: {', '.join(timezones)}\n"
    
    # Flag
    flag = country.get('flag', '')
    if flag:
        result += f"🏳️  Flag: {flag}\n"
    
    result += "\n\nPlease do not add or modify any information and ONLY summarize the country information in a way that is easy to understand and use."
    
    return result

@mcp.tool()
async def search_poi(location: str, poi_type: str = "attractions", limit: int = 10, radius: int = 10000) -> str:
    """Search for Points of Interest (POI) in a location using OpenStreetMap.
    
    Args:
        location: Location to search in (city, country, etc.)
        poi_type: Type of POI to search for (e.g., 'restaurants', 'hotels', 'attractions', 'museums')
        limit: Maximum number of results (default 10)
        radius: Search radius in meters (default 10000)
    """
    # First get coordinates for the location
    coords = await get_coordinates_for_location(location)
    
    if not coords:
        return f"Unable to find coordinates for location: {location}"
    
    latitude, longitude = coords
    
    # Get fully qualified Overpass API URL using the overpass module
    try:
        overpass_url = get_overpass_url(poi_type, latitude, longitude, radius, limit)
    except ValueError as e:
        available_types = get_available_poi_types()
        return f"Invalid POI type: {poi_type}. Available types: {', '.join(available_types)}"
    
    # Make the request to the Overpass API
    data = await make_request(overpass_url)
    
    if not data or 'elements' not in data:
        return f"Unable to fetch POI data for {location}."
    
    elements = data['elements']
    if len(elements) == 0:
        return f"No {poi_type} POIs found in {location}."
    
    result = f"Summarise this for me. Do not modify or add information. Points of Interest ({poi_type}) in {location}:\n\n"
    
    poi_count = 0
    for element in elements:
        if poi_count >= limit:
            break
            
        if element.get('type') == 'node' and 'tags' in element:
            tags = element['tags']
            name = tags.get('name', tags.get('tourism', 'Unnamed POI'))
            
            result += f"📍 {name}\n"
            
            # Add additional info if available
            if 'website' in tags:
                result += f"   🌐 Website: {tags['website']}\n"
            if 'phone' in tags:
                result += f"   📞 Phone: {tags['phone']}\n"
            if 'opening_hours' in tags:
                result += f"   🕐 Hours: {tags['opening_hours']}\n"
            if 'cuisine' in tags:
                result += f"   🍽️  Cuisine: {tags['cuisine']}\n"
            if 'addr:street' in tags:
                result += f"   🏠 Address: {tags.get('addr:housenumber', '')} {tags['addr:street']}\n"
            if 'brand' in tags:
                result += f"   🏢 Brand: {tags['brand']}\n"
            if 'stars' in tags:
                result += f"   ⭐ Rating: {tags['stars']} stars\n"
            
            result += "\n"
            poi_count += 1
    
    if len(elements) > limit:
        result += f"... and {len(elements) - limit} more POIs"
    
    result += "\n\nPlease do not add or modify any information and ONLY summarize the POIs in a way that is easy to understand and use."
    
    return result

@mcp.tool()
async def convert_currency(amount: float, from_currency: str, to_currency: str) -> str:
    """Convert an amount from one currency to another.
    
    Args:
        amount: Amount to convert
        from_currency: Source currency code (e.g., 'USD')
        to_currency: Target currency code (e.g., 'EUR')
    """
    url = f"{EXCHANGE_RATE_API}/latest/{from_currency}"
    
    data = await make_request(url)
    
    if not data:
        return f"Unable to fetch exchange rates for {from_currency}."
    
    rates = data.get('rates', {})
    
    if to_currency not in rates:
        return f"Currency {to_currency} not found in exchange rates."
    
    rate = rates[to_currency]
    converted_amount = amount * rate
    
    return f"Summarise this for me. Do not modify or add information. Currency Conversion:\n{amount} {from_currency} = {converted_amount:.2f} {to_currency}\n(Exchange rate: 1 {from_currency} = {rate:.4f} {to_currency})"

@mcp.tool()
async def get_travel_summary(location: str) -> str:
    """Get a comprehensive travel summary for a location including weather, country info, and POIs.
    
    Args:
        location: Location name (country, city, etc.)
    """
    result = f"🌍 Travel Summary for {location}:\n{'='*50}\n\n"
    
    # Get country information
    country_info = await get_country_info(location)
    result += country_info + "\n\n"
    
    # Get weather forecast
    weather_info = await get_weather_by_location(location, days=5)
    result += weather_info + "\n\n"
    
    # Get popular tourist attractions
    poi_info = await search_poi(location, "attractions", limit=5)
    result += poi_info + "\n\n"
    
    # Get public holidays (if it's a country)
    try:
        # Try to get country code from country info
        country_data = await make_request(f"{COUNTRIES_API}/name/{location}")
        if country_data and isinstance(country_data, list) and len(country_data) > 0:
            country_code = country_data[0].get('cca2', '')
            if country_code:
                holidays_info = await get_public_holidays(2025, country_code)
                result += holidays_info + "\n\n"
    except:
        pass  # Skip holidays if there's an error
    
    return result

if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio') 