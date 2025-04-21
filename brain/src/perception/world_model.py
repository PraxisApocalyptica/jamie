# This module manages the robot's internal representation of its environment,
# its own state, and the objects within the environment.

# It should store:
# - The map (e.g., 2D occupancy grid derived from SLAM data)
# - The robot's current pose (position and orientation) - needs to be updated by SlamLocalization
# - A list or database of detected objects (with class, confidence, pose, mask info) - updated by ObjectProcessor
# - State of direct sensors (bump sensors, force sensor, battery) - updated by communication handlers or hardware interfaces
# - State of actuators (arm joint angles, wheel velocities) - updated based on commanded state or encoder feedback

from typing import Dict, Any, List, Optional

class ObjectInfo:
    """Represents information about a detected object."""
    def __init__(self, id: str, obj_class: str, pose: Dict[str, float], confidence: float, mask=None):
        self.id: str = id
        self.obj_class: str = obj_class
        self.pose: Dict[str, float] = pose # Pose in the robot's world frame (e.g., {"x":..., "y":..., "z":..., "qx":..., ...})
        self.confidence: float = confidence
        self.mask: Any = mask # Raw mask data or processed polygon/bitmap

class RobotState:
    """Represents the robot's own state."""
    def __init__(self):
        self.base_pose: Dict[str, float] = {"x": 0.0, "y": 0.0, "z": 0.0, "roll": 0.0, "pitch": 0.0, "yaw": 0.0} # Robot base pose in world frame
        self.arm_joint_angles: List[float] = [] # Current angles of arm joints
        self.gripper_state: str = "unknown" # "open", "closed", "holding", "error"
        self.current_task: str = "IDLE" # High-level task state
        self.physical_sensors: Dict[int, Any] = {} # Raw sensor readings from Arduino or direct Pi connection

class WorldModel:
    """Manages the robot's internal understanding of the world and itself."""

    def __init__(self):
        self.robot_state = RobotState()
        self._objects: Dict[str, ObjectInfo] = {} # Dictionary of known objects {object_id: ObjectInfo}
        self._map: Any = None # Representation of the environment map (e.g., occupancy grid)

    def update_robot_pose(self, pose: Dict[str, float]):
        """Updates the robot's base pose in the world frame."""
        self.robot_state.base_pose = pose
        # print(f"Robot pose updated: {self.robot_state.base_pose}") # Debugging

    def update_detected_objects(self, objects_list: List[Dict[str, Any]]):
        """Updates the list of known objects based on new detections."""
        # <<<<< IMPLEMENT OBJECT TRACKING AND FUSION >>>>>
        # This is complex! Need to:
        # 1. Match new detections (from Vision app) to existing known objects (based on class, proximity, historical data).
        # 2. Add new objects.
        # 3. Update poses of known objects (e.g., Kalman filter).
        # 4. Handle objects that are no longer detected.
        # Detections come from Vision app, likely in phone's SLAM frame. Need to transform to robot's world frame.
        # Requires calibration data (phone_to_base_transform).
        print(f"TODO: Implement updating world model objects from {len(objects_list)} detections.")
        # Example: Simple replacement (loses history/tracking)
        # self._objects.clear()
        # for i, obj_data in enumerate(objects_list):
        #     obj_id = obj_data.get("id", f"obj_{i}_{int(time.time())}") # Ensure unique ID
        #     # pose_in_robot_frame = transform_phone_slam_to_robot_frame(obj_data.get("pose")) # Need implementation
        #     # self._objects[obj_id] = ObjectInfo(obj_id, obj_data.get("class"), pose_in_robot_frame, obj_data.get("confidence"), obj_data.get("mask"))
        # print(f"World model now has {len(self._objects)} tracked objects (simple update).")


    def get_object_by_id(self, obj_id: str) -> Optional[ObjectInfo]:
        """Retrieves object info by its ID."""
        return self._objects.get(obj_id)

    def get_objects_by_class(self, obj_class: str) -> List[ObjectInfo]:
        """Retrieves a list of objects matching a given class name."""
        return [obj for obj in self._objects.values() if obj.obj_class.lower() == obj_class.lower()]

    # Add methods to update map, sensor state, etc.
    # def update_map(self, map_data: Any): ...
    def update_sensor_data(self, pin: int, value: Any):
        """Updates the state of a physical sensor."""
        self.robot_state.physical_sensors[pin] = value
        # print(f"Sensor {pin} updated to {value}") # Debugging

    def get_sensor_value(self, pin: int) -> Optional[Any]:
        """Gets the current value of a physical sensor."""
        return self.robot_state.physical_sensors.get(pin)

    # Add methods to get map, robot state, etc.
    # def get_map(self): ...
    # def get_robot_pose(self): ...
