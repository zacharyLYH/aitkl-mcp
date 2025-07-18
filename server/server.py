from typing import Any, Dict, List, Optional, Tuple
import httpx
from mcp.server.fastmcp import FastMCP
from overpass import get_overpass_url, get_available_poi_types
import asyncio
import logging

# Configure logging to show on terminal
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

log = logging.getLogger("server.py")

# Initialize FastMCP server
mcp = FastMCP("travel")

# Constants
PUBLIC_HOLIDAYS_API = "https://date.nager.at/api/v3"
WEATHER_API = "https://api.open-meteo.com/v1"
COUNTRIES_API = "https://restcountries.com/v3.1"
EXCHANGE_RATE_API = "https://api.exchangerate-api.com/v4"
GEOCODING_API = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "travel-mcp/1.0"

# In-memory coordinate cache
COORDINATE_CACHE: Dict[str, Tuple[float, float]] = {}

async def make_request(url: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Make a request to any API with proper error handling and backoff."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json"
    }
    
    max_retries = 2
    base_delay = 1.0
    
    async with httpx.AsyncClient() as client:
        for attempt in range(max_retries):
            try:
                response = await client.get(url, headers=headers, params=params, timeout=30.0)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                # Don't retry on 4xx client errors (permanent)
                if 400 <= e.response.status_code < 500:
                    log.error(f"Client error {e.response.status_code} for {url}: {e}")
                    return None
                
                # Retry on 5xx server errors (temporary)
                if attempt == max_retries - 1:
                    log.error(f"Server error {e.response.status_code} for {url} after {max_retries} attempts: {e}")
                    return None
                    
                delay = base_delay * (2 ** attempt)
                log.error(f"Server error {e.response.status_code} (attempt {attempt + 1}/{max_retries}), retrying in {delay}s...")
                await asyncio.sleep(delay)
                
            except (httpx.NetworkError, httpx.TimeoutException, httpx.ConnectError) as e:
                # Retry on network/timeout errors (temporary)
                if attempt == max_retries - 1:
                    log.error(f"Network/timeout error for {url} after {max_retries} attempts: {e}")
                    return None
                    
                delay = base_delay * (2 ** attempt)
                log.error(f"Network/timeout error (attempt {attempt + 1}/{max_retries}), retrying in {delay}s...")
                await asyncio.sleep(delay)
                
            except Exception as e:
                # Don't retry on other unexpected errors
                log.error(f"Unexpected error for {url}: {e}")
                return None

async def get_coordinates_for_location(location: str) -> Optional[Tuple[float, float]]:
    """Get coordinates for a location using geocoding with caching.
    
    Example: https://nominatim.openstreetmap.org/search?q=Seattle,Washington&format=json&limit=1
    """

    # Check cache first
    if location.lower() in COORDINATE_CACHE:
        return COORDINATE_CACHE[location.lower()]
    
    # Fetch from API
    params = {"q": location, "format": "json", "limit": 1}
    data = await make_request(GEOCODING_API, params)
    
    if data and isinstance(data, list) and len(data) > 0:
        result = data[0]
        lat = result.get('lat')
        lon = result.get('lon')
        if lat and lon:
            try:
                coords = (float(lat), float(lon))
                COORDINATE_CACHE[location.lower()] = coords
                return coords
            except ValueError:
                log.error(f"Invalid coordinates for {location}: lat={lat}, lon={lon}")
                return None
    
    return None

async def get_weather_forecast(latitude: float, longitude: float, days: int = 7) -> str:
    """Get weather forecast for specific coordinates."""

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current_weather": "true",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,windspeed_10m_max",
        "timezone": "auto",
        "forecast_days": min(days, 16)
    }
    
    data = await make_request(f"{WEATHER_API}/forecast", params)
    
    if not data:
        return f"Unable to fetch weather data for coordinates ({latitude}, {longitude})."
    
    current = data.get('current_weather', {})
    daily = data.get('daily', {})
    
    result = "Summarise this for me. Do not modify or add information. Weather Forecast:\n\n"
    
    # Current weather
    if current:
        result += f"Current Weather ({current.get('time', 'Unknown')}):\n"
        result += f"   Temperature: {current.get('temperature', 'Unknown')}°C\n"
        result += f"   Wind Speed: {current.get('windspeed', 'Unknown')} km/h\n"
        result += f"   Weather Code: {current.get('weathercode', 'Unknown')}\n\n"
    
    # Daily forecast
    if daily and 'time' in daily:
        times = daily['time']
        temp_max = daily.get('temperature_2m_max', [])
        temp_min = daily.get('temperature_2m_min', [])
        precip_prob = daily.get('precipitation_probability_max', [])
        
        result += "📅 Daily Forecast:\n"
        for i in range(min(len(times), 7)):
            date = times[i]
            max_temp = temp_max[i] if i < len(temp_max) else 'Unknown'
            min_temp = temp_min[i] if i < len(temp_min) else 'Unknown'
            prob = precip_prob[i] if i < len(precip_prob) else 'Unknown'
            
            result += f"   {date}: {min_temp}°C - {max_temp}°C, {prob}% rain chance\n"
    
    return result

@mcp.tool()
async def get_public_holidays(year: int, country_code: str) -> str:
    """Get public holidays for a specific country and year.
    
    This tool fetches official public holidays from the date.nager.at API, providing
    comprehensive holiday information including local names and dates for planning
    travel around national celebrations and observances.
    
    Args:
        year: Year to get holidays for (e.g., 2024, 2025)
        country_code: Two letter country code (e.g., 'US', 'GB', 'DE', 'JP', 'AU')
    
    Example: https://date.nager.at/api/v3/PublicHolidays/2025/US
    """
    data = await make_request(f"{PUBLIC_HOLIDAYS_API}/PublicHolidays/{year}/{country_code}")
    
    if not data:
        return f"The public holidays API is not working for {country_code} in {year}."
    
    if len(data) == 0:
        return f"No public holidays were found for {country_code} in {year}."
    
    result = f"Summarise this for me. Do not modify or add information. Public holidays in {country_code} for {year}:\n\n"
    
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
    
    return result

@mcp.tool()
async def get_weather_by_location(location: str, days: int = 7) -> str:
    """Get weather forecast for a location by name.
    
    This tool provides detailed weather forecasts including current conditions,
    daily temperature ranges, precipitation probability, and wind speeds.
    Perfect for travel planning and understanding local weather patterns.
    
    Args:
        location: Location name (country, city, etc.) - e.g., 'Paris', 'Tokyo', 'New York'
        days: Number of days to forecast (1-16, default 7)
    
    Example: https://api.open-meteo.com/v1/forecast?latitude=37.7749&longitude=-122.4194&current_weather=true&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,windspeed_10m_max&timezone=auto
    """
    coords = await get_coordinates_for_location(location)
    
    if not coords:
        return f"Unable to find coordinates for location: {location}"
    
    latitude, longitude = coords
    return await get_weather_forecast(latitude, longitude, days)

@mcp.tool()
async def get_country_info(country_name: str) -> str:
    """Get detailed information about a specific country. If the name is not a country, do not use this tool.
    
    This tool provides comprehensive country information including official names,
    capitals, demographics, languages, currencies, time zones, and geographic data.
    Essential for understanding destination countries before travel.
    
    Args:
        country_name: Name of the country (e.g., 'france', 'japan', 'brazil', 'australia')
    
    Example: https://restcountries.com/v3.1/name/france
    """
    data = await make_request(f"{COUNTRIES_API}/name/{country_name}")
    
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
        result += f"🗣️  Languages: {', '.join(languages.values())}\n"
    
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
    
    return result

@mcp.tool()
async def search_poi(location: str, poi_type: str = "attractions", limit: int = 10, radius: int = 10000) -> str:
    """Search for Points of Interest (POI) in a location using OpenStreetMap.
    
    This tool finds various types of points of interest including attractions,
    restaurants, hotels, museums, and more. Provides detailed information like
    contact details, opening hours, and addresses for travel planning.
    
    Args:
        location: Location to search in (city, country, etc.) - e.g., 'Paris', 'Tokyo'
        poi_type: Type of POI to search for - options include 'restaurants', 'hotels', 
                 'attractions', 'museums', 'shops', 'banks', 'pharmacies'
        limit: Maximum number of results (default 10, max 50)
        radius: Search radius in meters (default 10000, max 50000)
    
    Example: https://overpass-api.de/api/interpreter?data=[out:json];(node["amenity"="restaurant"](around:10000,48.8566,2.3522););out 10;
    """
    coords = await get_coordinates_for_location(location)
    
    if not coords:
        return f"Unable to find coordinates for location: {location}"
    
    latitude, longitude = coords
    
    try:
        overpass_url = get_overpass_url(poi_type, latitude, longitude, radius, limit)
    except ValueError as e:
        available_types = get_available_poi_types()
        return f"Invalid POI type: {poi_type}. Available types: {', '.join(available_types)}"
    
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
    
    return result

@mcp.tool()
async def convert_currency(amount: float, from_currency: str, to_currency: str) -> str:
    """Convert an amount from one currency to another using real-time exchange rates.
    
    This tool provides accurate currency conversion using current exchange rates
    from the exchangerate-api.com service. Essential for travel budgeting and
    understanding local costs in your home currency.
    
    Args:
        amount: Amount to convert (e.g., 100.0)
        from_currency: Source currency code (e.g., 'USD', 'EUR', 'JPY', 'GBP')
        to_currency: Target currency code (e.g., 'EUR', 'USD', 'CAD', 'AUD')
    
    Example: https://api.exchangerate-api.com/v4/latest/USD
    """
    data = await make_request(f"{EXCHANGE_RATE_API}/latest/{from_currency}")
    
    if not data:
        return f"Unable to fetch exchange rates for {from_currency}."
    
    rates = data.get('rates', {})
    
    if to_currency not in rates:
        return f"Currency {to_currency} not found in exchange rates."
    
    rate = rates[to_currency]
    converted_amount = amount * rate
    
    return f"Summarise this for me. Do not modify or add information. Currency Conversion:\n{amount} {from_currency} = {converted_amount:.2f} {to_currency}\n(Exchange rate: 1 {from_currency} = {rate:.4f} {to_currency})"

@mcp.tool()
async def get_travel_summary_for_country(country_name: str) -> str:
    """Get a comprehensive travel summary for a location.
    
    This tool provides a complete travel overview including country information,
    current weather forecast, popular attractions, and upcoming public holidays.
    Perfect for initial travel research and destination planning.
    
    Args:
        country_name: Country name (e.g., 'France', 'Japan', 'Australia')
    """
    result = f"Summarise this for me. Do not modify or add information. Travel Summary for {country_name}:\n{'='*50}\n\n"
    
    # Get country information
    country_info = await get_country_info(country_name)
    result += country_info + "\n\n"
    
    # Get weather forecast
    weather_info = await get_weather_by_location(country_name, days=5)
    result += weather_info + "\n\n"
    
    # Get popular tourist attractions
    poi_info = await search_poi(country_name, "attractions", limit=5)
    result += poi_info + "\n\n"
    
    # Get public holidays 
    try:
        country_data = await make_request(f"{COUNTRIES_API}/name/{country_name}")
        if country_data and isinstance(country_data, list) and len(country_data) > 0:
            country_code = country_data[0].get('cca2', '')
            if country_code:
                holidays_info = await get_public_holidays(2025, country_code)
                result += holidays_info + "\n\n"
    except:
        pass  # Skip holidays if there's an error
    
    return result

@mcp.tool()
async def get_travel_summary_for_city(city_name: str, country_name: str) -> str:
    """Get a comprehensive travel summary for a location.
    
    This tool provides a complete travel overview including country information,
    current weather forecast, popular attractions, and upcoming public holidays.
    Perfect for initial travel research and destination planning.
    
    Args:
        city_name: City name (e.g., 'Paris', 'Tokyo', 'New York')
        country_name: Country name (e.g., 'France', 'Japan', 'Australia')
    """
    result = f"Summarise this for me. Do not modify or add information. Travel Summary for {city_name}:\n{'='*50}\n\n"
    
    country_info = await get_country_info(country_name)
    result += country_info + "\n\n"

    # Get weather forecast
    weather_info = await get_weather_by_location(city_name, days=5)
    result += weather_info + "\n\n"
    
    # Get popular tourist attractions
    poi_info = await search_poi(city_name, "attractions", limit=5)
    result += poi_info + "\n\n"
    
    # Get public holidays 
    try:
        country_data = await make_request(f"{COUNTRIES_API}/name/{country_name}")
        if country_data and isinstance(country_data, list) and len(country_data) > 0:
            country_code = country_data[0].get('cca2', '')
            if country_code:
                holidays_info = await get_public_holidays(2025, country_code)
                result += holidays_info + "\n\n"
    except:
        pass  # Skip holidays if there's an error
    
    return result

if __name__ == "__main__":
    mcp.run(transport='stdio')
