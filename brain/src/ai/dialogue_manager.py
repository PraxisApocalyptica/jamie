# This module manages the overall conversation flow, context,
# and decides the robot's spoken responses.

# It interfaces with:
# - NLU Processor: To understand user input (intent, entities).
# - Task Manager: To initiate robotics actions if the user command is a task.
# - Gemini Client: To generate natural language responses for chat or questions.
# - World Model: To get information about the robot's state and environment.
# - Vision Communicator: To send text back to the Vision app for TTS.
# - (Optional) Personality module: To influence response style and proactive behavior.
import time
import threading
import logging

from typing import Dict, Any, Optional
from src.ai.task_manager import TaskManager
# from .nlu_processor import NLUProcessor # Import if not passed in __init__
# from .task_manager import TaskManager # Import if not passed in __init__
# from .gemini_client import GeminiAPIClient # Import if not passed in __init__
# from ..communication.phone_wifi_server import PhoneWifiServer # Import for speaking
# from ..perception.world_model import WorldModel # Import for context

class DialogueManager:
    """Manages conversation flow and robot responses."""

    def __init__(
        self,
        # nlu_processor: NLUProcessor,
        task_manager: TaskManager, # TaskManager or similar
        gemini_client: Any, # GeminiAPIClient or similar
        vision_communicator: Any, # PhoneWifiServer or similar
        world_model: Any, # WorldModel or similar
        config=None
    ):
        # TODO: Initialize Dialogue Manager."
        # self.nlu_processor = nlu_processor # If NLU processing happens here
        self._logger = logging.getLogger(self.__class__.__name__)
        self.task_manager = task_manager
        self.gemini_client = gemini_client
        self.vision_communicator = vision_communicator
        self.world_model = world_model
        self.config = config

        self._conversation_context: Dict[str, Any] = {} # State for conversation history, referred entities, etc.
        self.start_interaction()

    def start_interaction(self):
        # GeminiClient already manages the raw turn history, this is for higher-level context.
        thread = threading.Thread(target=self.gemini_client.start)
        thread.start()
        thread.join()
        self.task_manager.sleep()

    def handle_user_command(
        self,
        intent: str,
        entities: Dict[str, Any],
        command_text: Optional[str] # Original text in case NLU needs context
    ) -> None:
        """
        Handles a user command or query parsed by the NLU.
        Decides whether to initiate a robot task or generate a spoken response.
        """
        self._logger.info(f"Dialogue Manager handling: Intent='{intent}', Entities={entities}")

        # --- Decide Action based on Intent ---
        if self.task_manager.is_robot_busy():
             self._respond_busy(command_text)
             return

        if intent == "PickUp":
            object_name = entities.get("object")
            if object_name:
                # Check if the object exists in the world model and is graspable
                objects_in_world = self.world_model.get_objects_by_class(object_name)
                if objects_in_world:
                    # Pick the best object to pick up (e.g., closest, highest confidence)
                    target_object = objects_in_world # Simple: pick the first one
                    self._respond_thinking(f"Okay, I will try to pick up the {target_object.obj_class}.")
                    # <<<<< INITIATE ROBOT TASK >>>>>
                    self.task_manager.set_goal({"intent": "pick_up", "object_id": target_object.id})
                else:
                    self._respond_error(f"I see objects, but I can't find a {object_name}.")
            else:
                 self._respond_error("I heard 'pick up', but what should I pick up?")

        elif intent == "GoTo":
            location_name = entities.get("location")
            if location_name:
                # Check if location is known (e.g., "kitchen", or refers to an object)
                 # resolved_location = self._resolve_location(location_name) # Needs implementation
                 # if resolved_location:
                 #    self._respond_thinking(f"Okay, I will try to go to the {location_name}.")
                 #    # <<<<< INITIATE ROBOT TASK >>>>>
                 #    # self.task_manager.set_goal({"intent": "go_to", "location": resolved_location})
                 # else:
                 self._respond_error(f"I don't know where {location_name} is.")
            else:
                 self._respond_error("I heard 'go to', but where should I go?")

        elif intent == "Identify":
             # Example: If NLU detected "that", maybe look at the object closest to the center of view
             # identified_object = self._identify_object_in_view() # Needs implementation based on vision data
             # if identified_object:
             #     self._respond_speak(f"That looks like a {identified_object.obj_class}.")
             # else:
             self._respond_speak("I'm not sure what you're referring to.")


        elif intent == "Unknown":
            # Send the original text to the LLM API
            if command_text:
                self._respond_thinking("Thinking...") # Indicate processing
                try:
                    ai_response_text = self.gemini_client.send_message(command_text)
                    if ai_response_text:
                        self._respond_speak(ai_response_text)
                    else:
                        self._respond_error("I don't have a response for that right now.")
                except self.gemini_client.GeminiBlockedError:
                    self._respond_speak("I cannot respond to that query.")
                except self.gemini_client.GeminiAPIError as e:
                    self._logger.error(f"Gemini API Error: {e}")
                    self._respond_error("I had trouble talking to my AI brain.")

            else:
                self._respond_speak("Yes?") # Simple fallback if command_text is unexpectedly empty for chat intent

        # Add more intents: "Stop", "ReportStatus", "FindCharger", "Play"

    # --- Methods to Generate and Send Responses (Speak via Vision app) ---

    def _respond_speak(self, text: str) -> None:
        """Sends text to the Vision app to be spoken via TTS."""
        if self.vision_communicator and self.vision_communicator.is_client_connected():
            # Use a unique utterance ID to potentially track when speaking is done
            utterance_id = f"tts_{int(time.time())}_{hash(text)}" # Simple ID
            message = {"type": "speak", "text": text, "utterance_id": utterance_id}
            try:
                 self.vision_communicator.send_data_to_client(message)
                 self._logger.debug(f"Sent text for TTS to Vision: '{text}'")
            except Exception as e:
                 self._logger.error(f"Error sending speak command to Vision: {e}")
                 # TODO: Handle communication error (e.g., speak error message locally if possible)
        else:
            self._logger.warning(f"Vision app not connected. Cannot speak: '{text}'")
            # TODO: Log or handle cases where Vision is not available for speaking

    def _respond_thinking(self, text: str = "Thinking...") -> None:
         """Sends text to Vision to indicate processing is happening."""
         # This could be a specific type of message that triggers a different UI/audio cue on the phone
         # Or just use _respond_speak
         self._logger.debug(f"Indicating thinking: {text}")
         self._respond_speak(text) # Example: just speak the text

    def _respond_error(self, text: str = "I encountered an error.") -> None:
        """Sends text to Vision to indicate an error."""
        self._logger.error(f"Indicating error: {text}")
        self._respond_speak(text) # Example: just speak the text

    def _respond_busy(self, original_command_text: Optional[str]) -> None:
        """Responds that the robot is currently busy."""
        self._logger.warning("Responding busy.")
        self._respond_speak("I'm busy right now. Please wait until I'm finished.")
        # Optional: Log the command that was ignored because robot was busy

    # --- Optional: Handle feedback from tasks or speaking ---
    def on_speaking_finished(self, utterance_id: str) -> None:
        """Callback when Vision confirms a speaking task is done."""
        # The TaskManager might need this feedback if a plan step involves speaking
        self._logger.debug(f"Dialogue Manager received speech finished confirmation for ID: {utterance_id}")
        # TODO: TaskManager might be waiting for this

    def on_task_status_update(self, task_id: str, status: str, message: Optional[str] = None):
        """Receives status updates from the TaskManager and potentially speaks them."""
        # Example statuses: "navigating", "arrived", "grasping", "grasp_failed", "task_complete"
        self._logger.debug(f"Dialogue Manager received task update: {task_id} - {status} - {message}")
        if status == "navigating":
             # self._respond_speak("Navigating now.") # Maybe too chatty
             pass
        elif status == "arrived":
             # self._respond_speak("I've arrived.")
             pass
        elif status == "grasping":
             # self._respond_speak("Attempting to grasp.")
             pass
        elif status == "grasp_failed":
             self._respond_speak("I wasn't able to pick that up.")
        elif status == "task_complete":
             self._respond_speak("Okay, I'm finished.")
        # Add other status -> spoken response mappings


    # --- Helper methods ---
    # def _resolve_location(self, location_name: str) -> Optional[Dict[str, float]]:
    #     """Resolves a named location (e.g., 'kitchen') to coordinates in the world model."""
    #     # Needs access to known locations in the WorldModel or map data
    #     # Could also resolve object names if the user means "go to the apple"
    #     self._logger.debug(f"TODO: Resolve location name: {location_name}")
    #     return None # Placeholder

    # def _identify_object_in_view(self) -> Optional[ObjectInfo]:
    #     """Identifies the most likely object the robot is looking at based on vision data."""
    #     # Needs access to recent vision detections and the robot's gaze direction (pan/tilt)
    #     self._logger.info("TODO: Identify object in view.")
    #     return None # Placeholder


# --- Example Usage (in main.py, integrated with TaskManager) ---
# # Inside ApocalypticaRobot.__init__
# # self.dialogue_manager = DialogueManager(
# #    task_manager=self.task_manager,
# #    gemini_client=self.gemini_client,
# #    vision_communicator=self.vision_comm,
# #    world_model=self.world_model,
# #    config=self.config['ai']['dialogue']
# # )
# # # TaskManager also needs a way to report status back to the DialogueManager
# # # self.task_manager.set_dialogue_manager(self.dialogue_manager)
# # # In main.py's _handle_vision_data, when a command is received:
# # # self.dialogue_manager.handle_user_command(intent, entities, command_text)
# # # In main.py's _handle_motion_data, when a task feedback is received:
# # # self.dialogue_manager.on_task_status_update(...) # Requires TaskManager to call this
# # # In main.py's _handle_vision_data, when speech_response_done is received:
# # # self.dialogue_manager.on_speaking_finished(utterance_id)
