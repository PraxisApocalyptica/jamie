# This module processes raw text input from the user (via Vision app)
# to understand the user's intent and extract relevant information (entities).

# Examples:
# "Pick up the red ball" -> Intent: PickUp, Entities: {object: "ball", color: "red"}
# "Go to the kitchen" -> Intent: GoTo, Entities: {location: "kitchen"}
# "What is that?" -> Intent: Identify, Entities: {target: "that"} # "that" might refer to a visually perceived object
# "How are you?" -> Intent: Chat, Entities: {}

from typing import Tuple, Dict, Any

class NLUProcessor:
    """Processes raw text to extract intent and entities."""

    def __init__(self, config=None):
        # Initialize NLU model or rules here
        # This could use a library like spaCy, NLTK, or a custom model.
        print("TODO: Initialize NLU Processor.")
        self.config = config

    def process(self, text: str) -> Tuple[str, Dict[str, Any]]:
        """
        Processes the input text to determine intent and extract entities.

        Args:
            text: The raw text string from speech recognition.

        Returns:
            A tuple containing:
                - intent (str): The recognized intent (e.g., "PickUp", "GoTo", "Chat", "Unknown").
                - entities (Dict[str, Any]): A dictionary of extracted information (e.g., {"object": "apple", "location": "kitchen"}).
        """
        print(f"TODO: Process text '{text}' for NLU.")
        # <<<<< IMPLEMENT NLU LOGIC >>>>>
        # - Tokenization, Part-of-Speech tagging, Named Entity Recognition.
        # - Intent classification based on keywords, sentence structure, or ML model.
        # - Entity extraction and resolution (e.g., linking "the red ball" to a specific object in the world model).

        # --- Example Simple Keyword-based NLU ---
        lower_text = text.lower()
        intent = "Unknown"
        entities: Dict[str, Any] = {}

        if "pick up" in lower_text or "grab" in lower_text:
            intent = "PickUp"
            # Simple entity extraction: assume the word after "the" is the object
            parts = lower_text.split(" the ")
            if len(parts) > 1:
                 object_name = parts[1].split(" ")[0] # Take the first word after "the"
                 entities["object"] = object_name.strip()
                 # More sophisticated NLU would handle adjectives ("the red block")
                 # and phrases ("the block on the table")

        elif "go to" in lower_text or "navigate to" in lower_text:
            intent = "GoTo"
             parts = lower_text.split(" to ")
             if len(parts) > 1:
                  location_name = " ".join(parts[1].split()).strip() # Take rest of the string, remove extra spaces
                  if location_name:
                      entities["location"] = location_name

        elif "what is that" in lower_text or "identify" in lower_text:
             intent = "Identify"
             # Needs context or visual input to identify "that" - World Model helps here
             # Entity might be a reference to a visually salient object

        elif "how are you" in lower_text or "hello" in lower_text or "thank you" in lower_text:
             intent = "Chat" # General conversational turn

        # --- End Example Simple Keyword-based NLU ---

        print(f"NLU Result: Intent='{intent}', Entities={entities}")
        return intent, entities

# --- Example Usage (in DialogueManager or main.py) ---
# # Inside JamieRobot.__init__
# # self.nlu_processor = NLUProcessor(config=self.config['ai']['nlu'])
# # Inside _handle_vision_data when type is "command" and has "text":
# # text_command = data.get("text")
# # intent, entities = self.nlu_processor.process(text_command)
# # self.dialogue_manager.handle_user_command(intent, entities, command_text=text_command)
```

echo "brain/src/ai/nlu_processor.py created."

# brain/src/ai/dialogue_manager.py (Placeholder)
echo "Creating brain/src/ai/dialogue_manager.py file..."
cat << 'EOF' > "$PROJECT_ROOT/brain/src/ai/dialogue_manager.py"
# This module manages the overall conversation flow, context,
# and decides the robot's spoken responses.

# It interfaces with:
# - NLU Processor: To understand user input (intent, entities).
# - Task Manager: To initiate robotics actions if the user command is a task.
# - Gemini Client: To generate natural language responses for chat or questions.
# - World Model: To get information about the robot's state and environment.
# - Vision Communicator: To send text back to the Vision app for TTS.
# - (Optional) Personality module: To influence response style and proactive behavior.

from typing import Dict, Any, Optional
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
        task_manager: Any, # TaskManager or similar
        gemini_client: Any, # GeminiAPIClient or similar
        vision_communicator: Any, # PhoneWifiServer or similar
        world_model: Any, # WorldModel or similar
        config=None
    ):
        print("TODO: Initialize Dialogue Manager.")
        # self.nlu_processor = nlu_processor # If NLU processing happens here
        self.task_manager = task_manager
        self.gemini_client = gemini_client
        self.vision_communicator = vision_communicator
        self.world_model = world_model
        self.config = config

        self._conversation_context: Dict[str, Any] = {} # State for conversation history, referred entities, etc.
        # GeminiClient already manages the raw turn history, this is for higher-level context.

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
        print(f"Dialogue Manager handling: Intent='{intent}', Entities={entities}")

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


        elif intent == "Chat":
             # <<<<< USE GEMINI CLIENT FOR GENERAL CONVERSATION >>>>>
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
                     print(f"Gemini API Error: {e}")
                     self._respond_error("I had trouble talking to my AI brain.")

             else:
                 self._respond_speak("Yes?") # Simple fallback if command_text is unexpectedly empty for chat intent


        elif intent == "Unknown":
             # If NLU couldn't understand the intent
             self._respond_speak("I didn't understand that. Can you please rephrase?")

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
                 print(f"Sent text for TTS to Vision: '{text}'")
            except Exception as e:
                 print(f"Error sending speak command to Vision: {e}")
                 # TODO: Handle communication error (e.g., speak error message locally if possible)
        else:
            print(f"Vision app not connected. Cannot speak: '{text}'")
            # TODO: Log or handle cases where Vision is not available for speaking

    def _respond_thinking(self, text: str = "Thinking...") -> None:
         """Sends text to Vision to indicate processing is happening."""
         # This could be a specific type of message that triggers a different UI/audio cue on the phone
         # Or just use _respond_speak
         print(f"Indicating thinking: {text}")
         self._respond_speak(text) # Example: just speak the text

    def _respond_error(self, text: str = "I encountered an error.") -> None:
        """Sends text to Vision to indicate an error."""
        print(f"Indicating error: {text}")
        self._respond_speak(text) # Example: just speak the text

    def _respond_busy(self, original_command_text: Optional[str]) -> None:
        """Responds that the robot is currently busy."""
        print("Responding busy.")
        self._respond_speak("I'm busy right now. Please wait until I'm finished.")
        # Optional: Log the command that was ignored because robot was busy

    # --- Optional: Handle feedback from tasks or speaking ---
    def on_speaking_finished(self, utterance_id: str) -> None:
        """Callback when Vision confirms a speaking task is done."""
        # The TaskManager might need this feedback if a plan step involves speaking
        print(f"Dialogue Manager received speech finished confirmation for ID: {utterance_id}")
        # TODO: TaskManager might be waiting for this

    def on_task_status_update(self, task_id: str, status: str, message: Optional[str] = None):
        """Receives status updates from the TaskManager and potentially speaks them."""
        # Example statuses: "navigating", "arrived", "grasping", "grasp_failed", "task_complete"
        print(f"Dialogue Manager received task update: {task_id} - {status} - {message}")
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
    #     print(f"TODO: Resolve location name: {location_name}")
    #     return None # Placeholder

    # def _identify_object_in_view(self) -> Optional[ObjectInfo]:
    #     """Identifies the most likely object the robot is looking at based on vision data."""
    #     # Needs access to recent vision detections and the robot's gaze direction (pan/tilt)
    #     print("TODO: Identify object in view.")
    #     return None # Placeholder


# --- Example Usage (in main.py, integrated with TaskManager) ---
# # Inside JamieRobot.__init__
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
```

echo "brain/src/ai/dialogue_manager.py created."

# brain/src/ai/personality.py (Placeholder)
echo "Creating brain/src/ai/personality.py file..."
cat << 'EOF' > "$PROJECT_ROOT/brain/src/ai/personality.py"
# This module defines and influences the robot's personality and proactive behaviors.

# It could contain:
# - Personality traits (e.g., cheerful, curious, cautious).
# - Rules or models to inject personality into responses (used by DialogueManager).
# - Logic for proactive behaviors (e.g., commenting on things it sees, greeting people, suggesting activities) - triggered based on World Model state and internal state.
# - An internal state model (e.g., "energy level", "curiosity level").

# This is highly optional and advanced.

from typing import Dict, Any

class Personality:
    """Defines the robot's personality and proactive behavior logic."""

    def __init__(self, config=None):
        print("TODO: Initialize Personality module.")
        self.config = config
        # Define personality traits (e.g., self.traits = {"friendliness": 0.8, "curiosity": 0.9})
        # Initialize internal state (e.g., self.internal_state = {"energy": 1.0, "mood": "neutral"})

    def influence_response(self, text: str) -> str:
        """Modifies a text response based on personality traits."""
        # <<<<< IMPLEMENT PERSONALITY INFLUENCE >>>>>
        # Example: Add exclamation marks if cheerful, add hesitant phrases if cautious.
        print(f"TODO: Infuse personality into text: '{text}'")
        # For example: if self.traits.get("cheerfulness", 0) > 0.7: return text + "!"
        return text # Return the original text for now

    def check_proactive_behaviors(self, world_model: Any) -> None:
        """Checks if any proactive behaviors should be triggered based on state."""
        # This method would be called periodically in the main loop or TaskManager.
        print("TODO: Check for proactive behaviors.")
        # <<<<< IMPLEMENT PROACTIVE BEHAVIOR TRIGGERS >>>>>
        # Example:
        # if world_model.sees_pet() and world_model.robot_state.current_task == "IDLE":
        #     # Trigger a task or dialogue:
        #     # self.dialogue_manager.handle_system_event("sees_pet", {"pet": pet_info})
        pass

# --- Example Usage (in DialogueManager or main.py) ---
# # Inside JamieRobot.__init__
# # self.personality = Personality(config=self.config['ai']['personality'])
# # Inside DialogueManager before speaking:
# # final_text_to_speak = self.personality.influence_response(raw_generated_text)
# # self._respond_speak(final_text_to_speak)
# # In main loop:
# # self.personality.check_proactive_behaviors(self.world_model) # Periodically check for proactive events
```

echo "brain/src/ai/personality.py created."

# brain/src/ai/task_manager.py (Placeholder)
echo "Creating brain/src/ai/task_manager.py file..."
cat << 'EOF' > "$PROJECT_ROOT/brain/src/ai/task_manager.py"
# This module is responsible for translating high-level goals (from NLU/Dialogue Manager)
# into sequences of low-level robot actions (a plan).
# It executes the plan and handles feedback from the Motion controller and sensors.

# It interfaces with:
# - Dialogue Manager: To receive goals and report task status/outcomes.
# - World Model: To get current state (robot pose, object info, sensor readings) and map.
# - Motion Communicator: To send low-level commands (move wheels, move arm joints, etc.) to Arduino.
# - Robotics Algorithms: To calculate paths, joint angles, grasp poses.
# - Sensor Handlers: To receive and interpret feedback (e.g., "arrived", "grasp confirmed", "bump").

from typing import Dict, Any, List, Optional
import time # For timing actions or adding delays

# from .dialogue_manager import DialogueManager # Import if needed for status updates
# from ..communication.arduino_serial import ArduinoSerialCommunicator # Import for motion control
# from ..perception.world_model import WorldModel # Import for state/map
# from ..robotics.arm_kinematics import ArmKinematics # Import for IK
# from ..robotics.path_planning import PathPlanning # Import for navigation
# from ..robotics.grasp_planning import GraspPlanning # Import for grasp planning

class TaskManager:
    """Manages robot tasks and plan execution."""

    def __init__(
        self,
        world_model: Any, # WorldModel instance
        motion_communicator: Any, # ArduinoSerialCommunicator instance
        # dialogue_manager: Optional[Any] = None, # DialogueManager instance for status updates
        # kinematics_solver: Optional[Any] = None, # ArmKinematics instance
        # path_planner: Optional[Any] = None, # PathPlanning instance
        # grasp_planner: Optional[Any] = None, # GraspPlanning instance
        config=None
    ):
        print("TODO: Initialize Task Manager.")
        self.world_model = world_model
        self.motion_communicator = motion_communicator
        # self.dialogue_manager = dialogue_manager
        # self.kinematics_solver = kinematics_solver
        # self.path_planner = path_planner
        # self.grasp_planner = grasp_planner
        self.config = config

        self._current_goal: Optional[Dict[str, Any]] = None
        self._current_plan: List[Dict[str, Any]] = [] # Sequence of plan steps
        self._current_step_index: int = 0
        self._step_feedback_pending: bool = False # Flag to wait for feedback for the current step
        self._last_step_start_time: float = 0.0 # For timing out steps

        # State variables to track ongoing actions if they are async
        # self._is_navigating: bool = False
        # self._is_arm_moving: bool = False
        # self._expected_feedback_id: Optional[str] = None # What specific feedback are we waiting for?


    def is_robot_busy(self) -> bool:
        """Checks if the robot is currently executing a task."""
        # The robot is busy if it has a goal and is executing a plan
        # return self._current_goal is not None and self._current_step_index < len(self._current_plan)
        # Or use the high-level state in the WorldModel:
        return self.world_model.robot_state.current_task != "IDLE"


    def set_goal(self, goal: Dict[str, Any]) -> None:
        """
        Receives a new high-level goal (from NLU/Dialogue Manager) and starts planning.
        """
        if self.is_robot_busy():
            print(f"Robot is busy with task {self.world_model.robot_state.current_task}. Cannot set new goal: {goal['intent']}")
            # TODO: Report busy status back via Dialogue Manager
            return

        print(f"Task Manager received new goal: {goal['intent']}")
        self._current_goal = goal
        self._current_plan = [] # Clear previous plan
        self._current_step_index = 0
        self._step_feedback_pending = False
        self._last_step_start_time = 0.0 # Reset timer

        # Set high-level state
        self.world_model.robot_state.current_task = "PLANNING"
        # TODO: Report status to Dialogue Manager: self.dialogue_manager.on_task_status_update(task_id=goal.get('id', 'N/A'), status="planning")

        # <<<<< IMPLEMENT PLANNING LOGIC HERE >>>>>
        # Based on self._current_goal and the WorldModel's current state (map, object locations),
        # generate a sequence of symbolic actions.
        # Example: If goal is {"intent": "pick_up", "object_id": "obj_123"}
        # 1. Get object info from WorldModel: object_info = self.world_model.get_object_by_id(goal['object_id'])
        # 2. If object exists and is pickable:
        # 3. Calculate approach location: approach_loc = self.path_planner.calculate_approach(self.world_model.robot_state.base_pose, object_info.pose)
        # 4. Calculate grasp pose: grasp_pose_arm_frame = self.grasp_planner.estimate_grasp_pose(object_info) # Requires 3D data/model
        # 5. Calculate pre-grasp & lift poses: pre_grasp_pose, lift_pose = self.kinematics_solver.calculate_pre_lift_poses(grasp_pose_arm_frame)
        # 6. Convert arm poses (in arm frame) to sequences of joint angles using Inverse Kinematics
        #    pre_grasp_angles = self.kinematics_solver.solve_ik(pre_grasp_pose)
        #    grasp_angles = self.kinematics_solver.solve_ik(grasp_pose_arm_frame)
        #    lift_angles = self.kinematics_solver.solve_ik(lift_pose)

        # 7. Populate the plan with steps (dictionaries describing the action and params)
        self._current_plan = [
            {"action": "speak", "params": {"text": f"Okay, I will try to pick up the {goal.get('object_id', 'object')}."}}, # Speak confirmation (handled by DialogueManager)
            {"action": "navigate_to", "params": {"location": {"x": 1.0, "y": 0.5, "yaw": 0.0}}}, # Example waypoint
            # Add more waypoints if path planning provides them
            {"action": "move_arm_to_angles", "params": {"angles":}}, # Example pre-grasp angles (Joint:Angle)
            {"action": "move_arm_to_angles", "params": {"angles":}}, # Example grasp angles
            {"action": "set_gripper", "params": {"state": "close"}}, # Close gripper
            {"action": "wait", "params": {"duration": 0.5}}, # Wait to secure grip
            {"action": "move_arm_to_angles", "params": {"angles":}}, # Example lift angles
            {"action": "speak", "params": {"text": "I think I've got it."}},
            {"action": "navigate_to", "params": {"location": {"x": 0.0, "y": 0.0, "yaw": 0.0}}}, # Example return home
            {"action": "move_arm_to_angles", "params": {"angles":}}, # Example drop-off angles
            {"action": "set_gripper", "params": {"state": "open"}}, # Open gripper
            {"action": "wait", "params": {"duration": 0.5}},
             {"action": "speak", "params": {"text": "Task complete."}},
        ]
        # TODO: Add error handling steps (e.g., "if grasp fails, replan or report failure")

        if self._current_plan:
            self.world_model.robot_state.current_task = "EXECUTING_PLAN"
            self._current_step_index = 0 # Start from the first step
            print(f"Plan created with {len(self._current_plan)} steps. Starting execution.")
            # self.dialogue_manager.on_task_status_update(task_id=goal.get('id', 'N/A'), status="executing", message=f"Starting plan with {len(self._current_plan)} steps.")
            # Execute the first step immediately or wait for process_current_task loop
            # self.process_current_task() # Execute the first step
        else:
            self._current_goal = None # Clear goal if planning failed
            self.world_model.robot_state.current_task = "IDLE"
            print("Planning failed or resulted in an empty plan.")
            # TODO: Report planning failure back via Dialogue Manager

    # This method should be called periodically by the main loop or triggered by events
    def process_current_task(self) -> None:
        """Processes the current step of the active plan."""
        # Check if we are in an executing state and not waiting for feedback
        if self.world_model.robot_state.current_task != "EXECUTING_PLAN":
            return # Not executing a plan
        if self._step_feedback_pending:
             # Check for timeout if feedback is pending
             # if time.time() - self._last_step_start_time > self.config['task_manager'].get('step_timeout_sec', 10.0): # Default 10s
             #     print(f"Step {self._current_step_index} timed out while waiting for feedback.")
             #     self._handle_step_failure("timeout") # Handle timeout
             return # Still waiting for feedback

        # Check if plan is finished
        if self._current_step_index >= len(self._current_plan):
            print("Plan execution finished.")
            self._handle_plan_completion()
            return

        # Execute the current step
        step = self._current_plan[self._current_step_index]
        action = step.get("action")
        params = step.get("params", {})

        print(f"Executing step {self._current_step_index}: Action='{action}'")
        self._last_step_start_time = time.time() # Start timer for this step
        self._step_feedback_pending = False # Assume no feedback needed initially

        # <<<<< IMPLEMENT ACTION EXECUTION >>>>>
        # Map symbolic actions to sending commands to the Motion controller or other modules.

        if action == "navigate_to":
            location = params.get("location")
            if location:
                # Convert location (e.g., WorldModel pose) to navigation goal for PathPlanner
                # self.path_planner.set_navigation_goal(location)
                # Tell PathPlanner to start navigating
                # The PathPlanner needs to calculate motor commands and send them to MotionCommunicator
                # It also needs to signal back when navigation is complete ("NAV_COMPLETE" feedback)
                print(f"TODO: Start navigation towards {location}")
                self.motion_communicator.send_command("M:150:150\n") # Example: just move forward indefinitely
                self._step_feedback_pending = True # Expect "NAV_COMPLETE" feedback

            else: self._handle_step_failure("missing_location")

        elif action == "move_arm_to_angles":
            angles = params.get("angles") # Expected to be a list of joint angles
            if angles and len(angles) == 6: # Assuming 6 DOF
                 # Send joint angles to Motion controller
                 for i, angle in enumerate(angles):
                     self.motion_communicator.send_command(f"J:{i}:{int(angle)}\n") # Send as integer
                 print(f"TODO: Send arm angles: {angles}")
                 self._step_feedback_pending = True # Expect "ARM_REACHED_POSE" feedback (or similar)

            else: self._handle_step_failure("invalid_angles")

        elif action == "set_gripper":
            state = params.get("state") # "open" or "close"
            gripper_joint_index = 5 # <<<<< SET YOUR GRIPPER JOINT INDEX >>>>>
            if state == "open":
                # self.motion_communicator.send_command(f"J:{gripper_joint_index}:{self.config['robot_parameters']['gripper_open_angle']}\n") # Use config for angles
                print("TODO: Send gripper open command")
                self._step_feedback_pending = True # Expect confirmation or time out
            elif state == "close":
                 # self.motion_communicator.send_command(f"J:{gripper_joint_index}:{self.config['robot_parameters']['gripper_close_angle']}\n") # Use config for angles
                 print("TODO: Send gripper close command")
                 self._step_feedback_pending = True # Expect confirmation or force sensor feedback (processed in process_feedback)
            else: self._handle_step_failure("invalid_gripper_state")

        elif action == "wait":
            duration = params.get("duration", 1.0)
            print(f"Waiting for {duration} seconds...")
            time.sleep(duration) # This action blocks, which is okay for simple waits
            self._step_feedback_pending = False # Completes after sleep
            # Move to the next step immediately after waiting
            self._current_step_index += 1
            # Optionally call process_current_task again here to immediately start the next step
            # self.process_current_task()


        elif action == "speak":
            text = params.get("text")
            if text:
                 # Send text to Dialogue Manager, which sends to Vision for TTS
                 # self.dialogue_manager.respond_speak(text)
                 print(f"TODO: Speak: '{text}'")
                 # Need feedback from Vision app when speaking is done ('speech_response_done')
                 self._step_feedback_pending = True # Wait for speak completion

            else: self._handle_step_failure("missing_speak_text")

        # Add other symbolic actions: "find_object", "scan_area", "charge", "identify_object", etc.

        if not self._step_feedback_pending and action != "wait":
            # If the action doesn't require explicit feedback and isn't a wait,
            # assume it completes immediately and move to the next step.
            # This should be used cautiously only for very fast, reliable commands.
            self._current_step_index += 1
            # Optionally call process_current_task again to immediately start the next step
            # self.process_current_task() # Use this if you don't rely on the main loop frequency

    def process_feedback(self, feedback_data: str) -> None:
        """
        Processes feedback received from the Motion controller or other modules.
        This method is called by communication handlers (e.g., _handle_motion_data).
        """
        print(f"Task Manager processing feedback: {feedback_data}")

        # Check if we are waiting for feedback for the current step
        if self._step_feedback_pending:
            current_step = self._current_plan[self._current_step_index]
            action = current_step.get("action")
            # TODO: Determine if the feedback matches the expected feedback for the current action

            # Example: Feedback from ArduinoSerialCommunicator or PathPlanning
            if action == "navigate_to" and feedback_data == "NAV_COMPLETE": # Example feedback string
                 print("Navigation step confirmed complete.")
                 self._step_feedback_pending = False
                 self._current_step_index += 1 # Move to the next plan step
                 # Optionally trigger processing the next step immediately
                 # self.process_current_task()

            # Example: Feedback from ArduinoSerialCommunicator or ArmKinematics/Control
            elif action == "move_arm_to_angles" and feedback_data == "ARM_REACHED_POSE": # Example feedback string
                 print("Arm movement step confirmed complete.")
                 self._step_feedback_pending = False
                 self._current_step_index += 1
                 # self.process_current_task()

            # Example: Feedback from ArduinoSerialCommunicator or ForceSensor
            elif action == "set_gripper" and current_step.get("params", {}).get("state") == "close":
                 # Need feedback that gripper closed AND grasped successfully
                 # This might come as a sensor reading ("SENSOR:force_pin:value")
                 # Need to check if force value > threshold using WorldModel
                 if feedback_data.startswith("SENSOR:") and "force_sensor_pin" in feedback_data: # Example check
                     # force_value = self.world_model.get_sensor_value(FORCE_SENSOR_PIN) # Need macro for pin
                     # if force_value is not None and force_value > self.config['robot_parameters'].get('grasp_force_threshold', 1.0): # Check threshold
                     print("Gripper close step confirmed, grasp detected.")
                     self.world_model.robot_state.gripper_state = "holding" # Update state
                     self._step_feedback_pending = False
                     self._current_step_index += 1
                     # self.process_current_task()
                 # Else: Gripper closed but no grasp detected? Handle failure?
                 elif feedback_data == "GRIPPER_CLOSED_NO_GRASP": # Example feedback string
                     print("Gripper closed but no grasp detected.")
                     self._handle_step_failure("no_grasp")
                 elif feedback_data == "GRIPPER_CLOSED_GRASPED": # Example feedback string confirming grasp
                     print("Gripper close step confirmed, grasp detected.")
                     self.world_model.robot_state.gripper_state = "holding" # Update state
                     self._step_feedback_pending = False
                     self._current_step_index += 1
                     # self.process_current_task()
                 elif feedback_data == "GRIPPER_CLOSED_ERROR": # Example error feedback
                     print("Gripper closed with error.")
                     self._handle_step_failure("gripper_error")


            elif action == "set_gripper" and current_step.get("params", {}).get("state") == "open":
                 if feedback_data == "GRIPPER_OPEN_COMPLETE": # Example feedback
                     print("Gripper open step confirmed.")
                     self.world_model.robot_state.gripper_state = "open" # Update state
                     self._step_feedback_pending = False
                     self._current_step_index += 1
                     # self.process_current_task()
                 elif feedback_data == "GRIPPER_OPEN_ERROR":
                     print("Gripper open with error.")
                     self._handle_step_failure("gripper_error")

            elif action == "speak" and feedback_data.startswith("speech_response_done"): # Example feedback from Vision
                 # The Vision app sends this via WifiCommunicator when TTS is done speaking
                 # Extract utterance ID if needed: utterance_id = feedback_data.split(":")
                 print("Speak step confirmed complete by Vision.")
                 self._step_feedback_pending = False
                 self._current_step_index += 1
                 # self.process_current_task()

            # Handle other feedback types...

    def _handle_step_failure(self, reason: str) -> None:
        """Handles failure of the current plan step."""
        failed_step = self._current_plan[self._current_step_index]
        action = failed_step.get("action")
        print(f"Step {self._current_step_index} ({action}) failed due to: {reason}")

        # <<<<< IMPLEMENT FAILURE HANDLING / REPLANNING >>>>>
        # 1. Stop robot motion as a safety measure:
        self.motion_communicator.send_command("STOP\n")
        # 2. Report failure via Dialogue Manager:
        # self.dialogue_manager.on_task_status_update(task_id=self._current_goal.get('id', 'N/A'), status="step_failed", message=f"{action} failed: {reason}")
        # self.dialogue_manager.respond_speak(f"I failed to {action.replace('_', ' ')}. Reason: {reason}.") # Simple spoken error
        print(f"TODO: Handle failure of action '{action}' due to '{reason}'.")

        # 3. Decide next steps:
        #    - Simple: Abort the current goal and return to IDLE.
        #    - Moderate: Try retrying the current step.
        #    - Advanced: Re-plan from the current state to achieve the goal.
        #    - Advanced: Set a new goal for recovery behavior (e.g., move to a safe location).

        # Simple approach: Abort goal and go back to IDLE
        self._handle_plan_completion(success=False) # Treat as overall plan failure


    def _handle_plan_completion(self, success: bool = True) -> None:
        """Handles the completion (success or failure) of the current plan."""
        print(f"Plan execution completed. Success: {success}")
        # Reset state
        self._current_goal = None
        self._current_plan = []
        self._current_step_index = 0
        self._step_feedback_pending = False
        self._last_step_start_time = 0.0

        # Set high-level state
        self.world_model.robot_state.current_task = "IDLE"

        # Report outcome via Dialogue Manager
        # status = "task_complete" if success else "task_failed"
        # message = "Task finished successfully." if success else "Task failed."
        # self.dialogue_manager.on_task_status_update(task_id=self._current_goal.get('id', 'N/A') if self._current_goal else 'N/A', status=status, message=message)
        # if success: self.dialogue_manager.respond_speak(message) # Speak success message
        # else: self.dialogue_manager.respond_error(message) # Speak failure message

        print("Task Manager is now IDLE.")


    # Optional: Method to handle requests from Dialogue Manager to set a lower priority goal
    # def set_goal_low_priority(self, goal: Dict[str, Any]) -> None:
    #    """Sets a goal that can be preempted by higher priority goals."""
    #    # Needs logic to store low priority goals and swap if robot becomes idle or high priority goal arrives.
    #    pass
```

echo "brain/src/ai/task_manager.py created."

# brain/src/robotics/__init__.py
echo "Creating brain/src/robotics/__init__.py file..."
cat << 'EOF' > "$PROJECT_ROOT/brain/src/robotics/__init__.py"
# This file makes 'robotics' a Python package
# This package contains the core robotics algorithms.
# from .arm_kinematics import ArmKinematics
# from .path_planning import PathPlanning
# from .grasp_planning import GraspPlanning
