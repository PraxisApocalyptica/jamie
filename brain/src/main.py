import time
import logging
import threading
import traceback # Import for logging errors

from dotenv import load_dotenv
from typing import Dict, Any

# Import your modules from src/
from src.communication.arduino_serial import ArduinoSerialCommunicator
from src.communication.phone_wifi_server import PhoneWifiServer
from src.perception.world_model import WorldModel
from src.ai.task_manager import TaskManager
from src.handlers.log_handler import LogHandler 
from src.config import load_config
# Import other modules as you implement them:
# from src.hardware_interfaces.three_d_camera import ThreeDCamera
# from src.perception.object_processor import ObjectProcessor
# from src.perception.slam_localization import SlamLocalization
# from src.robotics.arm_kinematics import ArmKinematics
# from src.robotics.path_planning import PathPlanning
# from src.robotics.grasp_planning import GraspPlanning
# from src.ai.nlu_processor import NLUProcessor
from src.ai.dialogue_manager import DialogueManager
# from src.ai.personality import Personality # If separate
from src.ai.clients.gemini.client import GeminiClient # For general chat
from src.ai.clients.speech.google_tts import GttsTTSClient


# --- Main Robot Class ---
class ApocalypticaRobot:
    def __init__(self, config_path="config/robot.yaml"):
        self._logger = logging.getLogger(self.__class__.__name__)
        load_dotenv()
        self.config = load_config(config_path)
        robot = self.config.get('robot', {})
        self.name = robot.get('name', 'Jamie')

        # --- Communication ---
        self.motion_comm = ArduinoSerialCommunicator(
            port=self.config['motion']['serial_port'],
            baud_rate=self.config['motion']['serial_baud_rate']
        )
        self.vision_comm = PhoneWifiServer(
            host=self.config['vision']['wifi_host'],
            port=self.config['vision']['wifi_port'],
            data_handler=self._handle_vision_data # Register callback
        )

        # --- World Model ---
        self.world_model = WorldModel() # Manages robot state, map, objects

        gtts_tts_client = GttsTTSClient(lang="en", default_playback_speed=1.2)

        # --- AI and Task Management ---
        self.gemini_client = GeminiClient(
           api_key= os.getenv("GEMINI_SECRET_KEY") or self.config['api_keys']['gemini'],
           max_output_tokens=self.config['ai']['gemini'].get('max_tokens', 150),
           temperature=self.config['ai']['gemini'].get('temperature', 0.7),
           max_history_turns=self.config['ai']['gemini'].get('max_history_turns', 20),
           config=self.config.get('robot', {}),
           speech_assistant=gtts_tts_client
        )
        # self.nlu_processor = NLUProcessor() # For parsing commands from text
        self.task_manager = TaskManager(
            world_model=self.world_model,
            motion_communicator=self.motion_comm,
            # Add other dependencies: kinematics, planning, etc.
            # kinematics_solver=ArmKinematics(...),
            # path_planner=PathPlanning(...),
            # grasp_planner=GraspPlanning(...),
            # dialogue_manager=self.dialogue_manager, # To generate spoken responses
            # vision_communicator=self.vision_comm, # To send commands/status to Vision
        )
        self.dialogue_manager = DialogueManager(
            gemini_client=self.gemini_client,
            vision_communicator=self.vision_comm,
            world_model=self.world_model,
            task_manager=self.task_manager
        ) # Manages conversation flow and speaks via Vision

        # --- Hardware Interfaces (Direct to Pi) ---
        # self.three_d_camera = ThreeDCamera(camera_id=self.config['sensors']['3d_camera']['id'])
        # self.encoder_reader = EncoderReader(...)
        # self.force_sensor = ForceSensor(...)

        # --- Other Components ---
        # self.object_processor = ObjectProcessor(world_model=self.world_model, ...)
        # self.slam_localization = SlamLocalization(world_model=self.world_model, ...)


    def _handle_vision_data(self, data: Dict[str, Any]) -> None:
        """Callback method to process data received from the Vision (Android/iOS) app."""
        # This method runs in a background thread managed by PhoneWifiServer
        # Avoid blocking this thread with heavy processing.
        # Delegate complex tasks (like NLU, Task execution) to the main loop or TaskManager.

        # Add logging to see what data is received
        self._logger.debug(f"Received data from Vision: {data}")

        data_type = data.get("type")

        if data_type == "slam_update":
            slam_pose = data.get("pose")
            map_data = data.get("map")
            if slam_pose:
                 # <<<<< INTEGRATE SLAM DATA >>>>>
                 # Process SLAM pose and potentially map data here or pass to SlamLocalization
                 # self.slam_localization.process_slam_pose(slam_pose)
                 pass # Placeholder

        elif data_type == "vision_update":
            detected_objects_list = data.get("objects", []) # List of detected objects from phone vision
            if detected_objects_list:
                 # <<<<< INTEGRATE VISION DATA >>>>>
                 # Process detected objects list here or pass to ObjectProcessor
                 # self.object_processor.process_vision_detections(detected_objects_list)
                 pass # Placeholder

        elif data_type == "command":
            # Received a text command from the phone (from ASR via phone's NLU or just raw text)
            command_text = data.get("text") # Raw text from ASR
            command_intent = data.get("intent") # Optional: if phone does initial NLU
            command_entities = data.get("entities") # Optional: if phone does initial NLU

            if command_text:
                 self._logger.debug(f"Received command text from Vision: {command_text}")
                 # <<<<< PROCESS COMMAND >>>>>
                 # 1. If phone didn't do NLU, process it here:
                 #    intent, entities = self.nlu_processor.process(command_text)
                 # 2. Pass the intent and entities to the Dialogue Manager/TaskManager
                 #    self.dialogue_manager.handle_user_command(intent, entities, command_text) # Dialogue manager decides if it's chat or task
                 #    # Or directly trigger TaskManager if Dialogue Manager isn't the first step:
                 #    # self.task_manager.set_goal_from_command(intent, entities)
                 pass # Placeholder
            elif command_intent: # If phone sent pre-parsed intent
                 self._logger.debug(f"Received parsed command from Vision: Intent='{command_intent}' Entities={command_entities}")
                 # <<<<< PROCESS PARSED COMMAND >>>>>
                 # self.dialogue_manager.handle_user_command(command_intent, command_entities, command_text=None)
                 # or self.task_manager.set_goal_from_command(command_intent, command_entities)
                 pass # Placeholder

        elif data_type == "speech_response_done":
             # Notification from Vision that it finished speaking a response sent earlier
             utterance_id = data.get("utterance_id")
             self._logger.debug(f"Vision confirmed speaking done for utterance ID: {utterance_id}")
             # TODO: Dialogue Manager or TaskManager might need this feedback to continue a turn or plan
             # self.dialogue_manager.on_speaking_finished(utterance_id) # Example
             pass # Placeholder


        # Add other data types: sensor data relayed from phone (e.g., compass?), status updates, etc.


    def _handle_motion_data(self, data: str) -> None:
        """Callback method to process data received from Motion (Arduino) over Serial."""
        # This method runs in a background thread managed by ArduinoSerialCommunicator
        # Avoid blocking this thread with heavy processing.
        # Delegate complex tasks (like triggering reactions) to the main loop or TaskManager.

        # Add logging to see what data is received
        self._logger.debug(f"Received data from Motion: {data}")

        # Data is likely sensor readings (e.g., "SENSOR:pin:value") or acknowledgments (e.g., "NAV_COMPLETE")
        # <<<<< PROCESS ARDUINO DATA >>>>>
        # Update world_model.physical_sensors
        # Check for critical alerts (bump sensor -> trigger collision avoidance in TaskManager)
        # Check for acknowledgments/feedback that a command is complete (e.g., "NAV_COMPLETE")
        # self.world_model.update_sensor_data(data) # Example
        # self.task_manager.process_feedback(data) # Example
        pass # Placeholder


    def run(self):
        self._logger.info(f"Starting {self.name}...")

        # --- Connect Components ---
        # Connect to Arduino, register callback for incoming data
        self.motion_comm.connect(data_handler=self._handle_motion_data)
        # Start listening for phone connection, register callback for incoming data
        self.vision_comm.start(data_handler=self._handle_vision_data) # Pass handler during start

        # Give connections time to establish
        time.sleep(2)

        if not self.motion_comm.is_connected:
            self._logger.warning("Failed to connect to Motion controller. Movement is unavailable.")
            # return
        # is_listening check is done inside vision_comm.start()

        # TODO: Connect/Initialize other hardware interfaces (3D camera, encoders)
        # try:
        #     self.three_d_camera.initialize()
        #     self._logger.debug("3D Camera initialized.")
        # except Exception as e:
        #     self._logger.warning(f"Warning: Failed to initialize 3D Camera: {e}")


        self._logger.info("All core communication components connected/started.")
        # Optional: Send initial command to Motion (e.g., move arm to home position)
        # self.motion_comm.send_command("J:0:90\n") # Example home command

        # --- Main Loop ---
        try:
            while True:
                # This main loop is the heart of the Brain's processing cycle.
                # It can run periodic tasks and check for conditions.

                # --- Perception Updates (if not thread-based) ---
                # If 3D camera/other sensors are not read in their own threads, read them here periodically
                # self.three_d_camera.capture_and_process() # Example
                # self.encoder_reader.read_data() # Example

                # --- Thinking / Decision Making ---
                # Check for task execution status and trigger the next step if ready.
                # The TaskManager holds the main logic flow for tasks.
                # This might be called periodically or be triggered by feedback.
                # self.task_manager.process_current_task() # Example: TaskManager manages its own plan steps/waiting

                # Example: Periodically check battery level if Arduino sends it
                # battery_level = self.world_model.get_battery_level() # Assumes WorldModel gets updates from Motion handler
                # if battery_level is not None and battery_level < self.config['power'].get('low_battery_threshold', 0.2): # Default 20%
                #     self.task_manager.set_goal_low_priority({"intent": "find_charger"})


                # Keep the main loop alive and responsive
                time.sleep(0.05) # Adjust loop frequency (e.g., 20 Hz)

        except KeyboardInterrupt:
            self._logger.warning("\nCtrl+C detected. Shutting down.")

        except Exception as e:
            self._logger.critical(f"\nAn unhandled error occurred: {e}")
            import traceback
            traceback.print_exc() # Print traceback for debugging
            # Attempt to stop motors as a safety measure
            try:
                self.motion_comm.send_command("STOP\n")
            except Exception:
                pass # Ignore errors during emergency stop

        finally:
            # --- Cleanup ---
            self._logger.debug("Cleaning up...")
            # Ensure robot is in a safe state
            self.motion_comm.send_command("STOP\n") # Stop base motors
            # TODO: Send command to move arm to a safe 'home' position
            time.sleep(1.0) # Give time for final commands to send/execute

            # Disconnect communication channels
            self.motion_comm.disconnect()
            self.vision_comm.stop()

            # TODO: Shut down other hardware interfaces (3D camera, etc.)
            # self.three_d_camera.shutdown()

            self._logger.info("Shutdown complete.")


# --- Script Entry Point ---
if __name__ == "__main__":
    # Ensure working directory is the root of the repo or adjust config path
    # The main script is in jamie/brain/src/, config is in jamie/brain/config/
    # So the path relative to main.py is ../config/robot.yaml
    config_file_relative_path = "../config/robot.yaml"

    logger_handler = LogHandler()
    _logger = logger_handler.get_logger()

    # Add a check if running from the correct directory (optional but helpful)
    import os
    # Get the directory of the current script (brain/src/)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Construct the absolute path to the config file
    config_file_abs_path = os.path.join(script_dir, config_file_relative_path)

    if not os.path.exists(config_file_abs_path):
        _logger.error(f"Error: Configuration file not found at {config_file_abs_path}")
        _logger.warning(f"Please ensure the script is run from the correct location (e.g., 'cd jamie/brain' then 'python src/main.py')")
        exit(1)

    robot = ApocalypticaRobot(config_path=config_file_abs_path) # Pass absolute path

    # Start the robot's main loop
    robot.run()
