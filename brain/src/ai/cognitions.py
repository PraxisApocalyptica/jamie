from typing import Dict, List, Any, Optional
from src.ai.capabilities import Cognition


class Cognitions(Cognition):
    """
    A concrete implementation of the Cognition interface providing basic functionality.
    """

    def provide_normal_reply(self, prompt: str, context: Optional[Any] = None) -> str:
        """Simple implementation of the normal reply method."""
        print(f"--- Executing provide_normal_reply ---")
        print(f"   Prompt: {prompt}")
        print(f"   Context: {context}")
        return f"Normal reply to: '{prompt}'."

    def deliberate_and_decide(self, prompt: str, context: Optional[Any] = None) -> str:
        """Simple implementation of deliberation."""
        print(f"--- Executing deliberate_and_decide ---")
        print(f"   Topic: {prompt}")
        print(f"   Context: {context}")
        return f"Decision reached for: '{prompt}'."

    def plan_action_sequence(self, request: List[Dict[str, Any]], context: Optional[Any] = None) -> str:
        """Simple implementation of action planning."""
        print(f"--- Executing plan_action_sequence ---")
        print(f"   Planning request: {request}")
        print(f"   Context: {context}")
        # Example: Could generate a more detailed plan here
        plan_summary = f"Planned {len(request)} actions based on context: {context}."
        return plan_summary # Return string for demo

    def interpret_sensor_data(self, sensor_id: str, sensor_data: Any) -> str:
        """Simple implementation of sensor data interpretation."""
        print(f"--- Executing interpret_sensor_data ---")
        print(f"   Sensor ID: {sensor_id}")
        print(f"   Sensor Data: {sensor_data}")
        return f"Interpreted data from {sensor_id}: {str(sensor_data)[:50]}..."
