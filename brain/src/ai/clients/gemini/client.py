import google.generativeai as genai
import logging
import re

from google.api_core.exceptions import (
    ClientError, ServerError, RetryError, DeadlineExceeded,
    ResourceExhausted, InvalidArgument, InternalServerError, BadRequest
)
from typing import Dict, Any, Optional, Union

from src.ai.clients.constants import GEMINI as GeminiConstants, MEMORY

from src.ai.clients.gemini.exceptions import (
    GeminiAPIError, GeminiResponseParsingError, GeminiBlockedError
)
from src.ai.mind.memory import Memory


# --- Gemini Client Class with Encrypted Concatenated Memory Fragments Persistence ---
class GeminiClient(Memory):
    """
    Handles communication with the Google Gemini API using the official client library,
    managing conversation memory as encrypted fragments and the current session's history.

    Persists memory as multiple encrypted concatenated string fragments using a FileProtector.

    Memory Management Strategy:
    - Memory is stored as individual encrypted files ("fragments") in a directory.
    - On startup, *all* existing fragment files are loaded, decrypted, and stored
      internally as a list of strings (`self._memory_fragments`).
    - The generativeai `ChatSession` object (`self._chat`) is initialized with an empty history.
    - The *first* message sent to the model includes a concatenated string of *all loaded memory fragments*
      prepended with context headers, followed by the standard initial instructions and a starting prompt.
      This provides historical context to the model without stuffing it into the `_chat.history` itself
      turn-by-turn.
    - Subsequent messages use the `self._chat` object's `send_message` method, which automatically
      manages the *current session's* turn-by-turn history for immediate context. The loaded
      memory fragments are *not* included in these subsequent messages.
    - When saving (e.g., on exit), the *current session's history* (retrieved from `self._chat.history`)
      is formatted into a single concatenated string (trimmed if `max_history_turns` is set).
      This string is then encrypted and saved as a *new* fragment file in the memory directory,
      incrementing the fragment index. It does *not* modify or overwrite previous fragments.
    - Clearing memory involves deleting *all* fragment files and resetting the `self._chat` object.
    """

    def __init__(
        self,
        api_key: str,
        config: Dict[str, Any],
        model_name: str = GeminiConstants.MODEL,
        max_output_tokens: int = 150,
        temperature: float = 0.7,
        max_history_turns: Optional[Union[int, str]] = None,
        memory_file_prefix: Optional[str] = MEMORY.NAME,
        memory_location: str = MEMORY.LOCATION,
        fragment_extension: str = MEMORY.FRAGMENT_EXTENSION,
        speech_assistant = None,
        remember_memories: bool = False,
    ) -> None:
        """
        Initializes the Gemini client, configuring the API, initializing the FileProtector,
        and loading encrypted memory fragments as a list of strings.

        Args:
            api_key: Your Google Gemini API key.
                     WARNING: In this version, used as the encryption password for memory.
                     This is HIGHLY INSECURE and should be replaced with a separate,
                     user-provided password or a more secure key management method
                     in production environments.
            config: Configuration dictionary for the agent (e.g., 'name', 'purpose').
            model_name: The name of the Gemini model to use (e.g., 'gemini-pro').
            max_output_tokens: Maximum number of tokens for the model's response.
            temperature: Controls response randomness (0.0 to 1.0).
            max_history_turns: Maximum number of conversation turns (user+model pairs)
                               from the *current session* to include when saving it as a
                               new memory fragment. If None, all turns from the current
                               session are saved as one fragment. If 0, an empty fragment
                               is effectively saved (doesn't create a file if empty).
                               History is trimmed *before* formatting and saving.
                               Note: This does *not* limit the number of *loaded* memory fragments.
            memory_file_prefix: Optional prefix for memory fragment files (e.g., 'memory_'). If None,
                                memory persistence is disabled.
            memory_location: Directory where the memory fragment files will be stored. Created if it doesn't exist.
            fragment_extension: The file extension for encrypted memory fragments (e.g., '.enc').

        Raises:
            ValueError: If essential initialization parameters are invalid.
            ImportError: If required libraries are not installed or constants are missing.
            RuntimeError: If Gemini model initialization fails.
        """
        self._logger = logging.getLogger(self.__class__.__name__)
        super().__init__(api_key, max_history_turns, memory_file_prefix,
                       memory_location, fragment_extension, remember_memories)

        # --- Input Validation ---
        if not api_key:
            raise ValueError("API key cannot be empty.")
        if not model_name:
            raise ValueError("Model name cannot be empty.")
        if not isinstance(max_output_tokens, int) or max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be a positive integer.")
        if not isinstance(temperature, (int, float)) or not (0.0 <= temperature <= 1.0):
            raise ValueError("temperature must be between 0.0 and 1.0.")

        self.config = config if config is not None else {}
        self.name: str = self.config.get('name', 'AI')
        self.purpose: str = self.config.get('purpose', 'engage in conversation')

        self._api_key: str = api_key
        self._model_name: str = model_name
        self._generation_config: Dict[str, Any] = {
            "max_output_tokens": max_output_tokens,
            "temperature": temperature,
        }
        self.remember_memories = remember_memories

        # --- Configure the generativeai library ---
        try:
            genai.configure(api_key=self._api_key)
            self._model = genai.GenerativeModel(self._model_name)
            self._logger.debug(f"GenerativeModel '{self._model_name}' loaded.")
        except Exception as e:
            self._logger.critical(f"Failed to configure genai or load model '{self._model_name}': {e}", exc_info=True)
            raise RuntimeError(f"Could not initialize Gemini model: {e}") from e

        # The chat object starts empty; loaded memory is added to the *first* prompt.
        self._chat = self._model.start_chat(history=[])
        self.speech_assistant = speech_assistant
        self.start()
        self._logger.debug("Chat session started with empty history.")

    def get_name(self):
        return self.name

    def start(self) -> None:
        """
        Starts the interactive conversation loop in the console.
        Loads memory fragments, sends initial context/instructions including loaded fragments,
        and processes user input until the exit command. Saves the current session's history
        as a new fragment on exit.
        """
        try:
            recent_thoughts = self.get_recent_thoughts()

            if recent_thoughts:
                try:
                    # Send the initial message. The model's response will be added to _chat.history.
                    # We use communicate directly, which calls the chat object's send_message.
                    self.communicate(recent_thoughts)
                    self._logger.info("Initial context message sent successfully.")

                except Exception as e:
                    self._logger.error(f"Error sending initial context message to model: {e}", exc_info=True)


        except (ValueError, ImportError, RuntimeError) as e:
            # Catch potential errors during client initialization or setup that might occur before the loop
            self._logger.critical(f"Critical Initialization/Runtime Error before conversation loop started or during execution: {e}", exc_info=True)
        except Exception as e:
            # Catch any unhandled exception that might escape the loop or setup
            self._logger.critical(f"An unhandled exception occurred during client execution: {type(e).__name__}: {e}", exc_info=True)


    async def communicate(self, user_input_text: str) -> str:
        """
        Sends a user message to the Gemini API via the chat object, processes the response,
        handles errors, and returns the model's text response.

        Note: Loaded memory fragments are *not* automatically prepended to every message.
        They are included only in the *first* message sent via the `start` method.
        The `_chat` object manages the recent conversation history internally.
        """
        if not user_input_text or not user_input_text.strip():
            self._logger.warning("Attempted to send empty user input.")
            return ""

        try:
            # Get current history length *before* sending to get an accurate log of session turns
            current_history_len = len(self._chat.history) if self._chat and hasattr(self._chat, 'history') else 0
            self._logger.debug(f"Sending message to model ({current_history_len} turns in session history): {user_input_text[:150]}...")
            if not self._chat:
                raise RuntimeError("Chat object is not initialized.")

            # Send the message to the Gemini model using the chat object
            # This adds the message to the chat's internal history and uses that history for context.
            response = self._chat.send_message(
                user_input_text.strip(),
                generation_config=self._generation_config,
            )
            self._logger.debug("Received response object from model.")
            self._logger.debug(f"Response has {len(response.candidates) if response.candidates else 0} candidates. Prompt Feedback: {response.prompt_feedback}")

            # Check for blocking feedback
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                block_reason_name = response.prompt_feedback.block_reason.name
                safety_details_list = []
                if response.prompt_feedback.safety_ratings:
                    for rating in response.prompt_feedback.safety_ratings:
                        safety_details_list.append(f"{rating.category.name}: {rating.probability.name}")
                block_details = f"Prompt blocked by safety settings ({block_reason_name}). Details: {'; '.join(safety_details_list) if safety_details_list else 'No details provided.'}"
                self._logger.warning(block_details)
                raise GeminiBlockedError(block_details)

            # Check if response contains expected content
            if not response.candidates or not response.candidates[0].content or not response.candidates[0].content.parts:
                candidate_finish_reasons = [str(c.finish_reason) for c in response.candidates if hasattr(c, 'finish_reason')] if response.candidates else ["N/A"]
                self._logger.warning(f"API returned a response with no content candidates or parts. Finish reasons: {', '.join(candidate_finish_reasons)}")
                raise GeminiResponseParsingError(f"API returned response object with no text content. Finish reasons: {', '.join(candidate_finish_reasons)}")

            # Extract text from the response parts
            model_response_parts = []
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'text') and isinstance(part.text, str):
                    model_response_parts.append(part.text)
                elif part is not None: # Log non-text parts if present
                    self._logger.debug(f"Ignoring non-text part in model response: {type(part).__name__}")

            model_response_text = "".join(model_response_parts).strip()

            if not model_response_text:
                self._logger.warning("API returned response object, but extracted text was empty after stripping.")
                # Re-check block reason in case it was missed earlier or is implicit
                if response.prompt_feedback and response.prompt_feedback.block_reason:
                    block_reason_name = response.prompt_feedback.block_reason.name
                    raise GeminiBlockedError(f"Prompt blocked by safety settings: {block_reason_name} (and returned empty text)")
                raise GeminiResponseParsingError("API returned empty text response after extraction.")

            # Attempt to remove potential model-generated prefixes like "--- AI (Turn 1) ---"
            # This regex might need adjustment based on actual model output.
            try:
                escaped_name = re.escape(self.name)
                # This pattern is less specific about turn number, just looking for the format
                prefix_pattern = re.compile(rf'^---\s*{escaped_name}\s*\(.*\)\s*---\s*', re.IGNORECASE)
                match = prefix_pattern.match(model_response_text)
                if match:
                    original_response_length = len(model_response_text)
                    model_response_text = model_response_text[match.end():].strip()
                    self._logger.debug(f"Removed potential model-generated prefix. Original length: {original_response_length}, New length: {len(model_response_text)}")
                else:
                     # Also check for simpler patterns like "AI:" or "Model:" if the structured one isn't used
                    simple_prefix_pattern = re.compile(rf'^{escaped_name}:\s*', re.IGNORECASE)
                    match = simple_prefix_pattern.match(model_response_text)
                    if match:
                        original_response_length = len(model_response_text)
                        model_response_text = model_response_text[match.end():].strip()
                        self._logger.debug(f"Removed potential simple model-generated prefix. Original length: {original_response_length}, New length: {len(model_response_text)}")

            except Exception as e:
                self._logger.warning(f"Error during response prefix removal regex: {e}", exc_info=True) # Log regex errors but don't fail


            self._logger.debug(f"Final processed response text (after cleaning): {model_response_text[:150]}...")
            if self.speech_assistant and model_response_text:
                # Speak the model_response_text if speech assistant is available
                if hasattr(self.speech_assistant, 'synthesize_and_speak'):
                    self.speech_assistant.synthesize_and_speak(model_response_text)
                else:
                    self._logger.debug("speech_assistant is not initialized or missing synthesize_and_speak method.")
            return model_response_text

        # --- Specific API Error Handling ---
        except (BadRequest, InvalidArgument) as e:
            self._logger.error(f"Google API Client Error (Bad Request/Invalid Argument): {type(e).__name__}: {e}", exc_info=True)
            error_message = str(e)
            if "safety" in error_message.lower() or "block" in error_message.lower() or "harm" in error_message.lower():
                raise GeminiBlockedError(f"API error likely related to content/safety or invalid request format: {error_message}") from e
            else:
                raise GeminiAPIError(f"Client error (Invalid Request) during API call: {error_message}") from e

        except ResourceExhausted as e:
            self._logger.error(f"Google API Error (Resource Exhausted/Rate Limit): {type(e).__name__}: {e}", exc_info=True)
            raise GeminiAPIError(f"Rate limit or resource quota exceeded: {str(e)}") from e

        except (InternalServerError, ServerError) as e:
            self._logger.error(f"Google API Server Error: {type(e).__name__}: {e}", exc_info=True)
            raise GeminiAPIError(f"API server error: {str(e)}") from e

        except (RetryError, DeadlineExceeded) as e:
            self._logger.error(f"Google API Network/Retry Error: {type(e).__name__}: {e}", exc_info=True)
            # Check for specific safety/block reasons within the error message if available
            error_message = str(e)
            if "safety" in error_message.lower() or "block" in error_message.lower() or "harm" in error_message.lower():
                raise GeminiBlockedError(f"API request timed out or failed after retries, likely due to content/safety: {error_message}") from e
            else:
                raise GeminiAPIError(f"API request failed after retries or exceeded deadline: {str(e)}") from e

        except ClientError as e:
            self._logger.error(f"Google API Client Error (General): {type(e).__name__}: {e}", exc_info=True)
            # Catch any other ClientError not specifically handled
            raise GeminiAPIError(f"A general client error occurred during API call: {str(e)}") from e

        # --- Custom Exceptions (Re-raise) ---
        except GeminiBlockedError:
            raise # Re-raise the specific blocked error

        except GeminiResponseParsingError:
            raise # Re-raise the specific parsing error

        # --- Catch All Other Exceptions ---
        except Exception as e:
            self._logger.critical(f"An unexpected critical error occurred during communicate: {type(e).__name__}: {e}", exc_info=True)
            # Wrap any other unexpected errors in a general API error
            raise GeminiAPIError(f"An unexpected internal error occurred during message processing: {e}") from e


    def shutdown(self):
        # Ensure memory is saved when the program exits the try/except block
        self._logger.debug("Exiting conversation. Attempting to save current session history as a new memory fragment...")
        if self.remember_memories:
            try:
                self._save_current_memory_as_fragment() # Call the new save method
                self._logger.debug("Finished storing current session as a memory fragment.")
            except Exception as e:
                # Catch any exceptions specifically during the save process
                self._logger.error(f"An error while saving current session history as a memory fragment: {e}", exc_info=True)

        self._logger.info("--- Conversation Ended ---")
