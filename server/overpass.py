def get_overpass_url(poi_type, lat, lon, radius=2000, limit=20):
    """
    Generate Overpass API URLs for different POI types
    
    Args:
        poi_type: Type of POI to search for
        lat: Latitude
        lon: Longitude  
        radius: Search radius in meters (default: 2000)
        limit: Max results to return (default: 20)
        **kwargs: Additional filters (cuisine, attraction_type, etc.)
    
    Returns:
        Complete Overpass API URL
    """
    
    base_url = "http://overpass-api.de/api/interpreter"
    
    # Get the query based on POI type
    query = _build_overpass_query(poi_type, lat, lon, radius, limit)
    
    # Return complete URL
    return f"{base_url}?data={query}"


def _build_overpass_query(poi_type, lat, lon, radius, limit):
    """Build Overpass query string for different POI types"""
    
    queries = {
        "restaurants": _restaurants_query(lat, lon, radius, limit),
        "fast_food": _fast_food_query(lat, lon, radius, limit),
        "cafes": _cafes_query(lat, lon, radius, limit),
        "bars": _bars_query(lat, lon, radius, limit),
        "nightlife": _nightlife_query(lat, lon, radius, limit),
        
        "attractions": _attractions_query(lat, lon, radius, limit),
        "museums": _museums_query(lat, lon, radius, limit),
        "monuments": _monuments_query(lat, lon, radius, limit),
        "parks": _parks_query(lat, lon, radius, limit),
        "viewpoints": _viewpoints_query(lat, lon, radius, limit),
        "religious": _religious_query(lat, lon, radius, limit),
        "historic": _historic_query(lat, lon, radius, limit),
        
        "hotels": _hotels_query(lat, lon, radius, limit),
        "hostels": _hostels_query(lat, lon, radius, limit),
        "accommodation": _accommodation_query(lat, lon, radius, limit),
        
        "shopping": _shopping_query(lat, lon, radius, limit),
        "malls": _malls_query(lat, lon, radius, limit),
        "markets": _markets_query(lat, lon, radius, limit),
        "supermarkets": _supermarkets_query(lat, lon, radius, limit),
        
        "transport": _transport_query(lat, lon, radius, limit),
        "stations": _stations_query(lat, lon, radius, limit),
        "airports": _airports_query(lat, lon, radius, limit),
        
        "healthcare": _healthcare_query(lat, lon, radius, limit),
        "banks": _banks_query(lat, lon, radius, limit),
        "gas_stations": _gas_stations_query(lat, lon, radius, limit),
        
        "all_pois": _all_pois_query(lat, lon, radius, limit)
    }
    
    if poi_type not in queries:
        available = list(queries.keys())
        raise ValueError(f"Unknown POI type: {poi_type}. Available: {available}")
    
    return queries[poi_type]


# =============================================================================
# FOOD & DRINK QUERIES
# =============================================================================

def _restaurants_query(lat, lon, radius, limit):
    return f'[out:json];(node["amenity"="restaurant"](around:{radius},{lat},{lon}););out {limit};'

def _fast_food_query(lat, lon, radius, limit):
    return f'[out:json];(node["amenity"="fast_food"](around:{radius},{lat},{lon}););out {limit};'

def _cafes_query(lat, lon, radius, limit):
    return f'[out:json];(node["amenity"="cafe"](around:{radius},{lat},{lon}););out {limit};'

def _bars_query(lat, lon, radius, limit):
    return f'[out:json];(node["amenity"~"^(bar|pub)$"](around:{radius},{lat},{lon}););out {limit};'

def _nightlife_query(lat, lon, radius, limit):
    return f'[out:json];(node["amenity"~"^(bar|pub|nightclub|biergarten)$"](around:{radius},{lat},{lon}););out {limit};'


# =============================================================================
# ATTRACTIONS & TOURISM QUERIES
# =============================================================================

def _attractions_query(lat, lon, radius, limit, attraction_type=None):
    if attraction_type:
        type_filters = {
            "museums": '["tourism"="museum"]',
            "monuments": '["historic"~"^(monument|memorial)$"]',
            "parks": '["leisure"~"^(park|garden)$"]',
            "viewpoints": '["tourism"="viewpoint"]',
            "religious": '["amenity"="place_of_worship"]',
            "art": '["tourism"="artwork"]',
            "castles": '["historic"="castle"]'
        }
        filter_str = type_filters.get(attraction_type, '["tourism"]')
    else:
        filter_str = '["tourism"~"^(attraction|museum|monument|artwork|viewpoint)$"]'
    
    return f'[out:json];(node{filter_str}(around:{radius},{lat},{lon}););out {limit};'

def _museums_query(lat, lon, radius, limit):
    return f'[out:json];(node["tourism"="museum"](around:{radius},{lat},{lon}););out {limit};'

def _monuments_query(lat, lon, radius, limit):
    return f'[out:json];(node["historic"~"^(monument|memorial)$"](around:{radius},{lat},{lon}););out {limit};'

def _parks_query(lat, lon, radius, limit):
    return f'[out:json];(node["leisure"~"^(park|garden)$"](around:{radius},{lat},{lon}););out {limit};'

def _viewpoints_query(lat, lon, radius, limit):
    return f'[out:json];(node["tourism"="viewpoint"](around:{radius},{lat},{lon}););out {limit};'

def _religious_query(lat, lon, radius, limit):
    return f'[out:json];(node["amenity"="place_of_worship"](around:{radius},{lat},{lon}););out {limit};'

def _historic_query(lat, lon, radius, limit):
    return f'[out:json];(node["historic"](around:{radius},{lat},{lon}););out {limit};'


# =============================================================================
# ACCOMMODATION QUERIES
# =============================================================================

def _hotels_query(lat, lon, radius, limit):
    return f'[out:json];(node["tourism"="hotel"](around:{radius},{lat},{lon}););out {limit};'

def _hostels_query(lat, lon, radius, limit):
    return f'[out:json];(node["tourism"="hostel"](around:{radius},{lat},{lon}););out {limit};'

def _accommodation_query(lat, lon, radius, limit):
    return f'[out:json];(node["tourism"~"^(hotel|hostel|guest_house|apartment)$"](around:{radius},{lat},{lon}););out {limit};'


# =============================================================================
# SHOPPING QUERIES
# =============================================================================

def _shopping_query(lat, lon, radius, limit):
    return f'[out:json];(node["shop"](around:{radius},{lat},{lon}););out {limit};'

def _malls_query(lat, lon, radius, limit):
    return f'[out:json];(node["shop"="mall"](around:{radius},{lat},{lon}););out {limit};'

def _markets_query(lat, lon, radius, limit):
    return f'[out:json];(node["amenity"="marketplace"](around:{radius},{lat},{lon}););out {limit};'

def _supermarkets_query(lat, lon, radius, limit):
    return f'[out:json];(node["shop"="supermarket"](around:{radius},{lat},{lon}););out {limit};'


# =============================================================================
# TRANSPORT QUERIES
# =============================================================================

def _transport_query(lat, lon, radius, limit):
    return f'[out:json];(node["public_transport"~"^(station|stop_position)$"](around:{radius},{lat},{lon}););out {limit};'

def _stations_query(lat, lon, radius, limit):
    return f'[out:json];(node["railway"="station"](around:{radius},{lat},{lon}););out {limit};'

def _airports_query(lat, lon, radius, limit):
    return f'[out:json];(node["aeroway"="aerodrome"](around:{radius},{lat},{lon}););out {limit};'


# =============================================================================
# SERVICES QUERIES
# =============================================================================

def _healthcare_query(lat, lon, radius, limit):
    return f'[out:json];(node["amenity"~"^(hospital|clinic|pharmacy)$"](around:{radius},{lat},{lon}););out {limit};'

def _banks_query(lat, lon, radius, limit):
    return f'[out:json];(node["amenity"~"^(bank|atm)$"](around:{radius},{lat},{lon}););out {limit};'

def _gas_stations_query(lat, lon, radius, limit):
    return f'[out:json];(node["amenity"="fuel"](around:{radius},{lat},{lon}););out {limit};'


# =============================================================================
# COMPREHENSIVE QUERY
# =============================================================================

def _all_pois_query(lat, lon, radius, limit):
    return f'''[out:json];
    (
      node["amenity"~"^(restaurant|cafe|bar|hotel)$"](around:{radius},{lat},{lon});
      node["tourism"~"^(attraction|museum|monument)$"](around:{radius},{lat},{lon});
      node["shop"~"^(mall|supermarket)$"](around:{radius},{lat},{lon});
      node["leisure"~"^(park|garden)$"](around:{radius},{lat},{lon});
    );
    out {limit};'''


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_available_poi_types():
    """Get list of all available POI types"""
    return [
        # Food & Drink
        "restaurants", "fast_food", "cafes", "bars", "nightlife",
        
        # Attractions
        "attractions", "museums", "monuments", "parks", "viewpoints", 
        "religious", "historic",
        
        # Accommodation  
        "hotels", "hostels", "accommodation",
        
        # Shopping
        "shopping", "malls", "markets", "supermarkets",
        
        # Transport
        "transport", "stations", "airports",
        
        # Services
        "healthcare", "banks", "gas_stations",
        
        # All
        "all_pois"
    ]

def get_cuisine_types():
    """Get list of supported cuisine types for restaurants"""
    return [
        "italian", "chinese", "japanese", "mexican", "indian", 
        "french", "thai", "pizza", "seafood", "american",
        "korean", "vietnamese", "greek", "turkish", "lebanese"
    ]

def get_attraction_types():
    """Get list of supported attraction types"""
    return [
        "museums", "monuments", "parks", "viewpoints", 
        "religious", "art", "castles"
    ]