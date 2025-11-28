#!/usr/bin/env python3
"""
Weather MCP Server
Provides weather information via Open-Meteo API (free, no API key required).
"""

import httpx
from typing import Optional
from fastmcp import FastMCP

mcp = FastMCP("weather")

# Open-Meteo API endpoints
GEOCODING_API = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_API = "https://api.open-meteo.com/v1/forecast"

# Weather code descriptions
WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


async def geocode_city(city: str) -> Optional[dict]:
    """Get coordinates for a city name."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            GEOCODING_API,
            params={"name": city, "count": 1, "language": "en", "format": "json"},
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()

        if not data.get("results"):
            return None

        result = data["results"][0]
        return {
            "name": result.get("name"),
            "country": result.get("country"),
            "admin1": result.get("admin1"),  # State/Province
            "latitude": result.get("latitude"),
            "longitude": result.get("longitude"),
            "timezone": result.get("timezone"),
        }


def get_weather_description(code: int) -> str:
    """Get human-readable weather description from weather code."""
    return WEATHER_CODES.get(code, f"Unknown ({code})")


@mcp.tool()
async def get_current_weather(city: str) -> dict:
    """
    Get current weather for a city.

    Args:
        city: Name of the city (e.g., "Seoul", "New York", "London")

    Returns:
        Current weather information including temperature, wind, and conditions
    """
    try:
        # Get city coordinates
        location = await geocode_city(city)
        if not location:
            return {"success": False, "error": f"City '{city}' not found"}

        # Get weather data
        async with httpx.AsyncClient() as client:
            response = await client.get(
                WEATHER_API,
                params={
                    "latitude": location["latitude"],
                    "longitude": location["longitude"],
                    "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,wind_direction_10m",
                    "timezone": location.get("timezone", "auto"),
                },
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

        current = data.get("current", {})
        units = data.get("current_units", {})

        return {
            "success": True,
            "location": {
                "city": location["name"],
                "country": location["country"],
                "region": location.get("admin1"),
                "latitude": location["latitude"],
                "longitude": location["longitude"],
            },
            "current": {
                "temperature": f"{current.get('temperature_2m')}{units.get('temperature_2m', '°C')}",
                "feels_like": f"{current.get('apparent_temperature')}{units.get('apparent_temperature', '°C')}",
                "humidity": f"{current.get('relative_humidity_2m')}{units.get('relative_humidity_2m', '%')}",
                "precipitation": f"{current.get('precipitation')}{units.get('precipitation', 'mm')}",
                "wind_speed": f"{current.get('wind_speed_10m')}{units.get('wind_speed_10m', 'km/h')}",
                "wind_direction": f"{current.get('wind_direction_10m')}°",
                "condition": get_weather_description(current.get("weather_code", 0)),
                "time": current.get("time"),
            },
        }

    except httpx.HTTPStatusError as e:
        return {"success": False, "error": f"API error: {e.response.status_code}"}
    except httpx.RequestError as e:
        return {"success": False, "error": f"Request error: {str(e)}"}
    except Exception as e:
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


@mcp.tool()
async def get_weather_forecast(city: str, days: int = 7) -> dict:
    """
    Get weather forecast for a city.

    Args:
        city: Name of the city (e.g., "Seoul", "New York", "London")
        days: Number of forecast days (1-16, default: 7)

    Returns:
        Daily weather forecast including temperature range and conditions
    """
    try:
        # Validate days parameter
        days = max(1, min(16, days))

        # Get city coordinates
        location = await geocode_city(city)
        if not location:
            return {"success": False, "error": f"City '{city}' not found"}

        # Get forecast data
        async with httpx.AsyncClient() as client:
            response = await client.get(
                WEATHER_API,
                params={
                    "latitude": location["latitude"],
                    "longitude": location["longitude"],
                    "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,weather_code,wind_speed_10m_max",
                    "timezone": location.get("timezone", "auto"),
                    "forecast_days": days,
                },
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

        daily = data.get("daily", {})
        units = data.get("daily_units", {})

        forecast = []
        dates = daily.get("time", [])
        for i, date in enumerate(dates):
            forecast.append(
                {
                    "date": date,
                    "temperature_max": f"{daily.get('temperature_2m_max', [])[i]}{units.get('temperature_2m_max', '°C')}",
                    "temperature_min": f"{daily.get('temperature_2m_min', [])[i]}{units.get('temperature_2m_min', '°C')}",
                    "precipitation": f"{daily.get('precipitation_sum', [])[i]}{units.get('precipitation_sum', 'mm')}",
                    "precipitation_probability": f"{daily.get('precipitation_probability_max', [])[i]}%",
                    "wind_speed_max": f"{daily.get('wind_speed_10m_max', [])[i]}{units.get('wind_speed_10m_max', 'km/h')}",
                    "condition": get_weather_description(
                        daily.get("weather_code", [])[i]
                    ),
                }
            )

        return {
            "success": True,
            "location": {
                "city": location["name"],
                "country": location["country"],
                "region": location.get("admin1"),
            },
            "forecast_days": len(forecast),
            "forecast": forecast,
        }

    except httpx.HTTPStatusError as e:
        return {"success": False, "error": f"API error: {e.response.status_code}"}
    except httpx.RequestError as e:
        return {"success": False, "error": f"Request error: {str(e)}"}
    except Exception as e:
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


@mcp.tool()
async def get_weather_by_coordinates(latitude: float, longitude: float) -> dict:
    """
    Get current weather for specific coordinates.

    Args:
        latitude: Latitude coordinate (-90 to 90)
        longitude: Longitude coordinate (-180 to 180)

    Returns:
        Current weather information for the specified location
    """
    try:
        # Validate coordinates
        if not (-90 <= latitude <= 90):
            return {"success": False, "error": "Latitude must be between -90 and 90"}
        if not (-180 <= longitude <= 180):
            return {
                "success": False,
                "error": "Longitude must be between -180 and 180",
            }

        # Get weather data
        async with httpx.AsyncClient() as client:
            response = await client.get(
                WEATHER_API,
                params={
                    "latitude": latitude,
                    "longitude": longitude,
                    "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,wind_direction_10m",
                    "timezone": "auto",
                },
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

        current = data.get("current", {})
        units = data.get("current_units", {})

        return {
            "success": True,
            "location": {
                "latitude": latitude,
                "longitude": longitude,
                "timezone": data.get("timezone"),
            },
            "current": {
                "temperature": f"{current.get('temperature_2m')}{units.get('temperature_2m', '°C')}",
                "feels_like": f"{current.get('apparent_temperature')}{units.get('apparent_temperature', '°C')}",
                "humidity": f"{current.get('relative_humidity_2m')}{units.get('relative_humidity_2m', '%')}",
                "precipitation": f"{current.get('precipitation')}{units.get('precipitation', 'mm')}",
                "wind_speed": f"{current.get('wind_speed_10m')}{units.get('wind_speed_10m', 'km/h')}",
                "wind_direction": f"{current.get('wind_direction_10m')}°",
                "condition": get_weather_description(current.get("weather_code", 0)),
                "time": current.get("time"),
            },
        }

    except httpx.HTTPStatusError as e:
        return {"success": False, "error": f"API error: {e.response.status_code}"}
    except httpx.RequestError as e:
        return {"success": False, "error": f"Request error: {str(e)}"}
    except Exception as e:
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


@mcp.tool()
async def get_hourly_forecast(city: str, hours: int = 24) -> dict:
    """
    Get hourly weather forecast for a city.

    Args:
        city: Name of the city (e.g., "Seoul", "New York", "London")
        hours: Number of forecast hours (1-168, default: 24)

    Returns:
        Hourly weather forecast including temperature and conditions
    """
    try:
        # Validate hours parameter
        hours = max(1, min(168, hours))

        # Get city coordinates
        location = await geocode_city(city)
        if not location:
            return {"success": False, "error": f"City '{city}' not found"}

        # Get hourly forecast data
        async with httpx.AsyncClient() as client:
            response = await client.get(
                WEATHER_API,
                params={
                    "latitude": location["latitude"],
                    "longitude": location["longitude"],
                    "hourly": "temperature_2m,relative_humidity_2m,precipitation_probability,precipitation,weather_code,wind_speed_10m",
                    "timezone": location.get("timezone", "auto"),
                    "forecast_hours": hours,
                },
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

        hourly = data.get("hourly", {})
        units = data.get("hourly_units", {})

        forecast = []
        times = hourly.get("time", [])
        for i, time in enumerate(times):
            forecast.append(
                {
                    "time": time,
                    "temperature": f"{hourly.get('temperature_2m', [])[i]}{units.get('temperature_2m', '°C')}",
                    "humidity": f"{hourly.get('relative_humidity_2m', [])[i]}{units.get('relative_humidity_2m', '%')}",
                    "precipitation_probability": f"{hourly.get('precipitation_probability', [])[i]}%",
                    "precipitation": f"{hourly.get('precipitation', [])[i]}{units.get('precipitation', 'mm')}",
                    "wind_speed": f"{hourly.get('wind_speed_10m', [])[i]}{units.get('wind_speed_10m', 'km/h')}",
                    "condition": get_weather_description(
                        hourly.get("weather_code", [])[i]
                    ),
                }
            )

        return {
            "success": True,
            "location": {
                "city": location["name"],
                "country": location["country"],
                "region": location.get("admin1"),
            },
            "forecast_hours": len(forecast),
            "forecast": forecast,
        }

    except httpx.HTTPStatusError as e:
        return {"success": False, "error": f"API error: {e.response.status_code}"}
    except httpx.RequestError as e:
        return {"success": False, "error": f"Request error: {str(e)}"}
    except Exception as e:
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


@mcp.tool()
async def search_city(query: str, limit: int = 5) -> dict:
    """
    Search for cities by name.

    Args:
        query: City name to search for
        limit: Maximum number of results (1-10, default: 5)

    Returns:
        List of matching cities with their coordinates
    """
    try:
        limit = max(1, min(10, limit))

        async with httpx.AsyncClient() as client:
            response = await client.get(
                GEOCODING_API,
                params={"name": query, "count": limit, "language": "en", "format": "json"},
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

        if not data.get("results"):
            return {"success": True, "query": query, "results": [], "count": 0}

        cities = []
        for result in data["results"]:
            cities.append(
                {
                    "name": result.get("name"),
                    "country": result.get("country"),
                    "region": result.get("admin1"),
                    "latitude": result.get("latitude"),
                    "longitude": result.get("longitude"),
                    "timezone": result.get("timezone"),
                    "population": result.get("population"),
                }
            )

        return {"success": True, "query": query, "results": cities, "count": len(cities)}

    except httpx.HTTPStatusError as e:
        return {"success": False, "error": f"API error: {e.response.status_code}"}
    except httpx.RequestError as e:
        return {"success": False, "error": f"Request error: {str(e)}"}
    except Exception as e:
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8012)
