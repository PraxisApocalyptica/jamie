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
            {"action": "move_arm_to_angles", "params": {"angles": 0}}, # Example pre-grasp angles (Joint:Angle)
            {"action": "move_arm_to_angles", "params": {"angles": 50}}, # Example grasp angles
            {"action": "set_gripper", "params": {"state": "close"}}, # Close gripper
            {"action": "wait", "params": {"duration": 0.5}}, # Wait to secure grip
            {"action": "move_arm_to_angles", "params": {"angles": 60}}, # Example lift angles
            {"action": "speak", "params": {"text": "I think I've got it."}},
            {"action": "navigate_to", "params": {"location": {"x": 0.0, "y": 0.0, "yaw": 0.0}}}, # Example return home
            {"action": "move_arm_to_angles", "params": {"angles": 120}}, # Example drop-off angles
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
