import google.generativeai as genai
import logging
import json # Keep import, might be useful for debugging/future changes
import os
import textwrap
import re
import time # Useful for potential retries or timing

# Import the new FileProtector class
from src.protectors.file_protector import FileProtector # Adjust path as needed

from google.api_core.exceptions import (
    ClientError,
    ServerError,
    RetryError,
    DeadlineExceeded,
    ResourceExhausted,
    InvalidArgument,
    InternalServerError, # More specific server error
    BadRequest # More specific client error for invalid requests
)
from typing import List, Dict, Any, Optional

# Assume these exist based on your imports
# Assume GeminiConstants includes definitions like KDF_SALT_SIZE, KDF_ITERATIONS,
# ENCRYPTION_ALGORITHM = algorithms.AES, ENCRYPTION_MODE = modes.GCM,
# AES_KEY_SIZE = 32, IV_NONCE_SIZE = 12 etc. AND HISTORY (or HISTORY_INSTRUCTIONS)
from src.ai.clients.constants import GEMINI as GeminiConstants, MEMORY, COMMANDS
# Assume custom exceptions exist
from src.ai.clients.gemini.exceptions import (
    GeminiAPIError,
    GeminiResponseParsingError,
    GeminiBlockedError
)


# --- Gemini Client Class with Encrypted Concatenated History Persistence ---
class GeminiClient:
    """
    Handles communication with the Google Gemini API using the official client library,
    managing conversation history and generation parameters.

    Persists history as a single encrypted concatenated string using a FileProtector.

    Note on History Management:
    - On startup, the previously saved *concatenated* history string is loaded.
    - This loaded string is *not* added turn-by-turn to the generativeai chat object's history.
    - Instead, the loaded string is included as part of the *first* message sent to the API
      in the new session, providing context to the model.
    - The generativeai chat object (`self._chat`) then manages the history of the *current*
      session's turns (the initial message + subsequent user/model turns).
    - When saving, the history is retrieved from the *current* session's chat object
      (trimmed if max_history_turns is set), formatted into a single concatenated string,
      encrypted, and saved, overwriting the previous history file.
    """

    def __init__(
        self,
        api_key: str,
        config: Dict[str, Any],
        speech_assistant: Any, # Use a more specific type hint if available
        model_name: str = GeminiConstants.MODEL,
        max_output_tokens: int = 150,
        temperature: float = 0.7,
        max_history_turns: Optional[int] = None,
        history_file: Optional[str] = MEMORY.NAME,
        history_dir: str = MEMORY.TYPE, # Added explicit history directory parameter
    ) -> None:
        """
        Initializes the Gemini client, configuring the API, initializing the FileProtector,
        and loading encrypted history as a single block if available.

        Args:
            api_key: Your Google Gemini API key.
                     WARNING: In this version, used as the encryption password for history.
                     This is HIGHLY INSECURE and should be replaced with a separate,
                     user-provided password or a more secure key management method
                     in production environments.
            config: Configuration dictionary for the agent (e.g., 'name', 'purpose').
            speech_assistant: An object handling speech synthesis (must have synthesize_and_speak method).
            model_name: The name of the Gemini model to use (e.g., 'gemini-pro').
            max_output_tokens: Maximum number of tokens for the model's response.
            temperature: Controls response randomness (0.0 to 1.0).
            max_history_turns: Maximum number of conversation turns (user+model pairs)
                               to include when saving the history. If None, all turns
                               from the current session are saved. History is trimmed
                               *before* formatting and saving. Note: Loaded history
                               is sent as a single initial message, not added as turns.
            history_file: Optional basename for the encrypted history file. If None,
                          history persistence is disabled.
            history_dir: Directory where the history file will be stored. Created if it doesn't exist.

        Raises:
            ValueError: If essential initialization parameters are invalid.
            ImportError: If required libraries are not installed or constants are missing.
        """
        self._logger = logging.getLogger(self.__class__.__name__)

        # --- Input Validation ---
        if not api_key:
            raise ValueError("API key cannot be empty.")
        if not model_name:
            raise ValueError("Model name cannot be empty.")
        if not isinstance(max_output_tokens, int) or max_output_tokens <= 0:
             raise ValueError("max_output_tokens must be a positive integer.")
        if not isinstance(temperature, (int, float)) or not (0.0 <= temperature <= 1.0):
             raise ValueError("temperature must be between 0.0 and 1.0.")
        if max_history_turns is not None and (not isinstance(max_history_turns, int) or max_history_turns < 0):
             raise ValueError("max_history_turns must be a non-negative integer or None.")
        if history_file is not None and not isinstance(history_file, str):
             raise ValueError("history_file must be a string basename or None.")
        if not isinstance(history_dir, str) or not history_dir:
             raise ValueError("history_dir must be a non-empty string.")

        self.config = config if config is not None else {} # Ensure config is a dict
        self.name: str = self.config.get('name', 'AI')
        self.purpose: str = self.config.get('purpose', 'engage in conversation')
        self.speech_assistant: Any = speech_assistant # Store the speech assistant object

        self._api_key: str = api_key
        self._model_name: str = model_name
        self._generation_config: Dict[str, Any] = {
            "max_output_tokens": max_output_tokens,
            "temperature": temperature,
        }
        self._max_history_turns: Optional[int] = max_history_turns

        # Construct full history file path
        self._history_file_path: Optional[str] = None
        if history_file is not None:
             self._history_file_path = os.path.join(history_dir, history_file)

        # --- Initialize File Protector ---
        # WARNING: Still using API key as password here. INSECURE.
        self._password: str = api_key # Required for FileProtector
        self._file_protector: Optional[FileProtector] = None

        if self._history_file_path: # Only initialize protector if persistence is enabled
             try:
                 # Basic check for required constants before passing
                 if not all(hasattr(GeminiConstants, attr) for attr in ['KDF_SALT_SIZE', 'KDF_ITERATIONS', 'ENCRYPTION_ALGORITHM', 'ENCRYPTION_MODE', 'AES_KEY_SIZE', 'IV_NONCE_SIZE']):
                      raise AttributeError("GeminiConstants is missing required cryptographic attributes.")

                 # Pass the relevant constants/config object to FileProtector
                 self._file_protector = FileProtector(self._password, GeminiConstants)
                 self._logger.debug("FileProtector initialized successfully.")
             except (ValueError, AttributeError, ImportError) as e:
                 self._logger.error(f"Failed to initialize FileProtector. History persistence disabled. Error: {e}", exc_info=True)
                 self._file_protector = None # Disable persistence
                 self._history_file_path = None # Ensure persistence path is also nullified


        # --- Configure the generativeai library ---
        try:
             genai.configure(api_key=self._api_key)
             # Optional: Check if model exists/is available
             # self._model = genai.get_model(self._model_name) # This makes __init__ slower, might defer
             self._model = genai.GenerativeModel(self._model_name)
             self._logger.debug(f"GenerativeModel '{self._model_name}' loaded.")
        except Exception as e:
             self._logger.critical(f"Failed to configure genai or load model '{self._model_name}': {e}", exc_info=True)
             # Re-raise or handle based on whether failure here is fatal
             raise RuntimeError(f"Could not initialize Gemini model: {e}") from e


        # --- Start a chat session with an empty history initially. ---
        # History is added *after* loading, as part of the first message.
        self._chat = self._model.start_chat(history=[])
        self._logger.debug("Chat session started with empty history.")

        # --- Load history on startup ---
        self._loaded_history_text: Optional[str] = None
        # Only attempt load if FileProtector was successfully initialized and a file path exists
        if self._file_protector and self._history_file_path and os.path.exists(self._history_file_path):
             self._loaded_history_text = self._load_history() # This now calls FileProtector
             if self._loaded_history_text:
                 self._logger.info(f"Loaded previous conversation history from {self._history_file_path} ({len(self._loaded_history_text)} chars).")
             else:
                 self._logger.warning(f"Could not load history from {self._history_file_path} or file was empty/corrupt.")
        elif self._history_file_path:
             self._logger.debug(f"History file {self._history_file_path} not found or persistence disabled. Starting fresh.")
        else:
             self._logger.debug("History persistence is disabled.")


    def _format_history_for_saving(self, history_list: List[Dict[str, Any]]) -> str:
        """
        Formats the chat history (list of dicts from self.get_history()) into a
        single string representation suitable for saving and later sending
        back to the model as context.

        Includes role labels and separates turns explicitly for clarity for the model.

        Args:
            history_list: A list of turn dictionaries (as returned by self.get_history()).

        Returns:
            A single string representing the formatted history.
        """
        formatted_text = ""
        if not history_list:
            return formatted_text

        # Add a simple header to make it clear what this block is
        formatted_text += f"{MEMORY.HEADER}\n\n"

        for turn in history_list:
            role = turn.get('role', 'unknown')
            text_content = ""
            if 'parts' in turn and isinstance(turn['parts'], list):
                for part in turn['parts']:
                    # Concatenate text parts within a single turn
                    if isinstance(part, dict) and 'text' in part and isinstance(part['text'], str):
                         text_content += part.get('text', '')

            if text_content.strip():
                # Use API roles ('user' or 'model') but capitalize for display/model clarity
                display_role = role.capitalize() if role in ['user', 'model'] else role

                # Use a clear marker for each turn with role
                formatted_text += MEMORY.TURN_MARKER.format(role=display_role)
                # Wrap the text content with indentation for readability/structure for model
                # Use a safe width, e.g., 80 chars
                wrapped_text = textwrap.fill(text_content.strip(), width=80, initial_indent="", subsequent_indent="  ").strip()
                formatted_text += wrapped_text + "\n\n" # Add extra newline between turns

        return formatted_text.strip() # Remove trailing whitespace from the whole block


    def _save_history(self) -> None:
        """
        Gets the current conversation history from the `self._chat` object,
        formats it into a single string (applying trimming based on max_history_turns
        if needed), encrypts it using FileProtector, and saves it to the configured file path.
        """
        # Only save if FileProtector was successfully initialized and history file path is specified
        if not self._file_protector or not self._history_file_path:
            self._logger.debug("History persistence is disabled, skipping save.")
            return

        # Manually convert Content objects to dicts for processing/trimming
        # get_history gives us the list[dict] format needed
        current_session_history_dicts = self.get_history()

        # Apply trimming *before* formatting and saving
        history_to_save_dicts = current_session_history_dicts
        if self._max_history_turns is not None:
             # A turn is typically a (user_message, model_response) pair = 2 entries in history.
             # We keep the *most recent* turns.
            max_entries_to_keep = max(0, self._max_history_turns * 2) # Max 0 turns means 0 entries
            if len(current_session_history_dicts) > max_entries_to_keep:
                self._logger.debug(f"Trimming history before saving: Keeping last {max_entries_to_keep} entries (max {self._max_history_turns} turns).")
                history_to_save_dicts = current_session_history_dicts[-max_entries_to_keep:]
             # If max_history_turns is > 0 but history has < 2 entries (incomplete first turn),
             # saving it is usually not helpful context for the next session.
             # If max_entries_to_keep is 0, the slice [-0:] correctly returns an empty list.
             # If max_entries_to_keep is > 0 and len is less than max_entries_to_keep (e.g. len 1, max_entries 2),
             # [-2:] returns the whole list, which is fine.
             # The only specific case to handle is if max_history_turns > 0 but len < 2,
             # indicating only the first user message is present without a model response.
             # We generally want to save full turns for context.
            if self._max_history_turns > 0 and 0 < len(current_session_history_dicts) < 2:
                self._logger.debug("Current history has only 1 entry (incomplete first turn), skipping save.")
                history_to_save_dicts = [] # Don't save incomplete first turns if trying to save turns > 0

        # Format the potentially trimmed list of dicts into a single string
        history_text = self._format_history_for_saving(history_to_save_dicts)

        # If the formatted text is empty after trimming (e.g., max_history_turns=0 or history was empty)
        if not history_text.strip():
            self._logger.debug("Formatted history is empty or only whitespace after trimming, ensuring history file is removed.")
             # Ensure file is removed if history becomes empty, to start fresh next time
            if os.path.exists(self._history_file_path):
                try:
                    os.remove(self._history_file_path)
                    self._logger.debug(f"Removed empty history file: {self._history_file_path}")
                except OSError as e:
                    self._logger.error(f"Error removing empty history file {self._history_file_path}: {e}")

        try:
            # Convert the formatted string to bytes using a robust encoding
            history_text_bytes = history_text.encode('utf-8')

            # Encrypt the history bytes using the FileProtector
            encrypted_data = self._file_protector.encrypt(history_text_bytes)

            # Ensure the directory exists before writing the file
            dir_name = os.path.dirname(self._history_file_path)
            if dir_name: # Check if dir_name is not empty (e.g., just a filename)
                 os.makedirs(dir_name, exist_ok=True) # Create directory if it doesn't exist

            # Write the encrypted data to the binary file
            # Use 'x' mode to avoid overwriting if another process might write (less common here)
            # or 'wb' (write binary) to simply overwrite. 'wb' is simpler and safer for typical use.
            with open(self._history_file_path, 'wb') as f:
                f.write(encrypted_data)

            self._logger.info(f"Conversation history saved (encrypted, concatenated) to {self._history_file_path} ({len(history_text_bytes)} bytes raw).")

        except Exception as e:
            self._logger.error(f"Failed to save encrypted history to {self._history_file_path}: {e}", exc_info=True) # Log traceback on save failure


    def _load_history(self) -> Optional[str]:
        """
        Loads conversation history from the encrypted file using FileProtector,
        decrypts it, and returns it as a single concatenated string.
        This loaded string is used only *once* in the initial prompt of a new session.

        Returns:
            The loaded, decrypted history string, or None if loading/decryption failed
            or the file was empty/missing.
        """
        # These conditions are checked in __init__ before calling, but defensive checks are fine.
        if not self._file_protector or not self._history_file_path:
             self._logger.debug("History persistence is disabled, cannot load.")
             return None
        if not os.path.exists(self._history_file_path):
            self._logger.debug(f"History file not found: {self._history_file_path}. No history to load.")
            return None

        try:
            # Read the raw encrypted data from the binary file
            with open(self._history_file_path, 'rb') as f:
                encrypted_data = f.read()

            if not encrypted_data:
                 self._logger.debug(f"History file {self._history_file_path} is empty. No history to load.")
                 # Optionally remove empty file here if desired
                 # try: os.remove(self._history_file_path) except OSError: pass
                 return None

            # Decrypt the data using the FileProtector (returns bytes or None)
            decrypted_data_bytes = self._file_protector.decrypt(encrypted_data)

            if decrypted_data_bytes is None:
                 # Decryption failed (logged inside FileProtector.decrypt)
                 self._logger.warning(f"Decryption failed for history file {self._history_file_path}. Cannot load history.")
                 # Consider adding a note/option to delete corrupted history? (Requires user interaction/config)
                 return None

            # Decode the bytes to a string
            history_text_string = decrypted_data_bytes.decode('utf-8')

            # Basic validation: check if the string is not empty after decoding
            if not history_text_string.strip():
                 self._logger.warning(f"Decrypted data from {self._history_file_path} was empty or contained only whitespace after decoding. Cannot load history.")
                 # Optionally remove empty file here if desired
                 # try: os.remove(self._history_file_path) except OSError: pass
                 return None

            return history_text_string # Return the loaded concatenated string

        except Exception as e:
            # Catch any other unexpected errors during file read or decoding
            self._logger.error(f"An unexpected error occurred during loading or decoding of {self._history_file_path}: {e}", exc_info=True)
            return None


    def clear_history(self) -> None:
        """
        Clears the conversation history in the *current session's* chat object
        and removes the encrypted history file if persistence is enabled and the file exists.
        Also re-sends the initial purpose prompt to re-establish context in the new session.
        """
        self._logger.info("Clearing conversation history...")
        # Clear in-memory history by starting a new chat session
        if self._model:
             self._chat = self._model.start_chat(history=[])
             self._logger.debug("Conversation history cleared in memory.")
             # Clear the loaded history text if it exists (important for the next session)
             self._loaded_history_text = None
        else:
             self._logger.warning("Model not initialized, cannot clear in-memory history.")
             return # Cannot proceed without model

        # Remove the history file if persistence is enabled and file exists
        if self._history_file_path and os.path.exists(self._history_file_path):
            try:
                os.remove(self._history_file_path)
                self._logger.info(f"Encrypted history file removed: {self._history_file_path}")
            except OSError as e:
                self._logger.error(f"Error removing encrypted history file {self._history_file_path}: {e}", exc_info=True)
        elif self._history_file_path:
             self._logger.debug(f"History file {self._history_file_path} not found, nothing to remove.")
        else:
             self._logger.debug("History persistence is disabled, no file to remove.")


        # Re-send initial prompt after clearing history to set context again
        # This message will become the first turn in the newly cleared session's history.
        purpose_text_parts = self._get_initial_purpose_text_parts()
        clear_prompt_parts = purpose_text_parts + [
            "Conversation history cleared. I'm ready for a new start. How can I assist you now?"
        ]

        clear_prompt = " ".join(part.strip() for part in clear_prompt_parts if part).strip()

        if clear_prompt:
                self._logger.debug(f"Resending initial instruction after clear: {clear_prompt[:150]}...")
                # Send this as a user message to the chat history
                try:
                     # send_message will handle the API call and appending to _chat.history
                     self.send_message(clear_prompt)
                     self._logger.debug("Initial instruction sent successfully after history clear.")
                except Exception as e:
                     self._logger.error(f"Failed to send initial instruction after history clear: {e}", exc_info=True)


    def _get_initial_purpose_text_parts(self) -> List[str]:
         """Helper to retrieve initial purpose text parts from constants."""
         purpose_text_parts: List[str] = []
         # Prefer HISTORY_INSTRUCTIONS if available, otherwise fall back to HISTORY
         instructions_constant = getattr(GeminiConstants, 'HISTORY_INSTRUCTIONS', None)
         if instructions_constant is None:
             instructions_constant = getattr(GeminiConstants, 'HISTORY', []) # Fallback to HISTORY

         if isinstance(instructions_constant, list):
              purpose_text_parts = [
                  initial_instruction.format(name=self.name, purpose=self.purpose).strip()
                  for initial_instruction in instructions_constant
                  if isinstance(initial_instruction, str) and initial_instruction.strip()
              ]
         else:
              self._logger.warning("GeminiConstants.HISTORY_INSTRUCTIONS or HISTORY is not a list of strings, cannot load initial prompt parts.")

         return purpose_text_parts


    def get_history(self) -> List[Dict[str, Any]]:
        """
        Returns a copy of the current conversation history from the `self._chat` object
        as a list of dictionaries. This reflects the turns accumulated *in the current session*.
        Content objects are manually converted to a dictionary format.

        Returns:
            A list of dictionaries representing the conversation history turns.
        """
        if self._chat and hasattr(self._chat, 'history') and isinstance(self._chat.history, list):
            history_list = []
            # Iterate through the Content objects in the chat history
            for content in self._chat.history:
                # Ensure content has role and parts attributes, which Content objects should have
                if not hasattr(content, 'role') or not hasattr(content, 'parts'):
                     self._logger.warning(f"Skipping malformed history entry: {content}")
                     continue

                turn_dict = {"role": content.role, "parts": []}
                if content.parts and isinstance(content.parts, list):
                    for part in content.parts:
                        part_dict = {}
                        # Extract text part
                        if hasattr(part, 'text') and isinstance(part.text, str):
                            part_dict['text'] = part.text
                        # Add handling for other part types (like image, etc.) if needed in the future
                        # elif hasattr(part, 'inline_data'): ...

                        if part_dict: # Only append if a valid part was extracted
                            turn_dict["parts"].append(part_dict)

                # Only append turns that have successfully extracted parts and have a valid role
                if turn_dict["parts"] and turn_dict.get('role') in ['user', 'model']: # Only append if role is 'user' or 'model'
                     history_list.append(turn_dict)
                elif turn_dict["parts"]:
                    self._logger.warning(f"Skipping history entry with invalid role '{turn_dict.get('role')}': {turn_dict}")


            return history_list
        elif self._chat:
             self._logger.warning("self._chat exists but its history attribute is missing or not a list.")
             return []
        else:
             self._logger.warning("self._chat is None, cannot retrieve history.")
             return []


    def send_message(self, user_input_text: str) -> str:
         """
         Sends a user message to the Gemini API using the chat session.
         History included in the API call by the genai library is the turns
         accumulated in *this session*'s `self._chat.history`.
         Includes post-processing to remove specific unwanted prefixes from the response.

         Args:
             user_input_text: The user's message string.

         Returns:
             The cleaned model response string.

         Raises:
             ValueError: If user_input_text is empty or only whitespace.
             GeminiBlockedError: If the prompt or response is blocked by safety settings.
             GeminiResponseParsingError: If the API returns an unparseable response.
             GeminiAPIError: For other API-related errors.
         """
         if not user_input_text or not user_input_text.strip():
              self._logger.warning("Attempted to send empty user input.")
              return "" # Or raise ValueError depending on desired behavior

         # No trimming happens before each send_message call on the chat object.
         # The chat object's history grows until explicitly cleared or trimmed on save.

         try:
             # Pass the message to the chat object's send_message method
             # This method manages the history sent to the API under the hood.
             # The number of turns the *API* actually considers might differ based on API limits.
             self._logger.debug(f"Sending message to model ({len(self._chat.history) if self._chat else 0} turns in session history): {user_input_text[:150]}...")

             if not self._chat:
                  raise RuntimeError("Chat object is not initialized.")

             response = self._chat.send_message(
                 user_input_text.strip(),
                 generation_config=self._generation_config,
                 # Add safety_settings if needed here, based on user input or config
                 # safety_settings=[{ "category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}] # Example
             )
             self._logger.debug("Received response object from model.")
             # Log candidate count and prompt feedback status
             self._logger.debug(f"Response has {len(response.candidates) if response.candidates else 0} candidates. Prompt Feedback: {response.prompt_feedback}")


             # --- Response Validation and Extraction ---

             # 1. Check for safety blocks signaled in prompt_feedback
             if response.prompt_feedback and response.prompt_feedback.block_reason:
                  block_reason_name = response.prompt_feedback.block_reason.name
                  safety_details_list = []
                  if response.prompt_feedback.safety_ratings:
                        for rating in response.prompt_feedback.safety_ratings:
                            safety_details_list.append(f"{rating.category.name}: {rating.probability.name}")
                  block_details = f"Prompt blocked by safety settings ({block_reason_name}). Details: {'; '.join(safety_details_list) if safety_details_list else 'No details provided.'}"
                  self._logger.warning(block_details)
                  raise GeminiBlockedError(block_details)

             # 2. Check if candidates exist and have content
             if not response.candidates or not response.candidates[0].content or not response.candidates[0].content.parts:
                  # Even if no content, check candidate finish reason for more info
                  candidate_finish_reasons = [str(c.finish_reason) for c in response.candidates if hasattr(c, 'finish_reason')] if response.candidates else ["N/A"]
                  self._logger.warning(f"API returned a response with no content candidates or parts. Finish reasons: {', '.join(candidate_finish_reasons)}")
                  raise GeminiResponseParsingError(f"API returned response object with no text content. Finish reasons: {', '.join(candidate_finish_reasons)}")

             # 3. Extract text from the first candidate's content
             model_response_parts = []
             for part in response.candidates[0].content.parts:
                  if hasattr(part, 'text') and isinstance(part.text, str):
                       model_response_parts.append(part.text)
                  # Log other part types if encountered unexpectedly
                  elif part:
                       self._logger.debug(f"Ignoring non-text part in response: {type(part)}")


             model_response_text = "".join(model_response_parts).strip()

             if not model_response_text:
                  self._logger.warning("API returned response object, but extracted text was empty after stripping.")
                  # Re-check block reasons defensively, though primary check is above
                  if response.prompt_feedback and response.prompt_feedback.block_reason:
                       block_reason_name = response.prompt_feedback.block_reason.name
                       raise GeminiBlockedError(f"Prompt blocked by safety settings: {block_reason_name}")
                  # If still no block reason, treat as empty response error
                  raise GeminiResponseParsingError("API returned empty text response after extraction.")

             # --- Post-processing: Remove potential model-generated turn prefixes ---
             # This regex is specific to a format the model *might* generate if prompted
             # to mimic the history format used for loading. It is somewhat fragile.
             try:
                 # Construct a regex pattern to match the specific unwanted prefix: --- Name (Turn N) ---
                 # Escape special characters in self.name to ensure correct pattern matching
                 escaped_name = re.escape(self.name)
                 # Pattern: ^ literal ---, optional whitespace (\s*), escaped name, optional whitespace,
                 # literal '(', 'Turn', optional whitespace, one or more digits (\d+), optional whitespace,
                 # literal ')', optional whitespace, literal ---, optional whitespace (\s*)
                 # Make the group around (Turn N) optional just in case the model omits it,
                 # although the desired format includes it. Let's stick to the specific pattern expected.
                 prefix_pattern = re.compile(rf'^---\s*{escaped_name}\s*\(Turn\s*\d+\)\s*---\s*', re.IGNORECASE) # Case-insensitive name match? Depends on desired robustness. Keeping it case-sensitive matches the format exactly.

                 # Attempt to find the prefix at the *start* of the string
                 match = prefix_pattern.match(model_response_text)
                 if match:
                     original_response_length = len(model_response_text)
                     # Slice the string from the end of the matched prefix
                     model_response_text = model_response_text[match.end():].strip()
                     self._logger.debug(f"Removed potential model-generated prefix. Original length: {original_response_length}, New length: {len(model_response_text)}")

             except Exception as e:
                 self._logger.warning(f"Error during response prefix removal regex: {e}", exc_info=True)
                 # Continue with the potentially uncleaned text rather than failing the whole request

             # Return the processed text
             self._logger.debug(f"Final processed response text (after cleaning): {model_response_text[:150]}...")
             return model_response_text

         # --- API Error Handling ---
         # More specific error types first
         except (BadRequest, InvalidArgument) as e: # InvalidArgument is a ClientError subclass
              self._logger.error(f"Google API Client Error (Bad Request/Invalid Argument): {type(e).__name__}: {e}", exc_info=True)
              # Often related to prompt size, content issues, or malformed requests
              error_message = str(e)
              if "safety" in error_message.lower() or "block" in error_message.lower():
                   # Even if not explicitly blocked in prompt_feedback, this error might indicate it
                   raise GeminiBlockedError(f"API error likely related to content/safety or invalid request: {error_message}") from e
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
              # Could implement retry logic here if desired, but re-raising for now.
              raise GeminiAPIError(f"API request failed after retries or exceeded deadline: {str(e)}") from e

         except ClientError as e: # Catch any other ClientError subclasses
              self._logger.error(f"Google API Client Error (General): {type(e).__name__}: {e}", exc_info=True)
              raise GeminiAPIError(f"A general client error occurred during API call: {str(e)}") from e

         except GeminiBlockedError: # Re-raise custom blocked error caught earlier
              raise

         except GeminiResponseParsingError: # Re-raise custom parsing error caught earlier
              raise

         except Exception as e:
             # Catch any other unexpected errors during the API call or response processing
             self._logger.critical(f"An unexpected critical error occurred during send_message: {type(e).__name__}: {e}", exc_info=True)
             raise GeminiAPIError(f"An unexpected internal error occurred during message processing: {e}") from e


    def start(self) -> None:
        """
        Starts the interactive conversation loop.

        Handles sending the initial prompt (including loaded history and purpose)
        to the model at the beginning of the session and then processes
        user input commands and messages, interacting with the Gemini API.
        Saves history on exit.
        """
        try:
            self._logger.info("\n--- Starting Conversation ---")

            # --- Handle initial prompt logic ---
            # This constructs and sends the *very first* message to the model
            # in this new chat session. Its response becomes the first model turn.
            initial_message_to_send: Optional[str] = None

            # Get the core purpose text parts from constants
            purpose_text_parts = self._get_initial_purpose_text_parts()
            purpose_text = "\n".join(purpose_text_parts) # Join with newlines for readability for the model

            # Determine the content of the first message
            if self._loaded_history_text:
                # If history was loaded, combine it with the purpose and send as the first message
                # Format it clearly so the model understands it's past context vs new instructions
                initial_message_to_send = textwrap.dedent(f"""
                {MEMORY.INITIAL_CONTEXT_HEADER}
                The following is a transcript of our previous conversation. Please use it as context for our continued discussion:

                {self._loaded_history_text}

                {MEMORY.INITIAL_INSTRUCTIONS_HEADER}
                Based on our previous conversation (if any) and your purpose as {self.name}, {self.purpose}.
                {purpose_text}

                {MEMORY.INITIAL_START_MARKER}
                Okay, I'm ready to continue the conversation. How can I assist you further?
                """).strip()
                self._loaded_history_text = None # Clear after planning to send - it's now in the first message


            elif purpose_text:
                # If no history loaded, just send the purpose text as the first message
                initial_message_to_send = textwrap.dedent(f"""
                {MEMORY.INITIAL_INSTRUCTIONS_HEADER}
                As {self.name}, your purpose is to {self.purpose}.
                {purpose_text}

                {MEMORY.INITIAL_START_MARKER}
                Okay, I'm ready. How can I assist you?
                """).strip()

            # Send the initial message if planned
            # The response to this message becomes the *first* entry from the model in the session history
            if initial_message_to_send:
                self._logger.debug(f"Sending initial context message ({len(initial_message_to_send)} chars): {initial_message_to_send[:200]}...")
                try:
                    # Use send_message which handles API calls and history updates
                    self.send_message(initial_message_to_send)
                    self._logger.info("Initial context message sent successfully.")
                except Exception as e:
                    # Log and continue, the conversation might still work but lack initial context
                    self._logger.error(f"Error sending initial context message to model: {e}", exc_info=True)
                    self.speech_assistant.synthesize_and_speak("I had trouble setting up the initial conversation context.")

            # --- Main Conversation Loop ---
            while True:
                user_input = input("You: ")
                user_input = user_input.strip() # Strip leading/trailing whitespace

                if not user_input:
                    continue # Ignore empty input

                # Process commands
                if user_input.lower() == COMMANDS.EXIT:
                    break
                if user_input.lower() == COMMANDS.CLEAR_HISTORY:
                    self.clear_history() # clear_history already re-sends initial prompt
                    self._logger.info("History cleared. Starting fresh.")
                    continue

                if user_input.lower() == COMMANDS.SHOW_HISTORY:
                    self._logger.info("--- Current Session History (in-memory) ---")
                    # get_history shows the history of the *current* chat session
                    history = self.get_history()
                    if history:
                        for i, turn in enumerate(history):
                            text_snippet = ""
                            if 'parts' in turn and isinstance(turn['parts'], list):
                                for part in turn['parts']:
                                    if isinstance(part, dict) and 'text' in part and isinstance(part['text'], str):
                                        # Display only a snippet of text part for brevity
                                        text_content = part.get('text', '')
                                        snippet_length = 100
                                        text_snippet += text_content[:snippet_length]
                                        if len(text_content) > snippet_length:
                                             text_snippet += '...'
                                        break # Display only the first text part of the turn for brevity
                            display_role = "You" if turn.get('role') == 'user' else self.name # Use self.name for model turns
                            self._logger.info(f"[Turn {i}] {display_role} ({turn.get('role')}): {text_snippet}")
                    else:
                        self._logger.info("Current session history is empty.")
                    self._logger.info("-------------------------------------------")
                    continue # Continue the loop after showing history


                # Process regular user input by sending it to the model
                try:
                    # send_message handles API communication, response validation,
                    # post-processing, and updates the _chat.history object.
                    response = self.send_message(user_input)

                    if response: # Only speak if response text is not empty
                        print(f"{self.name}: {response}")
                        # Ensure speech_assistant is not None before calling
                        if self.speech_assistant and hasattr(self.speech_assistant, 'synthesize_and_speak'):
                             self.speech_assistant.synthesize_and_speak(response)
                        else:
                             self._logger.warning("speech_assistant is not initialized or missing synthesize_and_speak method.")

                except GeminiBlockedError as e:
                    self._logger.error(f"Response blocked: {e}")
                    print(f"{self.name}: I'm sorry, I cannot respond to that query.")
                    if self.speech_assistant and hasattr(self.speech_assistant, 'synthesize_and_speak'):
                         self.speech_assistant.synthesize_and_speak("I'm sorry, I cannot respond to that query.")

                except GeminiAPIError as e:
                    self._logger.error(f"API error during send_message: {e}")
                    print(f"{self.name}: I encountered an error communicating with the service.")
                    if self.speech_assistant and hasattr(self.speech_assistant, 'synthesize_and_speak'):
                         self.speech_assistant.synthesize_and_speak("I encountered an error communicating with the service.")

                except Exception as e:
                    self._logger.critical(f"An unexpected error occurred during conversation turn: {type(e).__name__}: {e}", exc_info=True)
                    print(f"{self.name}: An unexpected error occurred.")
                    if self.speech_assistant and hasattr(self.speech_assistant, 'synthesize_and_speak'):
                         self.speech_assistant.synthesize_and_speak("An unexpected error occurred.")


        except ValueError as e:
            self._logger.error(f"Client Initialization Error during start: {e}", exc_info=True)
        except ImportError as e:
            self._logger.error(f"Import Error: {e}. Please ensure all dependencies and local modules are correctly installed and structured.", exc_info=True)
        except RuntimeError as e:
             self._logger.error(f"Runtime Error during client initialization or operation: {e}", exc_info=True)
        except Exception as e:
            self._logger.critical(f"An unhandled exception occurred during client execution: {type(e).__name__}: {e}", exc_info=True)


        finally:
             # --- Save history on exit ---
             # This saves the *current session's* history (trimmed according to max_history_turns)
             # as a single concatenated block for next time.
             self._logger.debug("Exiting conversation. Saving history...")
             try:
                 self._save_history()
                 self._logger.info("History save process finished.")
             except Exception as e:
                  # Catch exceptions during save to prevent the finally block from crashing
                  self._logger.error(f"An error occurred during final history save: {e}", exc_info=True)
