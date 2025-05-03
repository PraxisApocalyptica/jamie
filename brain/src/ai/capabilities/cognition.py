from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any

# =====================================================
# Interface 3: Cognition / Thought Process
# =====================================================

ActionDetail = Dict[str, Any]
ActionResult = Dict[str, Any] 

class Cognition(ABC):
    """
    Abstract Base Class defining different modes of thinking, response generation,
    and action planning for AI.
    """

    @abstractmethod
    def provide_normal_reply(self, prompt: str, context: Optional[Any] = None) -> str:
        """
        Generates a direct, conversational response without deep analysis or planning.
        Suitable for simple questions or statements.

        Args:
            prompt: The user input or stimulus requiring a response.
            context: Optional additional context (e.g., recent history).

        Returns:
            A string containing the AI's response.
        """
        pass

    @abstractmethod
    def deliberate_and_decide(self, topic: str, context: Optional[Any] = None) -> str:
        """
        Performs deeper thinking, analysis, or deliberation on a complex topic or task.
        This might involve internal simulations, multi-step reasoning, or consulting
        knowledge bases (like the HiveMind concept).

        Args:
            topic: The complex question, task, or scenario to deliberate on.
            context: Optional additional context.

        Returns:
            A string summarizing the outcome of the deliberation or the final decision.
        """
        raise NotImplementedError("Deep deliberation is not supported by this cognitive module.")

    @abstractmethod
    def plan_action_sequence(self, request: List[ActionDetail], context: Optional[Any] = None) -> None:
        """
        Analyzes a user request and breaks it down into a sequence of concrete actions
        to be executed using the Movement and Perception interfaces.

        Args:
            request: The user's command or goal that requires physical action.
            Example: [{'interface': 'Movement', 'action': 'move_forward', 'params': {'distance': 2.0}},
                      {'interface': 'Perception', 'action': 'capture_image', 'params': {'sensor_id': 'head_cam'}}]
            context: Optional additional context (e.g., current pose, known environment).

        Returns:
            None.
        """
        pass

    @abstractmethod
    def interpret_sensor_data(self, sensor_id: str, sensor_data: Any) -> str:
        """
        Analyzes data from a sensor (e.g., an image, a scan) and provides a
        textual interpretation or extracts relevant information.

        Args:
            sensor_id: The ID of the sensor providing the data.
            sensor_data: The raw data from the sensor (format depends on sensor type).

        Returns:
            A string describing the interpretation (e.g., "I see a red ball.",
            "Obstacle detected 1 meter ahead.").
        """
        raise NotImplementedError("Sensor data interpretation is not supported.")
