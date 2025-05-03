import logging
import os
import textwrap
import re
import glob
import numbers

from src.protectors.file_protector import FileProtector # Ensure this path is correct

from typing import List, Dict, Any, Optional, Union

from src.ai.clients.constants import GEMINI as GeminiConstants, MEMORY


class Memory:
    """
    Handles communication with the Google Gemini API using the official client library,
    managing conversation memory as encrypted fragments and the current session's turns.

    Persists memory as multiple encrypted concatenated string fragments using a FileProtector.

    Memory Management Strategy:
    - Memory is stored as individual encrypted files ("fragments") in a directory.
    - On startup, *all* existing fragment files are loaded, decrypted, and stored
      internally as a list of strings (`self._memory_fragments`). This represents the
      agent's long-term, persistent memory from previous interactions.
    - The generativeai `ChatSession` object (`self._chat`) is initialized with an empty history.
    - The *first* message sent to the model includes a concatenated string of *all loaded memory fragments*
      prepended with context headers, followed by the standard initial instructions and a starting prompt.
      This provides historical context (long-term memory) to the model without stuffing it into the `_chat.history` itself
      turn-by-turn.
    - Subsequent messages use the `self._chat` object's `send_message` method, which automatically
      manages the *current session's* turn-by-turn history (short-term memory) for immediate context. The loaded
      memory fragments are *not* included in these subsequent messages.
    - When saving (e.g., on exit), the *current session's turns* (retrieved from `self._chat.history`)
      are formatted into a single concatenated string (trimmed if `max_session_turns_to_save` is set).
      This string is then encrypted and saved as a *new* fragment file in the memory directory,
      incrementing the fragment index. It does *not* modify or overwrite previous fragments.
    - Clearing memory involves deleting *all* fragment files (persistent memory) and resetting
      the `self._chat` object's history (current session turns).
    """

    def __init__(
        self,
        api_key: str,
        max_session_turns_to_save: Optional[Union[int, str]] = None, # Renamed from max_history_turns
        memory_file_prefix: Optional[str] = MEMORY.NAME,
        memory_location: str = MEMORY.LOCATION,
        fragment_extension: str = MEMORY.FRAGMENT_EXTENSION,
        remember_memories: bool = False,
        # Added placeholder for config, model, etc., needed by _get_initial_purpose
        # and _chat instantiation, though not fully shown in the provided snippet.
        # Assuming these are passed or available via constants/attributes.
        # Example:
        # config: Dict[str, Any],
        # model_name: str,
        # max_output_tokens: int,
        # temperature: float,
        # speech_assistant: Any = None, # Assuming this is needed for clear_memory potentially
    ) -> None:
        """
        Initializes the Memory handler, configuring the FileProtector,
        and loading encrypted memory fragments as a list of strings.

        Args:
            api_key: Your Google Gemini API key.
                     WARNING: In this version, used as the encryption password for memory.
                     This is HIGHLY INSECURE and should be replaced with a separate,
                     user-provided password or a more secure key management method
                     in production environments.
            max_session_turns_to_save: Maximum number of conversation turns (user+model pairs)
                                       from the *current session* to include when saving it as a
                                       new memory fragment. If None or "ALL", all turns from the current
                                       session are saved as one fragment. If 0, an empty fragment
                                       is effectively saved (won't create a file if formatted text is empty).
                                       Session turns are trimmed *before* formatting and saving.
                                       Note: This does *not* limit the number of *loaded* memory fragments
                                       on startup, nor does it affect the memory fragments included
                                       in the *first* prompt.
            memory_file_prefix: Optional prefix for memory fragment files (e.g., 'memory_'). If None,
                                memory persistence is disabled.
            memory_location: Directory where the memory fragment files will be stored. Created if it doesn't exist.
            fragment_extension: The file extension for encrypted memory fragments (e.g., '.enc').
            # Placeholder args for other potential dependencies (model, config, etc.)

        Raises:
            ValueError: If essential initialization parameters are invalid.
            ImportError: If required libraries or constants are missing.
            RuntimeError: If FileProtector initialization fails unexpectedly.
        """
        self._logger = logging.getLogger(self.__class__.__name__)

        # --- Input Validation ---
        if not api_key:
            raise ValueError("API key cannot be empty.")
        if memory_file_prefix is not None and not isinstance(memory_file_prefix, str):
            raise ValueError("memory_file_prefix must be a string or None.")
        if not isinstance(memory_location, str) or not memory_location:
            raise ValueError("memory_location must be a non-empty string.")
        if not isinstance(fragment_extension, str) or not fragment_extension:
             raise ValueError("fragment_extension must be a non-empty string.")


        # --- Validate and process max_session_turns_to_save INPUT ---
        # We want self._max_session_turns_to_save to be None or a non-negative integer internally.
        processed_max_turns: Optional[int] = None # This will store the final internal value

        if max_session_turns_to_save is None:
            processed_max_turns = None # None input -> None internal (means save all session turns)
            self._logger.debug("max_session_turns_to_save input is None, will save all current session turns as a fragment.")
        elif isinstance(max_session_turns_to_save, numbers.Integral): # Handles int and other integral types
            if max_session_turns_to_save < 0:
                raise ValueError(f"max_session_turns_to_save integer value must be non-negative, but got {max_session_turns_to_save}.")
            processed_max_turns = int(max_session_turns_to_save) # Ensure it's a standard int
            self._logger.debug(f"max_session_turns_to_save input is valid integer: {processed_max_turns}.")
        elif isinstance(max_session_turns_to_save, str):
            if max_session_turns_to_save.upper() == 'ALL':
                processed_max_turns = None # "ALL" string input -> None internal (means save all session turns)
                self._logger.debug("Mapping max_session_turns_to_save string 'ALL' to internal value None (save all session turns).")
            else:
                # It's a string, but not "ALL". Try converting to int.
                try:
                    int_value = int(max_session_turns_to_save)
                    if int_value < 0:
                        raise ValueError(f"max_session_turns_to_save string value must be a non-negative integer string or 'ALL', but got '{max_session_turns_to_save}'.")
                    processed_max_turns = int_value # Valid number string -> use as int
                    self._logger.debug(f"max_session_turns_to_save input was number string '{max_session_turns_to_save}', successfully converted to integer {processed_max_turns}.")
                except ValueError:
                    # It's a non-numeric string other than "ALL"
                    raise ValueError(f"Invalid string value for max_session_turns_to_save: '{max_session_turns_to_save}'. Must be None, a non-negative integer string, or 'ALL'.") from None
        else:
            # It's some other invalid type (float, list, dict, etc.)
            raise ValueError(f"Invalid type for max_session_turns_to_save: {type(max_session_turns_to_save)}. Must be None, an integer, or the string 'ALL'.")

        # Store the processed value.
        # self._max_session_turns_to_save is now guaranteed to be None or a non-negative integer (int).
        self._max_session_turns_to_save: Optional[int] = processed_max_turns
        self._logger.debug(f"Internal self._max_session_turns_to_save set to: {self._max_session_turns_to_save} (Type: {type(self._max_session_turns_to_save)}).")

        self._api_key: str = api_key

        # Construct full memory directory path and file pattern
        self._memory_dir_path: str = memory_location
        self._memory_file_prefix: Optional[str] = memory_file_prefix
        self._fragment_extension: str = fragment_extension
        self._memory_file_pattern: Optional[str] = None # Pattern for glob
        if self._memory_file_prefix:
             # Example: '/path/to/memory/memory_*.enc'
            self._memory_file_pattern = os.path.join(self._memory_dir_path, f"{self._memory_file_prefix}*{self._fragment_extension}")

        # --- Initialize File Protector ---
        # WARNING: Still using API key as password here. INSECURE.
        self._password: str = api_key # Required for FileProtector
        self._file_protector: Optional[FileProtector] = None

        if self._memory_file_prefix: # Only initialize protector if persistence is enabled
            try:
                # Check if required constants exist for FileProtector
                if not all(hasattr(GeminiConstants, attr) for attr in ['KDF_SALT_SIZE', 'KDF_ITERATIONS', 'ENCRYPTION_ALGORITHM', 'ENCRYPTION_MODE', 'AES_KEY_SIZE', 'IV_NONCE_SIZE']):
                    raise AttributeError("GeminiConstants is missing required cryptographic attributes for FileProtector.")
                self._file_protector = FileProtector(self._password, GeminiConstants)
                self._logger.debug("FileProtector initialized successfully for memory persistence.")
            except (ValueError, AttributeError, ImportError) as e:
                self._logger.error(f"Failed to initialize FileProtector. Memory persistence disabled. Error: {e}", exc_info=True)
                self._file_protector = None
                self._memory_file_prefix = None # Disable persistence if protector fails

        # --- Initialize Chat Session (Placeholder) ---
        # This assumes the model is initialized elsewhere and assigned to self._model
        # And _generation_config is set. This is outside the provided snippet.
        # For clarity, adding placeholder attributes.
        self._model: Any = None # Assume this is set by parent class or init
        self._chat: Any = None # Assume this is set after model is ready
        self._generation_config: Any = None # Assume this is set
        self.config: Any = None
        self.name: Any = None
        self.purpose: Any = None

        self._memory_fragments: List[str] = [] # Stores decrypted fragment texts (long-term memory)
        if remember_memories:
            # --- Load memory fragments on startup ---
            if self._file_protector and self._memory_file_pattern:
                self._memory_fragments = self._load_memory_fragments(self._memory_dir_path, self._memory_file_prefix)
                if self._memory_fragments:
                    total_chars = sum(len(f) for f in self._memory_fragments)
                    self._logger.info(f"Loaded {len(self._memory_fragments)} memory fragments from {self._memory_dir_path} ({total_chars} total chars).")
                else:
                    self._logger.debug(f"No memory fragments found or loaded from {self._memory_dir_path}.")
            else:
                self._logger.debug("Memory persistence is disabled. No fragments loaded.")

        # --- Initialize the chat session *after* memory fragments are loaded ---
        # This ensures a chat object exists even if no model was initialized yet.
        # The actual model chat session needs to be started later, typically in the
        # send_message equivalent method of the main client class, using the
        # loaded fragments in the first prompt.
        # Placeholder: Assuming a method to initialize _chat after model is ready.
        # Example: self._initialize_chat_session() # This would happen outside Memory.__init__


    def _get_initial_purpose(self) -> List[str]:
        """Helper to retrieve initial purpose text parts from constants."""
        purpose_text_parts: List[str] = []
        instructions_constant = getattr(GeminiConstants, 'INSTRUCTIONS', [])

        if isinstance(instructions_constant, list):
            purpose_text_parts = [
                initial_instruction.format(name=self.name, purpose=self.purpose).strip()
                for initial_instruction in instructions_constant
                if isinstance(initial_instruction, str) and initial_instruction.strip()
            ]
        else:
            self._logger.warning("INSTRUCTIONS is not a list of strings, cannot load initial prompt parts.")

        return purpose_text_parts


    def _format_session_turns_as_fragment(self, session_turns_list: List[Dict[str, Any]]) -> str: # Renamed from _format_memory_as_fragment, param name changed
        """
        Formats the current chat session turns (list of dictionaries) into a single string
        suitable for saving as a new memory fragment, using predefined markers.

        Args:
            session_turns_list: A list of history turns from the current session, where each turn
                          is a dictionary with 'role' and 'parts' (list of dictionaries,
                          each with 'text').

        Returns:
            A formatted string representation of the session turns, or an empty string
            if the list is empty or contains no text content.
        """
        formatted_text = ""
        if not session_turns_list: # Use the new parameter name
            return formatted_text

        # Use a marker specific for session turns fragments
        formatted_text += f"{MEMORY.SESSION_FRAGMENT_HEADER}\n\n"

        for turn in session_turns_list: # Use the new parameter name
            # Ensure turn is a dictionary and has 'role' and 'parts'
            if not isinstance(turn, dict) or 'role' not in turn or 'parts' not in turn:
                self._logger.warning(f"Skipping malformed turn in session turns list: {turn}")
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
                        self._logger.warning(f"Skipping malformed part in session turn (Role: {role}): {part}")


            full_text_content = "".join(text_content_parts).strip()

            if full_text_content: # Only add turn if it has text content
                display_role = role.capitalize() if role in ['user', 'model'] else role
                formatted_text += MEMORY.TURN_MARKER.format(role=display_role)
                # Wrap text for readability, removing leading/trailing whitespace from each turn
                wrapped_text = textwrap.fill(full_text_content, width=80, initial_indent="", subsequent_indent="  ")
                formatted_text += wrapped_text.strip() + "\n\n" # Add newline after each turn

        # Remove header if no actual turns were added after formatting
        if formatted_text == f"{MEMORY.SESSION_FRAGMENT_HEADER}\n\n":
             return ""

        return formatted_text.strip() # Final strip removes trailing newlines if any


    def _save_current_memory_as_fragment(self) -> None:
        """
        Gets the current conversation turns from the `self._chat` object,
        formats them into a single string (applying trimming), encrypts it,
        and either appends it to the last fragment (if below size threshold)
        or saves it as a *new* memory fragment file (if above threshold or none exist).
        """
        # Only save if FileProtector was successfully initialized and memory persistence is enabled
        if not self._file_protector or not self._memory_file_prefix or not self._memory_dir_path:
            self._logger.debug(f"[{self.name}] Memory persistence is disabled, skipping save of current session turns.")
            return

        # Get the current session's turns as a list of dicts
        current_session_turns_dicts = self.get_memories()
        self._logger.debug(f"[{self.name}] Retrieved {len(current_session_turns_dicts)} entries from current session turns before processing for saving.")

        # --- Determine Session Turns to Save Based on self._max_session_turns_to_save ---
        # This logic is the same as before to prepare the data for saving/appending
        session_turns_to_save_dicts = []
        if self._max_session_turns_to_save is None:
            session_turns_to_save_dicts = current_session_turns_dicts
        elif isinstance(self._max_session_turns_to_save, numbers.Number) and self._max_session_turns_to_save >= 0:
             if self._max_session_turns_to_save == 0:
                  session_turns_to_save_dicts = []
             else:
                 max_entries_to_keep = int(self._max_session_turns_to_save) * 2
                 if 0 < len(current_session_turns_dicts) < 2 and self._max_session_turns_to_save > 0:
                     session_turns_to_save_dicts = current_session_turns_dicts
                 elif len(current_session_turns_dicts) > max_entries_to_keep:
                     session_turns_to_save_dicts = current_session_turns_dicts[-max_entries_to_keep:]
                 else:
                     session_turns_to_save_dicts = current_session_turns_dicts
        else:
             self._logger.error(f"[{self.name}] Invalid value for self._max_session_turns_to_save: {self._max_session_turns_to_save}. Skipping save.")
             return

        self._logger.debug(f"[{self.name}] Session turns list selected for saving/appending has {len(session_turns_to_save_dicts)} entries.")

        # Format the selected list of dicts into a single string for the fragment
        session_turns_formatted_text = self._format_session_turns_as_fragment(session_turns_to_save_dicts)
        self._logger.debug(f"[{self.name}] Formatted session turns text length before stripping: {len(session_turns_formatted_text)}. First 100 chars: '{session_turns_formatted_text[:100]}'")

        # If the formatted text is empty or only whitespace after formatting, don't save anything
        if not session_turns_formatted_text.strip():
            self._logger.debug(f"[{self.name}] Formatted session turns text is empty or only whitespace, skipping saving as fragment.")
            # Note: If the *last* fragment was below threshold, and this session is empty,
            # we still don't append an empty string. The goal is to save the *current* session history.
            return

        # --- Determine if to append to last fragment or create new ---
        last_fragment_path = None
        max_index = -1
        threshold_bytes = MEMORY.FRAGMENT_THRESHOLD * 1024 * 1024

        try:
            existing_fragments = glob.glob(self._memory_file_pattern) # e.g., './memory_fragments/memory_member_1_frag_*.enc'

            if existing_fragments:
                # Find the fragment with the highest index
                index_pattern = re.compile(rf"{re.escape(self._memory_file_prefix)}_(\d+){re.escape(self._fragment_extension)}$")
                indices_and_paths = []

                for fpath in existing_fragments:
                     fname = os.path.basename(fpath)
                     match = index_pattern.match(fname)
                     if match:
                         try:
                             index = int(match.group(1))
                             indices_and_paths.append((index, fpath))
                         except ValueError:
                             self._logger.warning(f"[{self.name}] Could not parse index from filename: {fname}. Skipping.")

                if indices_and_paths:
                    # Sort by index and get the path of the last one
                    last_fragment_info = max(indices_and_paths, key=lambda item: item[0])
                    max_index = last_fragment_info[0]
                    last_fragment_path = last_fragment_info[1]
                    self._logger.debug(f"[{self.name}] Identified last fragment: {last_fragment_path} with index {max_index}")

                    try:
                        last_fragment_size_bytes = os.path.getsize(last_fragment_path)
                        self._logger.debug(f"[{self.name}] Size of last fragment ({os.path.basename(last_fragment_path)}): {last_fragment_size_bytes} bytes.")

                        # Decide whether to append or create new
                        if last_fragment_size_bytes <= threshold_bytes:
                            # --- Case: Append to Last Fragment ---
                            self._logger.info(f"[{self.name}] Last fragment size ({last_fragment_size_bytes} bytes) is <= threshold ({threshold_bytes} bytes). Attempting to append current session history.")

                            try:
                                # 1. Read existing encrypted data
                                with open(last_fragment_path, 'rb') as f:
                                    existing_encrypted_data = f.read()
                                self._logger.debug(f"[{self.name}] Read {len(existing_encrypted_data)} bytes from {os.path.basename(last_fragment_path)}.")

                                # 2. Decrypt existing data
                                existing_decrypted_bytes = self._file_protector.decrypt(existing_encrypted_data)
                                existing_decrypted_text = existing_decrypted_bytes.decode('utf-8')
                                self._logger.debug(f"[{self.name}] Decrypted existing text length: {len(existing_decrypted_text)}")

                                # 3. Combine existing text with new session text
                                # Add a separator before the new session's formatted text
                                combined_text = existing_decrypted_text + MEMORY.FRAGMENT_SEPARATOR + session_turns_formatted_text
                                self._logger.debug(f"[{self.name}] Combined text length: {len(combined_text)}")

                                # 4. Re-encrypt combined data
                                combined_bytes = combined_text.encode('utf-8')
                                new_encrypted_data = self._file_protector.encrypt(combined_bytes)
                                self._logger.debug(f"[{self.name}] Combined bytes length: {len(combined_bytes)}, New encrypted data length: {len(new_encrypted_data)}")

                                if not new_encrypted_data:
                                     self._logger.warning(f"[{self.name}] Re-encryption resulted in empty data, skipping overwrite.")
                                     return

                                # 5. Overwrite the last fragment file with the new encrypted data
                                with open(last_fragment_path, 'wb') as f: # Use 'wb' mode to overwrite
                                    f.write(new_encrypted_data)

                                self._logger.info(f"[{self.name}] Successfully appended current session turns to fragment: {last_fragment_path}. New encrypted size: {len(new_encrypted_data)} bytes.")

                            except Exception as append_err:
                                self._logger.error(f"[{self.name}] Failed to append to fragment file {last_fragment_path}: {append_err}", exc_info=True)
                                # If append fails, decide if you want to attempt saving as a new file instead,
                                # or just log the error and skip this save cycle. Skipping is safer.
                                self._logger.warning(f"[{self.name}] Skipping save due to error during append process.")


                        else: # last_fragment_size_bytes > threshold_bytes
                            # --- Case: Create New Fragment ---
                            self._logger.info(f"[{self.name}] Last fragment size ({last_fragment_size_bytes} bytes) exceeds threshold ({threshold_bytes} bytes). Attempting to save current session as a new fragment.")
                            next_index = max_index + 1 # Increment index for the new file
                            # Proceed to the 'save new fragment' logic below

                    except OSError as e:
                        self._logger.error(f"[{self.name}] Could not get size of last fragment file {last_fragment_path}: {e}", exc_info=True)
                        # If we can't get the size, we can't apply the threshold logic.
                        # Treat this as a failure to append/save for this cycle.
                        self._logger.warning(f"[{self.name}] Skipping save due to error accessing last fragment file size.")
                        return # Exit the method


            # If last_fragment_path is None (no fragments found) or if the logic above decided to create a new one
            if last_fragment_path is None or (last_fragment_path is not None and os.path.getsize(last_fragment_path) > threshold_bytes):
                # This block handles creating the first fragment (max_index remains -1, next_index=0)
                # and creating subsequent fragments when the last one was too large (next_index = max_index + 1)
                if last_fragment_path is None:
                    self._logger.info(f"[{self.name}] No existing memory fragments found. Saving current session as the first fragment.")
                    next_index = 0
                # else: # max_index was already updated if fragments existed and were > threshold

                try:
                    # Convert the formatted string to bytes using a robust encoding
                    session_turns_bytes = session_turns_formatted_text.encode('utf-8')

                    # Encrypt the turns bytes using the FileProtector
                    encrypted_data = self._file_protector.encrypt(session_turns_bytes)
                    self._logger.debug(f"[{self.name}] Raw turns bytes length: {len(session_turns_bytes)}, Encrypted data length: {len(encrypted_data)}")

                    if not encrypted_data:
                        self._logger.warning(f"[{self.name}] Encryption resulted in empty data, skipping save of new fragment.")
                        return

                    # Ensure the directory exists before writing the file
                    os.makedirs(self._memory_dir_path, exist_ok=True)

                    # Format the filename with zero-padding based on next_index
                    # Assuming 3 digits for padding as per common practice and {index:03d} placeholder
                    next_fragment_filename = f"{self._memory_file_prefix}_{next_index:03d}{self._fragment_extension}"
                    next_fragment_path = os.path.join(self._memory_dir_path, next_fragment_filename)

                    # Write the encrypted data to the binary file
                    with open(next_fragment_path, 'wb') as f: # Use 'wb' mode to overwrite if somehow exists, or create
                        f.write(encrypted_data)

                    self._logger.info(f"[{self.name}] Current session turns saved (encrypted) as a new memory fragment: {next_fragment_path} (Index {next_index}). Raw size: {len(session_turns_bytes)} bytes, Encrypted size: {len(encrypted_data)} bytes.")

                except Exception as new_save_err:
                    self._logger.error(f"[{self.name}] Failed to save current session turns as a new fragment to {self._memory_dir_path}: {new_save_err}", exc_info=True)


        except Exception as e:
             # Catch any errors during the overall process of finding/checking fragments
             self._logger.error(f"[{self.name}] An unexpected error occurred during the save/append process: {e}", exc_info=True)
             self._logger.warning(f"[{self.name}] Skipping save/append due to unexpected error.")


    def _load_memory_fragments(self, memory_location: str, file_prefix: str) -> List[str]:
        """
        Loads conversation memory from all encrypted fragment files in the directory.

        Decrypts each file using FileProtector and returns a list of decrypted strings.
        Skips files that fail to decrypt or are empty.

        Args:
            memory_location: The directory containing the fragment files.
            file_prefix: The expected prefix of the fragment files.

        Returns:
            A list of loaded and decrypted memory fragment strings. Returns an empty list
            if no valid fragments are found or loaded.
        """
        if not self._file_protector or not file_prefix or not memory_location:
            self._logger.debug("Memory persistence is disabled, cannot load fragments.")
            return []

        if not os.path.exists(memory_location):
            self._logger.debug(f"Memory directory not found: {memory_location}. No fragments to load.")
            return []

        loaded_fragments: List[str] = []
        # Glob files matching the pattern, then sort them numerically by index
        fragment_pattern = os.path.join(memory_location, f"{file_prefix}_*{self._fragment_extension}")
        fragment_files = glob.glob(fragment_pattern)

        if not fragment_files:
            self._logger.debug(f"No files matching pattern '{fragment_pattern}' found in '{memory_location}'.")
            return []

        # Sort files based on the numeric index in the filename (e.g., _000, _001, ...)
        def get_index_from_filename(filepath):
            fname = os.path.basename(filepath)
            # Use the same pattern used for saving to extract the index
            index_pattern = re.compile(rf"{re.escape(file_prefix)}_(\d+){re.escape(self._fragment_extension)}$")
            match = index_pattern.match(fname)
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    return -1 # Return -1 for files with non-integer indices
            return -1 # Return -1 for files that don't match the pattern

        fragment_files.sort(key=get_index_from_filename)

        self._logger.debug(f"Found {len(fragment_files)} potential memory fragment files. Attempting to load...")

        for fpath in fragment_files:
            try:
                with open(fpath, 'rb') as f:
                    encrypted_data = f.read()

                if not encrypted_data:
                    self._logger.debug(f"Fragment file {fpath} is empty. Skipping.")
                    continue

                decrypted_data_bytes = self._file_protector.decrypt(encrypted_data)

                if decrypted_data_bytes is None:
                    self._logger.warning(f"Decryption failed for fragment file {fpath}. Skipping.")
                    continue

                fragment_text_string = decrypted_data_bytes.decode('utf-8')

                if not fragment_text_string.strip():
                    self._logger.warning(f"Decrypted data from {fpath} was empty or contained only whitespace after decoding. Skipping.")
                    continue

                loaded_fragments.append(fragment_text_string)
                self._logger.debug(f"Successfully loaded and decrypted fragment: {os.path.basename(fpath)} ({len(fragment_text_string)} chars)")

            except Exception as e:
                self._logger.error(f"An unexpected error occurred during loading or decoding of fragment {fpath}: {e}", exc_info=True)
                # Continue loading other fragments

        self._logger.info(f"Finished loading memory fragments. Loaded {len(loaded_fragments)} valid fragments.")
        return loaded_fragments


    def clear_memory(self) -> None:
        """
        Clears the current session turns in the generativeai chat object and
        removes all encrypted memory fragment files (persistent memory).

        After clearing, it sends a message to the model including the initial
        purpose instructions to reset the context for the *new* empty state.
        """
        self._logger.info("Clearing all memory fragments (persistent) and current session turns (short-term)...")

        # Clear in-memory chat history (current session turns)
        if self._model and self._chat: # Ensure model and chat are initialized
             # Note: 'history' is the name of the parameter/attribute used by the genai library
            self._chat = self._model.start_chat(history=[])
            self._logger.debug("Current session turns cleared in memory (_chat.history reset).")
        else:
            self._logger.warning("Model or chat not initialized, cannot clear in-memory session turns.")
            # Continue attempting to clear files even if model/chat is bad

        # Clear loaded memory fragments list (long-term memory)
        self._memory_fragments = []
        self._logger.debug("Loaded memory fragments list cleared in memory.")


        # Remove memory fragment files (persistent memory)
        if self._file_protector and self._memory_file_pattern:
            fragment_files = glob.glob(self._memory_file_pattern)
            if fragment_files:
                self._logger.info(f"Found {len(fragment_files)} memory fragment files to remove...")
                for fpath in fragment_files:
                    try:
                        os.remove(fpath)
                        self._logger.debug(f"Removed memory fragment file: {fpath}")
                    except OSError as e:
                        self._logger.error(f"Error removing memory fragment file {fpath}: {e}", exc_info=True)
                self._logger.info("Finished removing memory fragment files.")
            else:
                self._logger.debug(f"No memory fragment files matching pattern '{self._memory_file_pattern}' found, nothing to remove.")
        else:
            self._logger.debug("Memory persistence is disabled, no files to remove.")

        # Send initial instructions again after clearing memory
        # This helps the model re-orient itself after a full memory clear.
        purpose_text_parts = self._get_initial_purpose() # Assuming this method exists

        # Reconstruct the initial prompt structure for resending
        clear_prompt_parts_list: List[str] = []
        if purpose_text_parts:
            clear_prompt_parts_list.append(MEMORY.INITIAL_INSTRUCTIONS_HEADER)
            clear_prompt_parts_list.extend(purpose_text_parts)
            # Only add the start marker if there were actual instructions
            clear_prompt_parts_list.append(MEMORY.INITIAL_START_MARKER)
            clear_prompt_parts_list.append("Conversation history cleared. I'm ready for a new start. How can I assist you now?") # Keeping "Conversation history cleared" as it's a common status message
        else:
            # Fallback if no initial instructions are defined
            clear_prompt_parts_list.append("Conversation history cleared. I'm ready for a new start. How can I assist you now?") # Keeping "Conversation history cleared"

        clear_prompt = "\n".join(part for part in clear_prompt_parts_list if part).strip()

        if clear_prompt and self._chat and self._generation_config: # Ensure chat object is ready to send
            self._logger.debug(f"Resending initial instruction after clear: {clear_prompt[:200]}...")
            try:
                # Use the underlying _chat.send_message directly here to avoid adding the
                # large instruction text to the self._chat.history that get_memories sees
                # until the model responds. This keeps the session turns cleaner.
                # Note: The model's response *will* be added by _chat.send_message.
                response = self._chat.send_message(
                    clear_prompt,
                    generation_config=self._generation_config, # Assuming this is set
                )
                self._logger.debug("Initial instruction sent successfully after memory clear.")
                # Process the model's response to this instruction prompt, if any
                # Assuming 'self.name' and 'self.speech_assistant' exist if needed
                # if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                #     model_response_text = "".join([p.text for p in response.candidates[0].content.parts if hasattr(p, 'text')]).strip()
                #     if model_response_text:
                #         # Example: print or speak the model's confirmation
                #         # print(f"{self.name} (Instruction Response): {model_response_text}")
                #         pass # Suppressing default response print/speak for clear instruction
            except Exception as e:
                self._logger.error(f"Failed to send initial instruction after memory clear: {e}", exc_info=True)
        elif not clear_prompt:
             self._logger.debug("Initial instruction prompt is empty, skipping send after clear.")
        else:
             self._logger.warning("Chat object or generation config not ready, cannot send initial instruction after clear.")

    def get_recent_thoughts(self):
        recent_thought_fragments: List[str] = []

        # 1. Add loaded memory fragments to the initial prompt
        if self._memory_fragments:
            recent_thought_fragments.append(MEMORY.INITIAL_CONTEXT_HEADER)
            recent_thought_fragments.append("The following text contains information from previous conversations or stored memories. Please use this as background context:")
            recent_thought_fragments.append("") # Blank line before fragments
            # Concatenate fragments with a clear separator
            concatenated_fragments = f"\n{MEMORY.FRAGMENT_SEPARATOR}\n".join(self._memory_fragments)
            recent_thought_fragments.append(concatenated_fragments)
            recent_thought_fragments.append("") # Blank line after fragments
            self._logger.debug(f"Including {len(self._memory_fragments)} loaded memory fragments in the initial prompt.")
        else:
            # 2. Add initial instructions
            purpose_text_parts = self._get_initial_purpose()
            if purpose_text_parts:
                recent_thought_fragments.append(MEMORY.INITIAL_INSTRUCTIONS_HEADER)
                recent_thought_fragments.extend(purpose_text_parts)
                recent_thought_fragments.append("") # Blank line after instructions
                self._logger.debug("Including initial instructions in the initial prompt.")
            else:
                self._logger.warning("No initial instructions found in constants.")


        # 3. Add start marker and a welcoming phrase
        recent_thought_fragments.append(MEMORY.INITIAL_START_MARKER)
        recent_thought_fragments.append("Okay, I'm ready. How can I assist you today?")
        recent_thought_fragments.append("") # Ensure final newline

        # Combine all fragments into the final thoughts
        return "\n".join(recent_thought_fragments).strip()


    def get_memories(self) -> List[Dict[str, Any]]: # Renamed from get_history
        """
        Returns a copy of the current conversation turns from the generativeai chat object
        as a list of dictionaries, representing the structure suitable for saving or display.
        Filters for 'user' and 'model' roles and includes only text parts from 'parts'.

        Handles the actual iterable type (like RepeatedCompositeFieldContainer) returned by the library for parts.

        Returns:
            A list of session turns, where each turn is a dictionary
            with 'role' and 'parts' (a list of dictionaries, each with a 'text' key).
            Returns an empty list if no valid history is available or processed.
        """
        # Validate that the chat object and its history are in a usable state
        # Note: 'history' is the name of the attribute used by the genai library
        if not self._chat or not hasattr(self._chat, 'history') or not isinstance(self._chat.history, list):
            self._logger.warning("Chat object or its internal history list is not valid. Cannot retrieve session turns.") # Renamed message
            return []

        session_turns_list = [] # Renamed variable
        self._logger.debug(f"Attempting to process raw self._chat.history containing {len(self._chat.history)} items.")

        for i, content in enumerate(self._chat.history): # 'history' is the library's attribute name
            role_str = getattr(content, 'role', 'N/A')
            # Check if parts attribute exists and is not None before trying to iterate
            has_parts_attr = hasattr(content, 'parts') and content.parts is not None
            parts_type_name = type(content.parts).__name__ if has_parts_attr else 'N/A'
            self._logger.debug(f"Processing chat history item {i}: Role='{role_str}', Parts type='{parts_type_name}'") # Clarified message

            # Basic validation: Ensure content has role and parts attributes
            if not hasattr(content, 'role') or not has_parts_attr:
                self._logger.warning(f"Skipping chat history item {i} due to missing 'role' or missing/None 'parts' attribute.") # Clarified message
                continue

            # Role Filtering: Only process turns with standard 'user' or 'model' roles
            if content.role not in ['user', 'model']:
                self._logger.debug(f"Skipping chat history item {i} with non-standard role '{content.role}'.") # Clarified message
                continue

            # Process Parts: Extract only text parts by iterating directly
            processed_parts = []
            try:
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
                self._logger.warning(f"Chat history item {i} (Role: {content.role}) 'parts' attribute (Type: {parts_type_name}) was not iterable. Error: {te}") # Clarified message
                continue # Skip this turn
            except Exception as e:
                # Catch any other unexpected error during iteration
                self._logger.error(f"Unexpected error iterating over parts for chat history item {i} (Role: {content.role}). Error: {e}", exc_info=True) # Clarified message
                continue # Skip this turn on error

            # Append Turn: Add the processed turn dictionary to the session_turns_list
            if processed_parts:
                session_turns_list.append({"role": content.role, "parts": processed_parts}) # Use renamed variable
                self._logger.debug(f"Successfully processed and appended session turn {len(session_turns_list)} (Item {i}, Role: {content.role}) with {len(processed_parts)} text parts.") # Use renamed variable and message
            else:
                # Log turns that were skipped because they had no text parts after processing
                self._logger.debug(f"Skipping chat history item {i} (Role: {content.role}) because it contained no valid text parts after processing.") # Clarified message

        self._logger.debug(f"Finished get_memories processing. Returning list with {len(session_turns_list)} entries.") # Renamed variable and message
        return session_turns_list # Return renamed variable
