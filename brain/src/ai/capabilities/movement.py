from abc import ABC, abstractmethod
from typing import Tuple, Optional, Any

# =====================================================
# Interface 1: Movement
# =====================================================

class Movement(ABC):
    """
    Abstract Base Class defining a standard interface for robot base movement.
    Implementations will handle the specific hardware commands.
    """

    @abstractmethod
    def move_forward(self, distance: float, speed: Optional[float] = None) -> bool:
        """
        Moves the robot's base forward by a specified distance.

        Args:
            distance: The distance to move (units defined by implementation, e.g., meters).
            speed: Optional speed override for this specific movement
                   (units defined by implementation, e.g., m/s or percentage).

        Returns:
            True if the movement command was successfully initiated, False otherwise.
            Note: Completion might be asynchronous; this often just confirms sending the command.
        """
        pass

    @abstractmethod
    def move_backward(self, distance: float, speed: Optional[float] = None) -> bool:
        """
        Moves the robot's base backward by a specified distance.
        (See move_forward for args/return details)
        """
        pass

    @abstractmethod
    def turn_left(self, angle: float, angular_speed: Optional[float] = None) -> bool:
        """
        Turns the robot's base left (counter-clockwise) by a specified angle.

        Args:
            angle: The angle to turn (units defined by implementation, e.g., degrees).
            angular_speed: Optional angular speed override (e.g., deg/s).

        Returns:
            True if the turn command was successfully initiated, False otherwise.
        """
        pass

    @abstractmethod
    def turn_right(self, angle: float, angular_speed: Optional[float] = None) -> bool:
        """
        Turns the robot's base right (clockwise) by a specified angle.
        (See turn_left for args/return details)
        """
        pass

    @abstractmethod
    def stop(self) -> bool:
        """
        Stops all current base movement immediately.

        Returns:
            True if the stop command was successfully sent, False otherwise.
        """
        pass

    @abstractmethod
    def set_default_speed(self, linear_speed: float, angular_speed: float) -> bool:
        """
        Sets the default speeds for subsequent movement commands.

        Args:
            linear_speed: Default speed for forward/backward movement.
            angular_speed: Default speed for turning.

        Returns:
            True if speeds were successfully set, False otherwise.
        """
        pass

    @abstractmethod
    def get_current_pose(self) -> Optional[Tuple[float, float, float]]:
        """
        Returns the current estimated pose of the robot's base.

        Returns:
            A tuple representing the pose (e.g., (x, y, yaw_angle_degrees))
            or None if the pose is unknown or unavailable.
            Coordinate system and units are implementation-dependent.
        """
        pass

    # --- Optional/Advanced Movements (Implementations might raise NotImplementedError) ---

    @abstractmethod
    def move_to_coordinates(self, x: float, y: float, target_angle: Optional[float] = None) -> bool:
        """
        Moves the robot to a specific (x, y) coordinate in its map/world frame.
        Optionally orients the robot to a specific angle upon arrival.
        Requires navigation capabilities in the implementation.

        Args:
            x: Target X coordinate.
            y: Target Y coordinate.
            target_angle: Optional final orientation angle (e.g., degrees).

        Returns:
            True if the navigation goal was accepted, False otherwise.
        """
        # Note: Often implementations will just accept the goal and handle execution
        #       asynchronously. Status checking might need another method.
        raise NotImplementedError("move_to_coordinates is not supported by this movement system.")
