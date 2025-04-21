# This module will handle communication with external APIs (e.g., weather, time, news)
# if your robot friend needs access to real-world information.

import requests
import json
# Add other libraries as needed for specific APIs

class ExternalApiClient:
    """Handles communication with external web APIs."""

    def __init__(self, api_key=None):
        # Initialize with API keys or configuration for external services
        self.api_key = api_key # Example API key
        # Add base URLs, authentication methods, etc.

    def get_weather(self, location: str) -> str:
        """Example method to get weather information."""
        # <<<<< IMPLEMENT WEATHER API CALL >>>>>
        # Use 'requests' to call a weather API (e.g., OpenWeatherMap, WeatherAPI.com)
        # Requires signing up for the service and getting an API key
        print(f"TODO: Call weather API for {location}")
        try:
            # Example API call structure (replace with actual API endpoint and params)
            # url = f"https://api.weatherapi.com/v1/current.json?key={self.api_key}&q={location}"
            # response = requests.get(url)
            # response.raise_for_status() # Raise an exception for bad status codes
            # data = response.json()
            # weather_desc = data['current']['condition']['text']
            # temp_c = data['current']['temp_c']
            # return f"The weather in {location} is {weather_desc} with a temperature of {temp_c}°C."
            return f"Checking weather for {location}... (API call not implemented)" # Placeholder

        except requests.exceptions.RequestException as e:
            print(f"Error calling weather API: {e}")
            return f"I'm sorry, I couldn't get the weather for {location} right now."
        except Exception as e:
            print(f"An unexpected error occurred getting weather: {e}")
            return "I encountered an error trying to get the weather."

    # Add other methods for different external services (e.g., get_time, get_news_headlines)
    # def get_time(self, timezone=None): ...
    # def get_news(self, category=None): ...

# --- Example Usage (in DialogueManager or TaskManager) ---
# # Inside JamieRobot.__init__
# # self.external_api_client = ExternalApiClient(api_key=self.config['api_keys'].get('weather')) # Load key from config
# # Inside DialogueManager's response generation logic when user asks "What's the weather in X?"
# # location = ... # Extract location from NLU entities
# # weather_info = self.external_api_client.get_weather(location)
# # self.speak(weather_info) # Send text to Vision for TTS
