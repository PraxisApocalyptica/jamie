import google.generativeai as genai
import logging

from google.api_core.exceptions import (
    GoogleAPIError, # Base exception for google-api-core
    ClientError, # Client-side errors (e.g., invalid request, permissions)
    ServerError, # Server-side errors (e.g., internal server error)
    RetryError, # Error after retries exhausted
    DeadlineExceeded, # Request timed out
    ResourceExhausted # Rate limit exceeded
)
from typing import List, Dict, Any, Optional

from src.ai.clients.constants import GEMINI as GeminiConstants
from src.ai.clients.gemini.exceptions import (
    GeminiAPIError,           # Your custom base API error
    GeminiResponseParsingError, # Your custom parsing error (less needed with client library)
    GeminiBlockedError        # Your custom blocked error
)


# --- Gemini Client Class ---
class GeminiClient: # Renamed the class
    """
    Handles communication with the Google Gemini API using the official client library,
    managing conversation history and generation parameters.
    """

    def __init__(
        self,
        api_key: str,
        config,
        speech_assistant,
        model_name: str = GeminiConstants.MODEL, # Use model name (e.g., "gemini-2.0-flash")
        max_output_tokens: int = 150,
        temperature: float = 0.7,
        max_history_turns: Optional[int] = None, # Manage history manually or let library handle
    ) -> None:
        """
        Initializes the Gemini client using the official library.

        Args:
            api_key: Your Google Gemini API key.
            model_name: The name of the Gemini model to use (defaults to flash model name from constants).
            max_output_tokens: Maximum number of tokens to generate in the response.
            temperature: Controls randomness (0.0 to 1.0).
            max_history_turns: Maximum number of conversation turns to keep in history.
                               Note: The official library's chat object *can* manage history automatically,
                               but manual trimming might still be needed for very long contexts or specific strategies.
                               Set to None to rely on the library's default context window.
        """
        self._logger = logging.getLogger(self.__class__.__name__)
        if not api_key:
            raise ValueError("API key cannot be empty.")
        if not model_name:
            raise ValueError("Model name cannot be empty.")
        if not isinstance(max_output_tokens, int) or max_output_tokens <= 0:
             raise ValueError("max_output_tokens must be a positive integer.")
        if not isinstance(temperature, (int, float)) or not (0.0 <= temperature <= 1.0):
             raise ValueError("temperature must be between 0.0 and 1.0.")
        # Validate max_history_turns if managing manually
        if max_history_turns is not None and (not isinstance(max_history_turns, int) or max_history_turns < 0):
             raise ValueError("max_history_turns must be a non-negative integer or None.")

        self.config=config
        self.name=self.config.get('name')
        self.purpose=self.config.get('purpose')

        self.speech_assistant=speech_assistant

        self._api_key: str = api_key
        self._model_name: str = model_name
        self._generation_config: Dict[str, Any] = {
            "max_output_tokens": max_output_tokens, # Note: Parameter name in library often snake_case
            "temperature": temperature,
            # Add other generation parameters here if needed
        }
        self._max_history_turns: Optional[int] = max_history_turns

        # Configure the generativeai library with the API key
        genai.configure(api_key=self._api_key)

        # Get the generative model instance
        self._model = genai.GenerativeModel(self._model_name)

        # Start a chat session. This object manages the conversation history internally.
        # We will manage trimming externally if _max_history_turns is not None.
        self._chat = self._model.start_chat(history=[]) # Start with empty history initially

        # Optional: Initialize history with a system instruction if supported and desired
        # Note: System instructions are often passed directly when starting the chat or model,
        # depending on the model version and library support. Gemini 2.0 Flash might be limited here.
        # Example if adding initial turns (ensure they are user/model pairs):
        # self._chat = self._model.start_chat(history=[
        #     {"role": "user", "parts": [{"text": "You are a helpful robot assistant."}]},
        #     {"role": "model", "parts": [{"text": "Okay, I will be a helpful robot assistant!"}]}
        # ])
        # If initializing with history, update _history list to match _chat.history if needed for manual trimming


    def send_message(self, user_input_text: str) -> str:
        """
        Sends a user message to the Gemini API using the chat session.

        Updates the internal chat history managed by the client library.
        Handles API errors and response parsing.

        Args:
            user_input_text: The text message from the user.

        Returns:
            The generated text response from the model.

        Raises:
            GeminiAPIError: For general API errors (network, server, rate limit, etc.).
            GeminiBlockedError: If the prompt or response was blocked by the API.
        """
        if not user_input_text or not user_input_text.strip():
             return "" # Don't send empty messages

        # Trim history *before* sending the new message if managing manually
        self._trim_history()
        # The send_message call *appends* the user input internally

        try:
            # Send the message to the chat session
            # The library automatically manages appending user message and history
            response = self._chat.send_message(
                user_input_text.strip(), # Send the cleaned text
                generation_config=self._generation_config,
                # Add safety_settings if needed
            )

            # The library handles the API call and basic parsing.
            # Access the text from the response object.
            # Check if the response was blocked before trying to access text.
            # The library often raises exceptions for blocks, but checking status is good practice.
            # Example check (syntax might vary slightly based on library version):
            # if response.prompt_feedback and response.prompt_feedback.block_reason:
            #      raise GeminiBlockedError(f"Prompt blocked: {response.prompt_feedback.block_reason}")
            # if response.candidates and any(c.finish_reason == genai.enums.protos.generative_service.FinishReason.SAFETY for c in response.candidates):
            #      raise GeminiBlockedError("Response blocked by safety settings.")
            # A more robust way is to catch the specific exceptions raised by the library.

            # The library will raise exceptions for blocks, rate limits, etc.
            # If no exception, response should contain content.
            # Access the text; library handles parsing parts
            model_response_text = response.text # Access the generated text directly

            if model_response_text is None:
                # Should not happen often if no exception was raised, but as a safeguard
                 self._logger.debug("API returned response object but text was None.")
                 raise GeminiResponseParsingError("API returned empty text response.")

            # The library's chat object automatically appends the model's response to history.
            # We don't need to manually append here.

            return model_response_text.strip() # Return the cleaned text

        except (ClientError, ServerError, RetryError, DeadlineExceeded, ResourceExhausted) as e:
            # Catch specific exceptions raised by google-generativeai/google-api-core
            self._logger.error(f"Google API Error caught: {type(e).__name__}: {e}")

            # Map Google's exceptions to your custom exceptions
            if isinstance(e, ResourceExhausted):
                raise GeminiAPIError(f"Rate limit exceeded: {e}") from e # Map rate limit to your API error
            elif isinstance(e, ClientError):
                 # ClientError can indicate invalid requests, permission denied, safety blocks etc.
                 # Check error message or status code if available to refine mapping
                 error_message = str(e)
                 if "safety" in error_message.lower() or "block" in error_message.lower() or "invalid argument" in error_message.lower():
                      raise GeminiBlockedError(f"API blocked prompt/request: {error_message}") from e
                 else:
                      raise GeminiAPIError(f"Client error during API call: {error_message}") from e
            elif isinstance(e, (ServerError, RetryError, DeadlineExceeded)):
                # Other server or retry errors
                raise GeminiAPIError(f"API request failed: {e}") from e
            else:
                 # Catch any other potential Google API errors
                 raise GeminiAPIError(f"An unexpected Google API error occurred: {e}") from e

        except Exception as e:
            # Catch any other unexpected Python errors
            self._logger.error(f"An unexpected error occurred during the API call: {type(e).__name__}: {e}")
            raise GeminiAPIError(f"An unexpected error occurred: {e}") from e


    def _trim_history(self) -> None:
        """Trims the conversation history if max_history_turns is set."""
        # Note: The official library's chat object manages history.
        # We might trim the history list *before* sending a message if we
        # want to enforce a context window smaller than the model's max context.
        # However, the send_message method *adds* the current user message
        # *then* sends the history. So manual trimming needs careful handling
        # of the history list state _before_ the send_message call.

        # A simpler approach is to let the library manage history up to the model's
        # context window, UNLESS you need to explicitly limit turns for cost or
        # performance *below* the model's limit.

        # If self._max_history_turns is None, rely on the library's context window.
        if self._max_history_turns is None:
            return # No manual trimming desired

        # If we need to trim manually:
        # Get the current history from the chat object
        current_history = self._chat.history
        if len(current_history) > self._max_history_turns:
            self._logger.warning(f"History length {len(current_history)} exceeds max {self._max_history_turns}. Trimming.")
            # Trim the history list. Keep the last N turns.
            trimmed_history = current_history[-self._max_history_turns:]
            # Replace the chat object's history with the trimmed history
            # Note: Replacing chat history might require creating a new chat object
            # or using a specific method if provided by the library.
            # Example (syntax might vary or not be directly possible):
            # self._chat.history = trimmed_history # This direct assignment might NOT work
            # A more likely approach if direct assignment isn't possible is to
            # create a *new* chat object with the trimmed history.

            # Example of creating a new chat object with trimmed history:
            self._chat = self._model.start_chat(history=trimmed_history)
            self._logger.debug(f"History trimmed. New length: {len(self._chat.history)}")
        # Note: If you trim, the *current* user message is appended *after* trimming the old history.


    def get_history(self) -> List[Dict[str, Any]]:
        """Returns a copy of the current conversation history."""
        # Get history from the chat object
        if self._chat:
             # History from the library's chat object is a list of Content objects.
             # Convert it to the dict format if you need consistency with manual representation.
             # The Content object structure is {"role": str, "parts": list[Part]}
             return [turn.to_dict() for turn in self._chat.history] # Use to_dict() method if available
        return []


    def clear_history(self) -> None:
        """Clears the conversation history."""
        # Clearing history requires creating a new chat object
        if self._model:
             self._chat = self._model.start_chat(history=[])
             self._logger.debug("Conversation history cleared.")
        else:
             self._logger.warning("Model not initialized, cannot clear history.")


    def start(self) -> None:
        try:

            # Simulate a conversation
            self._logger.info("\nStarting conversation (type 'exit' to exit)...")
            history=" ".join(initial_history.format(
                name=self.name,
                purpose=self.purpose
            ) for initial_history in GeminiConstants.HISTORY)
            self.send_message(history)

            while True:
                user_input = input("You: ")
                if user_input.lower() == 'exit':
                    break
                if user_input.lower() == 'clear history':
                    self.clear_history()
                    self.send_message(history)
                    self._logger.debug("History cleared.")
                    continue
                if user_input.lower() == 'show history':
                    self._logger.debug("--- History ---")
                    history = self.get_history()
                    if history:
                        for i, turn in enumerate(history):
                            # Handle accessing parts safely
                            text_snippet = ""
                            if 'parts' in turn and isinstance(turn['parts'], list):
                                for part in turn['parts']:
                                    if 'text' in part:
                                        text_snippet += part['text']
                                        break # Assume first text part is sufficient
                            self._logger.info(f"{i}: {turn.get('role', 'unknown')}: {text_snippet[:80]}...") # Print first 80 chars
                    else:
                        self._logger.info("History is empty.")
                    self._logger.debug("---------------")
                    continue


                try:
                    # Send the message and get the response
                    response = self.send_message(user_input)
                    print(f"{self.name}: {response}")
                    self.speech_assistant.synthesize_and_speak(response)

                except GeminiBlockedError as e:
                    self._logger.error(f"{self.name}: I cannot respond to that query. ({e})")
                except GeminiAPIError as e:
                    self._logger.error(f"{self.name} encountered an API error: {e}")
                    # In a real robot, you might speak an error message
                except Exception as e:
                    self._logger.critical(f"An unexpected error occurred during conversation: {e}")
                    import traceback
                    traceback.print_exc() # Print traceback

                # Optional: Add a small delay between turns
                # time.sleep(1.0)

        except ValueError as e:
            self._logger.error(f"Client Initialization Error: {e}")
        except ImportError as e:
            self._logger.error(f"Import Error: {e}. Make sure you have installed 'google-generativeai' and your local modules are correctly structured.")
        except Exception as e:
            self._logger.critical(f"An unexpected error occurred during setup or main execution: {e}")
            import traceback
            traceback.print_exc()

        self._logger.info("Conversation ended.")

    # You might add methods to save/load history to/from a file if needed for persistence
    # def save_history(self, filepath): ...
    # def load_history(self, filepath): ...
