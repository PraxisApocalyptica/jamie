from abc import ABC, abstractmethod
from typing import List, Tuple, Optional, Any

# =====================================================
# Interface 2: Robot Perception (Sensors like Cameras)
# =====================================================

class Perception(ABC):
    """
    Abstract Base Class defining a standard interface for robot perception systems,
    like cameras, lidar, microphones etc., including orienting sensors ("eyes").
    """

    @abstractmethod
    def orient_sensor(self, sensor_id: str, pitch: Optional[float] = None, yaw: Optional[float] = None) -> bool:
        """
        Orients a specific sensor (e.g., a camera identified by 'head_cam').

        Args:
            sensor_id: Identifier for the sensor to orient.
            pitch: Target pitch angle (e.g., degrees, up/down). None means no change.
            yaw: Target yaw angle (e.g., degrees, left/right). None means no change.

        Returns:
            True if the orientation command was successfully initiated, False otherwise.
        """
        pass

    @abstractmethod
    def look_at_point(self, sensor_id: str, x: float, y: float, z: float) -> bool:
        """
        Orients a specific sensor to look towards a point in the world frame.
        Requires knowledge of sensor position and world coordinates.

        Args:
            sensor_id: Identifier for the sensor.
            x, y, z: Coordinates of the target point.

        Returns:
            True if the look command was successfully initiated, False otherwise.
        """
        raise NotImplementedError("look_at_point is not supported by this perception system.")

    @abstractmethod
    def capture_image(self, sensor_id: str) -> Optional[Any]:
        """
        Captures an image from a specified camera sensor.

        Args:
            sensor_id: Identifier for the camera sensor.

        Returns:
            Image data in an implementation-defined format (e.g., numpy array,
            PIL image, file path) or None if capture failed or sensor doesn't exist.
        """
        pass

    @abstractmethod
    def scan_environment(self, sensor_id: str) -> Optional[Any]:
        """
        Performs a scan using a sensor like lidar or depth camera.

        Args:
            sensor_id: Identifier for the scanning sensor.

        Returns:
            Scan data in an implementation-defined format (e.g., point cloud data,
            occupancy grid) or None if scan failed or sensor doesn't exist.
        """
        raise NotImplementedError("scan_environment is not supported by this perception system.")
        # return None

    @abstractmethod
    def get_sensor_orientation(self, sensor_id: str) -> Optional[Tuple[float, float]]:
        """
        Gets the current orientation of a specific sensor.

        Args:
            sensor_id: Identifier for the sensor.

        Returns:
            A tuple representing the orientation (e.g., (pitch_degrees, yaw_degrees))
            or None if unavailable.
        """
        pass

    @abstractmethod
    def list_available_sensors(self) -> List[Tuple[str, str]]:
        """
        Lists the sensors available through this perception interface.

        Returns:
            A list of tuples, where each tuple is (sensor_id: str, sensor_type: str).
            Example: [('head_cam', 'camera'), ('lidar_2d', 'lidar')]
        """
        pass
