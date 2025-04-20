import requests
import json
import time
from typing import List, Dict, Any, Optional # Import for type hinting

# --- Configuration ---
# Consider loading sensitive data from environment variables or a secure config file.
# For demonstration, the key is passed during initialization.
# Using the flash model endpoint as per your curl command
GEMINI_API_ENDPOINT: str = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

# --- Exceptions ---
class GeminiAPIError(Exception):
    """Custom exception for errors during Gemini API interaction."""
    pass

class GeminiResponseParsingError(GeminiAPIError):
    """Custom exception for errors parsing the Gemini API response."""
    pass

class GeminiBlockedError(GeminiAPIError):
    """Custom exception when the Gemini API blocks a prompt or response."""
    pass

# --- Gemini API Client Class ---
class GeminiAPIClient:
    """
    Handles communication with the Google Gemini API, managing conversation history
    and generation parameters like max output tokens.
    """

    def __init__(
        self,
        api_key: str,
        endpoint: str = GEMINI_API_ENDPOINT,
        max_output_tokens: int = 150,
        temperature: float = 0.7,
        max_history_turns: Optional[int] = 20 # Optional: Limit history size (e.g., last 10 user/model pairs = 20 elements)
    ) -> None:
        """
        Initializes the Gemini API client.

        Args:
            api_key: Your Google Gemini API key.
            endpoint: The API endpoint URL for the model.
            max_output_tokens: Maximum number of tokens to generate in the response.
            temperature: Controls randomness (0.0 to 1.0).
            max_history_turns: Maximum number of conversation turns to keep in history.
                               None means keep all history.
        """
        if not api_key:
            raise ValueError("API key cannot be empty.")
        if not endpoint:
            raise ValueError("API endpoint cannot be empty.")
        if not isinstance(max_output_tokens, int) or max_output_tokens <= 0:
             raise ValueError("max_output_tokens must be a positive integer.")
        if not isinstance(temperature, (int, float)) or not (0.0 <= temperature <= 1.0):
             raise ValueError("temperature must be between 0.0 and 1.0.")
        if max_history_turns is not None and (not isinstance(max_history_turns, int) or max_history_turns < 0):
             raise ValueError("max_history_turns must be a non-negative integer or None.")


        self._api_key: str = api_key
        self._endpoint: str = endpoint
        self._max_output_tokens: int = max_output_tokens
        self._temperature: float = temperature
        self._max_history_turns: Optional[int] = max_history_turns

        # Conversation history: List of dicts with "role" and "parts"
        self._history: List[Dict[str, Any]] = []

        # Optional: Add initial context/system instruction if your model supports it
        # Example for some models (might need adjustment for Gemini 2.0 Flash):
        # self._history.append({"role": "system", "parts": [{"text": "You are a helpful robot assistant."}]})
        # Note: Always start with user/model turns after any initial system instruction.


    def send_message(self, user_input_text: str) -> str:
        """
        Sends a user message to the Gemini API, including conversation history.

        Updates the internal conversation history with both the user's message
        and the model's response. Handles API errors and response parsing.

        Args:
            user_input_text: The text message from the user.

        Returns:
            The generated text response from the model.

        Raises:
            GeminiAPIError: If there's an error during the API call or processing.
        """
        if not user_input_text or not user_input_text.strip():
             return "" # Don't send empty messages to the API

        # Add the user's input to the history
        self._history.append({"role": "user", "parts": [{"text": user_input_text.strip()}]}) # Store stripped text

        # Prepare the full conversation payload for the API call
        payload = self._build_payload()

        # Call the API
        response_data = self._call_api(payload)

        # Parse and extract the model's response text
        model_response_text = self._parse_model_response(response_data)

        # Add the model's response to the history if it's not empty (some responses might be blocked)
        if model_response_text.strip():
             self._history.append({"role": "model", "parts": [{"text": model_response_text.strip()}]}) # Store stripped text

        # Trim history if limit is set
        self._trim_history()

        return model_response_text

    def _build_payload(self) -> Dict[str, Any]:
        """Builds the API request payload including history and generation config."""
        # Create a copy of history to avoid modifying the internal list if needed during building
        current_history_for_payload = list(self._history)

        payload: Dict[str, Any] = {
            "contents": current_history_for_payload, # Send the entire history
            "generationConfig": {
                "maxOutputTokens": self._max_output_tokens,
                "temperature": self._temperature,
                # Add other generation parameters here if needed (e.g., top_p, top_k)
            },
            # Add safetySettings if you need to override default filters
            # "safetySettings": [...]
        }
        return payload

    def _call_api(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Makes the HTTP POST request to the Gemini API endpoint."""
        headers = {'Content-Type': 'application/json'}
        # The API key is passed as a query parameter for this endpoint
        api_url_with_key = f"{self._endpoint}?key={self._api_key}"

        try:
            # Use json=payload to automatically serialize the dict to JSON
            response = requests.post(api_url_with_key, json=payload)
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            return response.json() # Return the JSON response body as a Python dict

        except requests.exceptions.RequestException as e:
            # Catch specific request errors (network issues, bad status codes)
            print(f"API Request Error: {e}")
            # Log response text if available for debugging status code errors
            if e.response is not None:
                 print(f"Response Status Code: {e.response.status_code}")
                 print(f"Response Body: {e.response.text}")
            # Determine if it's a block error or just a request error
            if e.response is not None and e.response.status_code in (400, 429): # 400 for invalid requests/safety, 429 for rate limit
                 try:
                     error_response = e.response.json()
                     if 'error' in error_response and error_response['error'].get('message'):
                          error_message = error_response['error'].get('message')
                          print(f"API error message: {error_message}")
                          if "safety" in error_message.lower() or "block" in error_message.lower():
                               raise GeminiBlockedError(f"API blocked prompt: {error_message}") from e
                          elif "rate limit" in error_message.lower():
                               raise GeminiAPIError(f"API rate limited: {error_message}") from e
                          else:
                               raise GeminiAPIError(f"API returned error: {error_message}") from e
                 except (json.JSONDecodeError, KeyError):
                      pass # Couldn't parse error details, raise generic API error

            raise GeminiAPIError(f"Failed to call Gemini API: {e}") from e
        except json.JSONDecodeError as e:
             print(f"API Response JSON Decode Error: {e}")
             # Log raw response if possible
             # print(f"Raw response text: {response.text if 'response' in locals() else 'Not available'}")
             raise GeminiResponseParsingError(f"Invalid JSON response from API: {e}") from e


    def _parse_model_response(self, response_data: Dict[str, Any]) -> str:
        """
        Parses the JSON response from Gemini API to extract the model's text.

        Raises:
             GeminiResponseParsingError: If the expected data structure is missing.
             GeminiBlockedError: If the response or prompt was blocked.
        """
        # Check if candidates and extract text parts
        if 'candidates' in response_data and len(response_data['candidates']) > 0:
            candidate = response_data['candidates'][0]

            # Check if the candidate was blocked
            if 'finishReason' in candidate and candidate['finishReason'] in ('SAFETY', 'OTHER'):
                print(f"Candidate blocked with finish reason: {candidate['finishReason']}")
                # Check prompt feedback for more details on safety blocks
                if 'promptFeedback' in response_data and 'blockReason' in response_data['promptFeedback']:
                     print(f"Prompt blocked with reason: {response_data['promptFeedback']['blockReason']}")
                     # You could return a specific message based on the block reason
                raise GeminiBlockedError(f"Response blocked by API: {candidate['finishReason']}")

            # Extract text parts if content exists
            if 'content' in candidate and 'parts' in candidate['content']:
                 text_parts = "".join(part.get('text', '') for part in candidate['content']['parts'] if 'text' in part)

                 # Check for MAX_TOKENS finish reason and append indicator if text was generated
                 if 'finishReason' in candidate and candidate['finishReason'] == 'MAX_TOKENS':
                      if text_parts:
                           text_parts += "..." # Indicate the response was cut short
                      else:
                           text_parts = "(Response cut short)" # Should ideally not happen if text_parts is empty

                 if text_parts:
                     return text_parts.strip() # Return the cleaned text

        # If we reached here, the expected structure was not found or no text was generated
        print("Unexpected response structure or no text generated in candidates.")
        # print(f"Full response data: {response_data}") # Debugging line
        # Check if the *prompt* was blocked (might have promptFeedback even without candidates)
        if 'promptFeedback' in response_data and 'blockReason' in response_data['promptFeedback']:
             print(f"Prompt blocked by safety settings: {response_data['promptFeedback']['blockReason']}")
             raise GeminiBlockedError(f"Prompt blocked by API: {response_data['promptFeedback']['blockReason']}")


        # If no clear text or block reason, indicate an issue
        raise GeminiResponseParsingError("Could not extract valid text response from API data.")


    def _trim_history(self) -> None:
        """Trims the conversation history if max_history_turns is set."""
        # Ensure history length is even if max_history_turns is odd to keep user/model pairs together
        # Or simply keep the last N turns regardless of pairs
        if self._max_history_turns is not None and len(self._history) > self._max_history_turns:
             # Keep the last max_history_turns elements
             self._history = self._history[-self._max_history_turns:]
             # print(f"History trimmed. Current length: {len(self._history)}") # Debugging


    def get_history(self) -> List[Dict[str, Any]]:
        """Returns a copy of the current conversation history."""
        return list(self._history) # Return a copy to prevent external modification

    def clear_history(self) -> None:
        """Clears the conversation history."""
        self._history = []
        print("Conversation history cleared.")

    # You might add methods to save/load history to/from a file if needed for persistence
    # def save_history(self, filepath): ...
    # def load_history(self, filepath): ...
