import google.generativeai as genai
import logging
import os
import textwrap
import re
from src.protectors.file_protector import FileProtector # Adjust path as needed

from google.api_core.exceptions import (
    ClientError, ServerError, RetryError, DeadlineExceeded,
    ResourceExhausted, InvalidArgument, InternalServerError, BadRequest
)
from typing import List, Dict, Any, Optional, Union

from src.ai.clients.constants import GEMINI as GeminiConstants, MEMORY, COMMANDS
from src.ai.clients.gemini.exceptions import (
    GeminiAPIError, GeminiResponseParsingError, GeminiBlockedError
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
        max_history_turns: Optional[Union[int, str]] = None,
        history_file: Optional[str] = MEMORY.NAME,
        history_dir: str = MEMORY.TYPE,
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
        if history_file is not None and not isinstance(history_file, str):
             raise ValueError("history_file must be a string basename or None.")
        if not isinstance(history_dir, str) or not history_dir:
             raise ValueError("history_dir must be a non-empty string.")


        # --- Validate and process max_history_turns INPUT ---
        # We want self._max_history_turns to be None or a non-negative integer internally.
        processed_max_history_turns: Optional[int] = None # This will store the final internal value

        if max_history_turns is None:
             processed_max_history_turns = None # None input -> None internal (means save all)
             self._logger.debug("max_history_turns input is None, will save all history.")
        elif isinstance(max_history_turns, int):
             if max_history_turns < 0:
                  raise ValueError(f"max_history_turns integer value must be non-negative, but got {max_history_turns}.")
             processed_max_history_turns = max_history_turns # Valid integer input -> use as int
             self._logger.debug(f"max_history_turns input is valid integer: {processed_max_history_turns}.")
        elif isinstance(max_history_turns, str):
             if max_history_turns.upper() == 'ALL':
                  processed_max_history_turns = None # "ALL" string input -> None internal (means save all)
                  self._logger.debug("Mapping max_history_turns string 'ALL' to internal value None (save all).")
             else:
                  # It's a string, but not "ALL". Try converting to int.
                  try:
                       int_value = int(max_history_turns)
                       if int_value < 0:
                            raise ValueError(f"max_history_turns string value must be a non-negative integer string or 'ALL', but got '{max_history_turns}'.")
                       processed_max_history_turns = int_value # Valid number string -> use as int
                       self._logger.debug(f"max_history_turns input was number string '{max_history_turns}', successfully converted to integer {processed_max_history_turns}.")
                  except ValueError:
                       # It's a non-numeric string other than "ALL"
                       raise ValueError(f"Invalid string value for max_history_turns: '{max_history_turns}'. Must be None, a non-negative integer string, or 'ALL'.") from None
        else:
            # It's some other invalid type (float, list, dict, etc.)
            raise ValueError(f"Invalid type for max_history_turns: {type(max_history_turns)}. Must be None, an integer, or the string 'ALL'.")

        # Store the processed value in the instance variable.
        # self._max_history_turns is now guaranteed to be None or a non-negative integer (int).
        self._max_history_turns: Optional[int] = processed_max_history_turns
        self._logger.debug(f"Internal self._max_history_turns set to: {self._max_history_turns} (Type: {type(self._max_history_turns)}).")


        self.config = config if config is not None else {}
        self.name: str = self.config.get('name', 'AI')
        self.purpose: str = self.config.get('purpose', 'engage in conversation')
        self.speech_assistant: Any = speech_assistant

        self._api_key: str = api_key
        self._model_name: str = model_name
        self._generation_config: Dict[str, Any] = {
            "max_output_tokens": max_output_tokens,
            "temperature": temperature,
        }

        # Construct full history file path
        self._history_file_path: Optional[str] = None
        if history_file is not None:
             self._history_file_path = os.path.join(history_dir, history_file)

        # --- Initialize File Protector ---
        # WARNING: Still using API key as password here. INSECURE.
        self._password: str = api_key # Required for FileProtector
        self._file_protector: Optional[FileProtector] = None

        if self._history_file_path:
             try:
                 if not all(hasattr(GeminiConstants, attr) for attr in ['KDF_SALT_SIZE', 'KDF_ITERATIONS', 'ENCRYPTION_ALGORITHM', 'ENCRYPTION_MODE', 'AES_KEY_SIZE', 'IV_NONCE_SIZE']):
                      raise AttributeError("GeminiConstants is missing required cryptographic attributes.")
                 self._file_protector = FileProtector(self._password, GeminiConstants)
                 self._logger.debug("FileProtector initialized successfully.")
             except (ValueError, AttributeError, ImportError) as e:
                 self._logger.error(f"Failed to initialize FileProtector. History persistence disabled. Error: {e}", exc_info=True)
                 self._file_protector = None
                 self._history_file_path = None


        # --- Configure the generativeai library ---
        try:
             genai.configure(api_key=self._api_key)
             self._model = genai.GenerativeModel(self._model_name)
             self._logger.debug(f"GenerativeModel '{self._model_name}' loaded.")
        except Exception as e:
             self._logger.critical(f"Failed to configure genai or load model '{self._model_name}': {e}", exc_info=True)
             raise RuntimeError(f"Could not initialize Gemini model: {e}") from e

        self._chat = self._model.start_chat(history=[])
        self._logger.debug("Chat session started with empty history.")

        # --- Load history on startup ---
        self._loaded_history_text: Optional[str] = None
        if self._file_protector and self._history_file_path and os.path.exists(self._history_file_path):
             self._loaded_history_text = self._load_history()
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
        Formats the chat history (list of dictionaries) into a single string
        suitable for saving, using predefined markers.

        Args:
            history_list: A list of history turns, where each turn is a dictionary
                          with 'role' and 'parts' (list of dictionaries, each with 'text').

        Returns:
            A formatted string representation of the history, or an empty string
            if the history list is empty.
        """
        formatted_text = ""
        if not history_list:
            return formatted_text

        formatted_text += f"{MEMORY.HEADER}\n\n"

        for turn in history_list:
            # Ensure turn is a dictionary and has 'role' and 'parts'
            if not isinstance(turn, dict) or 'role' not in turn or 'parts' not in turn:
                self._logger.warning(f"Skipping malformed turn in history_list: {turn}")
                continue

            role = turn.get('role', 'unknown')
            parts = turn.get('parts', [])

            text_content_parts = []
            if isinstance(parts, list):
                for part in parts:
                    # Ensure part is a dictionary and has a 'text' string key
                    if isinstance(part, dict) and 'text' in part and isinstance(part['text'], str):
                         text_content_parts.append(part['text'])
                    else:
                         self._logger.warning(f"Skipping malformed part in turn (Role: {role}): {part}")


            full_text_content = "".join(text_content_parts).strip()

            if full_text_content: # Only add turn if it has text content
                display_role = role.capitalize() if role in ['user', 'model'] else role
                formatted_text += MEMORY.TURN_MARKER.format(role=display_role)
                # Wrap text for readability, removing leading/trailing whitespace from each turn
                wrapped_text = textwrap.fill(full_text_content, width=80, initial_indent="", subsequent_indent="  ")
                formatted_text += wrapped_text.strip() + "\n\n" # Add newline after each turn

        return formatted_text.strip() # Final strip removes trailing newlines if any


    def _save_history(self) -> None:
        """
        Gets the current conversation history from the `self._chat` object,
        formats it into a single string (applying trimming based on self._max_history_turns
        which is guaranteed to be None or a non-negative integer). Encrypts and saves.

        - If self._max_history_turns is None, saves the full session history.
        - If self._max_history_turns is 0, saves an empty history (effectively clears).
        - If self._max_history_turns > 0, trims to the last N turns before saving.
        """
        # Only save if FileProtector was successfully initialized and history file path is specified
        if not self._file_protector or not self._history_file_path:
            self._logger.debug("History persistence is disabled, skipping save.")
            return

        # Manually convert Content objects to dicts for processing/trimming
        # Calling the potentially fixed get_history
        current_session_history_dicts = self.get_history()
        self._logger.debug(f"Retrieved {len(current_session_history_dicts)} entries from current session history before processing.")

        history_to_save_dicts = [] # Initialize as empty list, will be populated based on rules


        # --- Determine History to Save Based on self._max_history_turns (None or int) ---
        # self._max_history_turns is guaranteed to be None or a non-negative integer by __init__
        # This means the comparisons below are safe and will not cause TypeError.
        if self._max_history_turns is None:
            # Save the entire current session history if trimming is disabled (None means ALL)
            history_to_save_dicts = current_session_history_dicts
            self._logger.debug(f"max_history_turns is None (save all), selecting full current session history ({len(history_to_save_dicts)} entries) for saving.")

        elif self._max_history_turns == 0:
            # If max_history_turns is 0, save an empty history (effectively clearing)
            history_to_save_dicts = [] # This is already []
            self._logger.debug("max_history_turns is 0, selecting empty history for saving.")

        # If we reach here, self._max_history_turns must be an integer > 0
        elif self._max_history_turns > 0:
            # Apply trimming logic
            # Calculate the maximum number of entries to keep (2 entries per turn)
            max_entries_to_keep = self._max_history_turns * 2

            # Handle incomplete first turns when max_history_turns > 0
            # If history has 1 entry (user but no model response yet for the first turn)
            if 0 < len(current_session_history_dicts) < 2 and self._max_history_turns > 0:
                self._logger.debug(f"max_history_turns is {self._max_history_turns} (>0) but history has only {len(current_session_history_dicts)} entry(s) (incomplete first turn), saving this partial turn.")
                # In this edge case, save the single entry if it exists and max_history_turns > 0
                history_to_save_dicts = current_session_history_dicts
            elif len(current_session_history_dicts) > max_entries_to_keep:
                 # History is longer than the max allowed entries, trim it
                 history_to_save_dicts = current_session_history_dicts[-max_entries_to_keep:]
                 self._logger.debug(f"max_history_turns is {self._max_history_turns} (>0). Trimmed history from {len(current_session_history_dicts)} to {len(history_to_save_dicts)} entries (kept last {max_entries_to_keep}).")
            else:
                 # History is shorter than or equal to the max allowed entries (and >= 2 if applicable), save it all
                 history_to_save_dicts = current_session_history_dicts
                 self._logger.debug(f"max_history_turns is {self._max_history_turns} (>0). History length ({len(current_session_history_dicts)}) is less than or equal to max entries to keep ({max_entries_to_keep}). Selecting full current history (no trim needed beyond incomplete turn check logic above).")


        self._logger.debug(f"History list selected for saving has {len(history_to_save_dicts)} entries.")

        # Format the selected list of dicts into a single string
        history_text = self._format_history_for_saving(history_to_save_dicts)
        self._logger.debug(f"Formatted history text length before stripping: {len(history_text)}. First 100 chars: '{history_text[:100]}'")


        # If the formatted text is empty or only whitespace after formatting
        if not history_text.strip():
            self._logger.debug("Formatted history is empty or only whitespace, ensuring history file is removed.")
             # Ensure file is removed if history becomes empty, to start fresh next time
            if self._history_file_path and os.path.exists(self._history_file_path):
                try:
                    os.remove(self._history_file_path)
                    self._logger.debug(f"Removed empty history file: {self._history_file_path}")
                except OSError as e:
                    self._logger.error(f"Error removing empty history file {self._history_file_path}: {e}")
            # IMPORTANT: Add return here to stop the save process for empty history
            return


        # --- Encryption and Saving ---
        try:
            # Convert the formatted string to bytes using a robust encoding
            history_text_bytes = history_text.encode('utf-8')

            # Encrypt the history bytes using the FileProtector
            encrypted_data = self._file_protector.encrypt(history_text_bytes)
            self._logger.debug(f"Raw history bytes length: {len(history_text_bytes)}, Encrypted data length: {len(encrypted_data)}")

            if not encrypted_data:
                self._logger.warning("Encryption resulted in empty data, skipping save.")
                # Optionally remove file here too if it exists from a previous attempt
                if self._history_file_path and os.path.exists(self._history_file_path):
                    try:
                        os.remove(self._history_file_path)
                    except OSError:
                        pass # Ignore error if file removal fails here
                return


            # Ensure the directory exists before writing the file
            dir_name = os.path.dirname(self._history_file_path)
            if dir_name: # Check if dir_name is not empty (e.g., just a filename)
                os.makedirs(dir_name, exist_ok=True) # Create directory if it doesn't exist

            # Write the encrypted data to the binary file
            with open(self._history_file_path, 'wb') as f:
                f.write(encrypted_data)

            self._logger.info(f"Conversation history saved (encrypted, concatenated) to {self._history_file_path}. Raw size: {len(history_text_bytes)} bytes, Encrypted size: {len(encrypted_data)} bytes.")

        except Exception as e:
            self._logger.error(f"Failed to complete the save process for encrypted history to {self._history_file_path}: {e}", exc_info=True)

    def _load_history(self) -> Optional[str]:
        """
        Loads conversation history... (docstring remains the same)
        """
        if not self._file_protector or not self._history_file_path:
             self._logger.debug("History persistence is disabled, cannot load.")
             return None
        if not os.path.exists(self._history_file_path):
            self._logger.debug(f"History file not found: {self._history_file_path}. No history to load.")
            return None

        try:
            with open(self._history_file_path, 'rb') as f:
                encrypted_data = f.read()

            if not encrypted_data:
                 self._logger.debug(f"History file {self._history_file_path} is empty. No history to load.")
                 return None

            decrypted_data_bytes = self._file_protector.decrypt(encrypted_data)

            if decrypted_data_bytes is None:
                 self._logger.warning(f"Decryption failed for history file {self._history_file_path}. Cannot load history.")
                 return None

            history_text_string = decrypted_data_bytes.decode('utf-8')

            if not history_text_string.strip():
                 self._logger.warning(f"Decrypted data from {self._history_file_path} was empty or contained only whitespace after decoding. Cannot load history.")
                 return None

            return history_text_string

        except Exception as e:
            self._logger.error(f"An unexpected error occurred during loading or decoding of {self._history_file_path}: {e}", exc_info=True)
            return None

    def clear_history(self) -> None:
        """
        Clears the conversation history... (docstring remains the same)
        """
        self._logger.info("Clearing conversation history...")
        if self._model:
             self._chat = self._model.start_chat(history=[])
             self._logger.debug("Conversation history cleared in memory.")
             self._loaded_history_text = None
        else:
             self._logger.warning("Model not initialized, cannot clear in-memory history.")
             return

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

        purpose_text_parts = self._get_initial_purpose_text_parts()
        # Reconstruct the initial prompt structure for resending
        clear_prompt_parts_list: List[str] = []
        if purpose_text_parts:
             clear_prompt_parts_list.append(MEMORY.INITIAL_INSTRUCTIONS_HEADER)
             clear_prompt_parts_list.extend(purpose_text_parts)
             clear_prompt_parts_list.append(MEMORY.INITIAL_START_MARKER)
             clear_prompt_parts_list.append("Conversation history cleared. I'm ready for a new start. How can I assist you now?")
        else:
             # Fallback if no initial instructions are defined
             clear_prompt_parts_list.append("Conversation history cleared. I'm ready for a new start. How can I assist you now?")


        clear_prompt = "\n".join(part for part in clear_prompt_parts_list if part).strip()

        if clear_prompt:
            self._logger.debug(f"Resending initial instruction after clear: {clear_prompt[:200]}...")
            try:
                 # Use the underlying _chat.send_message directly here to avoid adding the
                 # large instruction text to the self._chat.history that get_history sees
                 # until the model responds. This keeps the history cleaner.
                 # Note: The model's response *will* be added by _chat.send_message.
                 response = self._chat.send_message(
                     clear_prompt,
                     generation_config=self._generation_config,
                 )
                 self._logger.debug("Initial instruction sent successfully after history clear.")
                 # Process the model's response to this instruction prompt, if any
                 if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                      model_response_text = "".join([p.text for p in response.candidates[0].content.parts if hasattr(p, 'text')]).strip()
                      if model_response_text:
                           print(f"{self.name} (Instruction Response): {model_response_text}")
                           if self.speech_assistant and hasattr(self.speech_assistant, 'synthesize_and_speak'):
                                self.speech_assistant.synthesize_and_speak(model_response_text)

            except Exception as e:
                 self._logger.error(f"Failed to send initial instruction after history clear: {e}", exc_info=True)


    def _get_initial_purpose_text_parts(self) -> List[str]:
        """Helper to retrieve initial purpose text parts from constants."""
        purpose_text_parts: List[str] = []
        instructions_constant = getattr(GeminiConstants, 'HISTORY_INSTRUCTIONS', None)
        if instructions_constant is None:
            instructions_constant = getattr(GeminiConstants, 'HISTORY', [])

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
        Returns a copy of the current conversation history from the generativeai chat object
        as a list of dictionaries, representing the structure suitable for saving or display.
        Filters for 'user' and 'model' roles and includes only text parts from 'parts'.

        Handles the actual iterable type (like RepeatedCompositeFieldContainer) returned by the library for parts.

        Returns:
            A list of history turns, where each turn is a dictionary
            with 'role' and 'parts' (a list of dictionaries, each with a 'text' key).
            Returns an empty list if no valid history is available or processed.
        """
        # Validate that the chat object and its history are in a usable state
        if not self._chat or not hasattr(self._chat, 'history') or not isinstance(self._chat.history, list):
             self._logger.warning("Chat object or its history is not valid or not a list. Cannot retrieve history.")
             return []

        history_list = []
        self._logger.debug(f"Attempting to process raw self._chat.history containing {len(self._chat.history)} items.")

        for i, content in enumerate(self._chat.history):
            role_str = getattr(content, 'role', 'N/A')
            # Check if parts attribute exists and is not None before trying to iterate
            has_parts_attr = hasattr(content, 'parts') and content.parts is not None
            parts_type_name = type(content.parts).__name__ if has_parts_attr else 'N/A'
            self._logger.debug(f"Processing history item {i}: Role='{role_str}', Parts type='{parts_type_name}'")

            # Basic validation: Ensure content has role and parts attributes
            if not hasattr(content, 'role') or not has_parts_attr:
                 self._logger.warning(f"Skipping history item {i} due to missing 'role' or missing/None 'parts' attribute.")
                 continue

            # Role Filtering: Only process turns with standard 'user' or 'model' roles
            if content.role not in ['user', 'model']:
                 self._logger.debug(f"Skipping history item {i} with non-standard role '{content.role}'.")
                 continue

            # Process Parts: Extract only text parts by iterating directly
            processed_parts = []
            try:
                 # === FIX: Removed isinstance(content.parts, list) check ===
                 # Directly iterate over content.parts, assuming it's iterable.
                 # This works for lists and RepeatedCompositeFieldContainer etc.
                 for j, part in enumerate(content.parts):
                      # Check if the part object has a 'text' attribute and it's a string
                      if hasattr(part, 'text') and isinstance(part.text, str):
                           # Append the text part as a dictionary in the desired format
                           processed_parts.append({'text': part.text})
                           self._logger.debug(f"  Item {i}, Part {j}: Successfully added text part.")
                      elif part is not None:
                           # Log if a part is skipped
                           self._logger.debug(f"  Item {i}, Part {j}: Skipping non-text or malformed part (Type: {type(part).__name__}).")
                      else:
                           self._logger.debug(f"  Item {i}, Part {j}: Encountered None part, skipping.")

            except TypeError as te:
                 # Catch if content.parts is somehow not iterable (shouldn't happen if has_parts_attr is true)
                 self._logger.warning(f"History item {i} (Role: {content.role}) 'parts' attribute (Type: {parts_type_name}) was not iterable. Error: {te}")
                 continue # Skip this turn
            except Exception as e:
                 # Catch any other unexpected error during iteration
                 self._logger.error(f"Unexpected error iterating over parts for history item {i} (Role: {content.role}). Error: {e}", exc_info=True)
                 continue # Skip this turn on error

            # Append Turn: Add the processed turn dictionary to the history_list
            if processed_parts:
                history_list.append({"role": content.role, "parts": processed_parts})
                self._logger.debug(f"Successfully processed and appended turn {len(history_list)} (Item {i}, Role: {content.role}) with {len(processed_parts)} text parts.")
            else:
                 # Log turns that were skipped because they had no text parts after processing
                 self._logger.debug(f"Skipping history item {i} (Role: {content.role}) because it contained no valid text parts after processing.")

        self._logger.debug(f"Finished get_history processing. Returning list with {len(history_list)} entries.")
        return history_list

    def send_message(self, user_input_text: str) -> str:
        """
        Sends a user message to the Gemini API via the chat object, processes the response,
        handles errors, and returns the model's text response.
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

            # Send the message to the Gemini model
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
            try:
                # Be careful with regex patterns, especially with dynamic names
                # This pattern assumes the format is strictly "--- Name (Turn N) ---" at the start
                escaped_name = re.escape(self.name)
                prefix_pattern = re.compile(rf'^---\s*{escaped_name}\s*\(Turn\s*\d+\)\s*---\s*', re.IGNORECASE)
                match = prefix_pattern.match(model_response_text)
                if match:
                    original_response_length = len(model_response_text)
                    model_response_text = model_response_text[match.end():].strip()
                    self._logger.debug(f"Removed potential model-generated prefix. Original length: {original_response_length}, New length: {len(model_response_text)}")
            except Exception as e:
                self._logger.warning(f"Error during response prefix removal regex: {e}", exc_info=True) # Log regex errors but don't fail

            self._logger.debug(f"Final processed response text (after cleaning): {model_response_text[:150]}...")
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
            self._logger.critical(f"An unexpected critical error occurred during send_message: {type(e).__name__}: {e}", exc_info=True)
            # Wrap any other unexpected errors in a general API error
            raise GeminiAPIError(f"An unexpected internal error occurred during message processing: {e}") from e


    def start(self) -> None:
        """
        Starts the interactive conversation loop in the console.
        Loads previous history (if any), sends initial context/instructions,
        and processes user input until the exit command. Saves history on exit.
        """
        try:
            self._logger.info("\n--- Starting Conversation ---")
            initial_message_to_send: Optional[str] = None
            purpose_text_parts = self._get_initial_purpose_text_parts()
            # Combine initial purpose instructions
            purpose_text = "\n".join(purpose_text_parts) if purpose_text_parts else ""

            # Construct the initial message to send based on loaded history and purpose
            if self._loaded_history_text:
                # Include loaded history and current instructions for context
                initial_message_to_send = textwrap.dedent(f"""
                {MEMORY.INITIAL_CONTEXT_HEADER}
                The following is a transcript of our previous conversation. Please use it as context for our continued discussion:

                {self._loaded_history_text}

                {MEMORY.INITIAL_INSTRUCTIONS_HEADER}
                Based on our previous conversation (if any) and your purpose as {self.name}, {self.purpose}:
                {purpose_text if purpose_text else "Engage in conversation naturally."}

                {MEMORY.INITIAL_START_MARKER}
                Okay, I'm ready to continue the conversation. How can I assist you further?
                """).strip()
                self._loaded_history_text = None # Clear loaded history after using it once

            elif purpose_text:
                # Only send instructions if no history was loaded
                initial_message_to_send = textwrap.dedent(f"""
                {MEMORY.INITIAL_INSTRUCTIONS_HEADER}
                As {self.name}, your purpose is to {self.purpose}.
                {purpose_text}

                {MEMORY.INITIAL_START_MARKER}
                Okay, I'm ready. How can I assist you?
                """).strip()
            # If neither history nor purpose text exists, no initial message is strictly needed

            if initial_message_to_send:
                self._logger.debug(f"Sending initial context/instruction message ({len(initial_message_to_send)} chars): {initial_message_to_send[:200]}...")
                try:
                    # Send the initial message. The model's response will be added to history.
                    # No need to capture/print response here usually, as it's often just acknowledgement.
                    self.send_message(initial_message_to_send)
                    self._logger.info("Initial context message sent successfully.")
                except Exception as e:
                    self._logger.error(f"Error sending initial context message to model: {e}", exc_info=True)
                    # Inform the user if the initial setup message failed
                    if self.speech_assistant and hasattr(self.speech_assistant, 'synthesize_and_speak'):
                         self.speech_assistant.synthesize_and_speak("I had trouble setting up the initial conversation context.")

            # Start the main conversation loop
            while True:
                user_input = input("You: ")
                user_input = user_input.strip()

                if not user_input:
                    continue # Skip empty input

                # --- Command Handling ---
                if user_input.lower() == COMMANDS.EXIT:
                    break # Exit the loop
                if user_input.lower() == COMMANDS.CLEAR_HISTORY:
                    self.clear_history() # Clear history and reset chat state
                    self._logger.info("History cleared. Starting fresh.")
                    continue # Continue to the next input loop iteration
                if user_input.lower() == COMMANDS.SHOW_HISTORY:
                    # Display current in-memory session history
                    self._logger.info("--- Current Session History (in-memory) ---")
                    history = self.get_history() # Get history using the method
                    if history:
                        for i, turn in enumerate(history):
                            text_snippet = ""
                            # Concatenate text parts for display snippet
                            if 'parts' in turn and isinstance(turn['parts'], list):
                                for part in turn['parts']:
                                    if isinstance(part, dict) and 'text' in part and isinstance(part['text'], str):
                                        text_content = part.get('text', '')
                                        text_snippet += text_content # Append all text parts for the snippet
                                        # Break after the first text part or concatenate a few for a longer snippet?
                                        # Let's just show the start of the concatenated text for the turn
                                        break # Show only the first text part's beginning
                            display_role = "You" if turn.get('role') == 'user' else self.name
                            # Limit snippet length for display
                            snippet_display_length = 100
                            display_snippet = text_snippet[:snippet_display_length]
                            if len(text_snippet) > snippet_display_length:
                                 display_snippet += '...'
                            self._logger.info(f"[Turn {i}] {display_role} ({turn.get('role')}): {display_snippet}")
                    else:
                        self._logger.info("Current session history is empty.")
                    self._logger.info("-------------------------------------------")
                    continue

                # --- Send User Message to Model ---
                try:
                    response = self.send_message(user_input) # Send the user's message
                    if response:
                        print(f"{self.name}: {response}") # Print the model's response
                        # Speak the response if speech assistant is available
                        if self.speech_assistant and hasattr(self.speech_assistant, 'synthesize_and_speak'):
                             self.speech_assistant.synthesize_and_speak(response)
                        else:
                             self._logger.debug("speech_assistant is not initialized or missing synthesize_and_speak method.")
                # --- Exception Handling for send_message ---
                except GeminiBlockedError as e:
                    self._logger.error(f"Response blocked by safety: {e}")
                    print(f"{self.name}: I'm sorry, I cannot respond to that query due to safety policies.")
                    if self.speech_assistant and hasattr(self.speech_assistant, 'synthesize_and_speak'):
                         self.speech_assistant.synthesize_and_speak("I'm sorry, I cannot respond to that query due to safety policies.")
                except GeminiAPIError as e:
                    self._logger.error(f"API error during send_message: {e}")
                    print(f"{self.name}: I encountered an error communicating with the service.")
                    if self.speech_assistant and hasattr(self.speech_assistant, 'synthesize_and_speak'):
                         self.speech_assistant.synthesize_and_speak("I encountered an error communicating with the service.")
                except GeminiResponseParsingError as e:
                    self._logger.error(f"Error parsing model response: {e}")
                    print(f"{self.name}: I received an unexpected response format from the service.")
                    if self.speech_assistant and hasattr(self.speech_assistant, 'synthesize_and_speak'):
                         self.speech_assistant.synthesize_and_speak("I received an unexpected response format from the service.")
                except Exception as e:
                    # Catch any other unexpected errors during a conversation turn
                    self._logger.critical(f"An unexpected error occurred during conversation turn: {type(e).__name__}: {e}", exc_info=True)
                    print(f"{self.name}: An unexpected error occurred.")
                    if self.speech_assistant and hasattr(self.speech_assistant, 'synthesize_and_speak'):
                         self.speech_assistant.synthesize_and_speak("An unexpected error occurred.")

        except (ValueError, ImportError, RuntimeError) as e:
             # Catch potential errors during client initialization or setup that might occur before the loop
             self._logger.critical(f"Critical Initialization/Runtime Error before conversation loop started or during execution: {e}", exc_info=True)
        except Exception as e:
            # Catch any unhandled exception that might escape the loop or setup
            self._logger.critical(f"An unhandled exception occurred during client execution: {type(e).__name__}: {e}", exc_info=True)

        finally:
             # Ensure history is saved when the program exits the try/except block
             self._logger.debug("Exiting conversation. Attempting to save history...")
             try:
                 self._save_history() # Call the save method
                 self._logger.debug("History save process finished.")
             except Exception as e:
                  # Catch any exceptions specifically during the save process
                  self._logger.error(f"An error occurred during final history save: {e}", exc_info=True)
