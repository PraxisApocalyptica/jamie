# This module manages the overall conversation flow, context,
# and decides the robot's spoken responses.

# It interfaces with:
# - NLU Processor: To understand user input (intent, entities).
# - Task Manager: To initiate robotics actions if the user command is a task.
# - Gemini Client: To generate natural language responses for chat or questions.
# - World Model: To get information about the robot's state and environment.
# - Vision Communicator: To send text back to the Vision app for TTS.
# - (Optional) Personality module: To influence response style and proactive behavior.
import asyncio
import logging
import os
import random
import threading

from typing import Dict, Any, Set
from src.ai.clients.gemini.client import GeminiClient
from src.ai.mind.hive_mind import HiveMind
from src.ai.clients.speech.google_tts import GttsTTSClient
from src.ai.task_manager import TaskManager
from src.ai.processor.cognition_processor import CognitionProcessor
from src.ai.capabilities import Cognition
from src.ai.cognitions import Cognitions

from src.ai.clients.constants import COMMANDS, AI_RESPONSES
from src.ai.clients.gemini.exceptions import (
    GeminiAPIError, GeminiResponseParsingError, GeminiBlockedError
)
# from .nlu_processor import NLUProcessor # Import if not passed in __init__
# from ..communication.phone_wifi_server import PhoneWifiServer # Import for speaking
# from ..perception.world_model import WorldModel # Import for context

class Interactions:
    """Manages conversation flow and robot responses."""

    def __init__(
        self,
        # nlu_processor: NLUProcessor,
        task_manager: TaskManager, # TaskManager or similar
        vision_communicator: Any, # PhoneWifiServer or similar
        world_model: Any, # WorldModel or similar
        config=None
    ):
        # self.nlu_processor = nlu_processor # If NLU processing happens here
        self._logger = logging.getLogger(self.__class__.__name__)
        self.task_manager = task_manager
        self.vision_communicator = vision_communicator
        self.world_model = world_model
        self.config = config

        self._conversation_context: Dict[str, Any] = {}
        self.speech_assistant = GttsTTSClient(lang="en", default_playback_speed=1.15)
        self.cognition_processor: CognitionProcessor = CognitionProcessor()
        self.cognitions: Cognition = Cognitions()
        self._background_tasks: Set[asyncio.Task] = set()
        self.start()

    def start(self):

        collective_config = {
            "collective_name": "The Synthesis Council",
            "collective_purpose": "brainstorm solutions and make recommendations",
            "name": "AI Member",
            "purpose": "contribute to collective decisions",
        }
        api_key = os.getenv("GEMINI_SECRET_KEY") or self.config['api_keys']['gemini']
        self.hive_mind = HiveMind(
            api_key=api_key,
            config=collective_config,
        )
        # --- AI and Task Management ---
        self.ai_client = GeminiClient(
           api_key= api_key,
           max_output_tokens=self.config['ai']['gemini'].get('max_tokens', 150),
           temperature=self.config['ai']['gemini'].get('temperature', 0.7),
           max_history_turns=self.config['ai']['gemini'].get('max_history_turns', 'ALL'),
           config=self.config.get('robot', {}),
           speech_assistant=self.speech_assistant,
           remember_memories=True,
        )
        self.name = self.ai_client.get_name()
        self.task_manager.assign_task(self.start_interaction)
        self.task_manager.sleep()

    def start_interaction(self):
        """The actual interaction loop run within its own thread."""
        # --- Event Loop Setup for this Thread ---
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop) # <--- Set the loop for this thread
        self._logger.info(f"Event loop created and set for thread {threading.current_thread().name}")

        try:
            # Run the main ASYNC interaction logic using this thread's event loop
            self._loop.run_until_complete(self._start_interaction()) # <--- Run the async part
        except Exception as e:
            self._logger.critical(f"Critical error in interaction loop: {e}", exc_info=True)
        finally:
            # --- Cleanup ---
            self._logger.info("Cleaning up interaction loop...")
            self._loop = None

    async def _start_interaction(self):
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
                # Note: Renamed to clear_memory, keeping old command name for backward compatibility
                self.ai_client.clear_memory() # Clear memory files and reset chat state
                self._logger.info("Memory cleared. Starting fresh session.")
                if self.speech_assistant and hasattr(self.speech_assistant, 'synthesize_and_speak'):
                    self.speech_assistant.synthesize_and_speak("My memory has been cleared. How can I assist you now?")
                continue # Continue to the next input loop iteration
            if user_input.lower() == COMMANDS.SHOW_HISTORY:
                # Display current in-memory session history
                self._logger.info("--- Current Session History (in-memory) ---")
                history = self.ai_client.get_memories()
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
                        self._logger.debug(f"[Turn {i+1}] {display_role} ({turn.get('role')}): {display_snippet}")
                else:
                    self._logger.info("Current session history is empty.")
                self._logger.info("-------------------------------------------")
                continue

            
            bg_task = asyncio.create_task(
                self.ai_client.communicate(user_input),
                name=f"{self.name}-{user_input[:10]}" # Optional name for debugging
            )
            self._background_tasks.add(bg_task)
            # Remove task from set when done to prevent memory leak
            bg_task.add_done_callback(self._background_tasks.discard)
            # --- Send User Message to Model ---
            try:
                collective_response = await self.hive_mind.deliberate(user_input)
                try:
                    execution_plan = self.cognition_processor.parse_function(collective_response)
                    capabilities = self.cognition_processor.create_function_callables(execution_plan, self.cognitions)

                    # Execute the functions sequentially
                    self._logger.debug("\nExecuting plan steps:")
                    for i, capability in enumerate(capabilities):
                        capability()

                except (ValueError, AttributeError) as e:
                    self._logger.error(f"Error processing capabilities: {e}")

            # --- Exception Handling for communicate ---
            except GeminiBlockedError as e:
                self._logger.error(f"Response blocked by safety: {e}")
                if self.speech_assistant and hasattr(self.speech_assistant, 'synthesize_and_speak'):
                    self.speech_assistant.synthesize_and_speak(random.choice(AI_RESPONSES.SECURITY))
            except GeminiAPIError as e:
                self._logger.error(f"API error during communication: {e}")
                if self.speech_assistant and hasattr(self.speech_assistant, 'synthesize_and_speak'):
                    self.speech_assistant.synthesize_and_speak(random.choice(AI_RESPONSES.UNAVAILABLE))
            except GeminiResponseParsingError as e:
                self._logger.error(f"Error parsing model response: {e}")
                if self.speech_assistant and hasattr(self.speech_assistant, 'synthesize_and_speak'):
                    self.speech_assistant.synthesize_and_speak(random.choice(AI_RESPONSES.CONFUSED))
            except Exception as e:
                # Catch any other unexpected errors during a conversation turn
                self._logger.critical(f"An unexpected error occurred during conversation turn: {type(e).__name__}: {e}", exc_info=True)
                if self.speech_assistant and hasattr(self.speech_assistant, 'synthesize_and_speak'):
                    self.speech_assistant.synthesize_and_speak(random.choice(AI_RESPONSES.UNEXPECTED))

        self.shutdown()

    def shutdown(self):
        self.hive_mind.shutdown()
        self.ai_client.shutdown()
