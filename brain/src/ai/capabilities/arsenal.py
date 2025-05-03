import inspect
import logging
import abc

from typing import List, Type
from . import CAPABILITIES


class CapabilityArsenal:
    """
    Discovers and describes action-oriented capabilities
    within the 'src.ai.capabilities' package.
    """

    def __init__(self):
        """
        Initializes the arsenal by identifying relevant interface classes.
        """
        self._logger = logging.getLogger(self.__class__.__name__)
        # Use the explicitly imported list from __init__.py
        self._capabilities: List[Type[abc.ABC]] = CAPABILITIES
        self._logger.info("Arsenal initialized.")

    def get_capabilities(self) -> str:
        """
        Generates a formatted string describing the methods available in the
        registered action-oriented capabilities.

        Returns:
            A string detailing the available capabilities, formatted for an LLM prompt,
            or an error message string if no interfaces were found.
        """
        description_parts = []
        self._logger.debug(f"Generating capabilities description from: {[iface.__name__ for iface in self._capabilities]}")

        if not self._capabilities:
             self._logger.warning("No capabilities found or loaded for description generation.")
             return "## Capabilities Summary\n\n[Error: No capabilities found]\n\n---"

        for interface_cls in self._capabilities:
            # Double-check it's a valid ABC subclass (though the import list should ensure this)
            if not inspect.isclass(interface_cls) or not issubclass(interface_cls, abc.ABC):
                 self._logger.warning(f"Skipping invalid entry in INTERFACES_FOR_DESCRIPTION: {interface_cls}")
                 continue

            interface_doc = inspect.getdoc(interface_cls)
            description_parts.append(f"### Interface: {interface_cls.__name__}\n")
            if interface_doc:
                description_parts.append(f"{interface_doc}\n")
            description_parts.append("#### Available Actions:\n")

            # Find all relevant methods (abstract or concrete, non-private)
            methods_to_describe = {}
            for name, method in inspect.getmembers(interface_cls, predicate=inspect.isfunction):
                 # Include abstract methods and non-private concrete methods defined in this class
                 if not name.startswith('_') and (getattr(method, "__isabstractmethod__", False) or method.__qualname__.startswith(interface_cls.__name__)):
                     # Check __qualname__ to avoid inheriting methods from deep in the hierarchy like object.__init__
                     # unless they are explicitly overridden and made abstract/public here.
                     methods_to_describe[name] = method

            if not methods_to_describe:
                description_parts.append("- (No public actions defined in this interface)\n")
                continue

            # Sort methods alphabetically for consistent output
            sorted_method_names = sorted(methods_to_describe.keys())

            for name in sorted_method_names:
                method = methods_to_describe[name]
                try:
                    sig = inspect.signature(method)
                    doc = inspect.getdoc(method)
                    sig_str = f"{name}{sig}"
                    sig_str = sig_str.replace('(self, ', '(').replace('(self)', '()') # Remove self

                    description_parts.append(f"- `{sig_str}`\n")
                    if doc:
                        doc_lines = doc.strip().split('\n')
                        indented_doc = "\n  ".join([f"  {line.strip()}" for line in doc_lines])
                        description_parts.append(f"{indented_doc}\n")
                    else:
                         description_parts.append("  (No specific description provided.)\n") # Add placeholder if no docstring
                    description_parts.append("\n") # Space between methods

                except (ValueError, TypeError) as e:
                    self._logger.warning(f"Could not introspect method {interface_cls.__name__}.{name}: {e}")
                    description_parts.append(f"- {name}(...): [Could not retrieve details]\n\n")

        if not description_parts:
             # This case should be caught earlier, but as a fallback
             return "## Capabilities Summary\n\n[Error: Could not generate description from found interfaces]\n\n---"

        # --- Construct Final Description ---
        # This section tells the AI *how* to think about using the capabilities.
        final_description = "---\n## Capabilities Summary\n\n"
        final_description += (
            "You are an AI controlling a robot. Below are the interfaces and specific actions "
            "you can request to be performed in the physical world. "
            "Your primary way to invoke these actions is by formulating a plan.\n\n"
            "**How to Use Capabilities:**\n"
            "1. Analyze the user's request to determine if physical actions are needed.\n"
            "2. If actions are needed, determine the sequence of steps required using the capabilities listed below.\n"
            "3. **Crucially, you don't execute these directly.** Instead, you must output a plan detailing the sequence of actions.\n"
            "4. This plan should ideally follow the format expected by a planning function (like `plan_action_sequence` from your Cognition abilities):\n"
            "   - A list of steps.\n"
            "   - Each step specifying the `interface` (e.g., 'Movement', 'Perception'), the `action` name (e.g., 'move_forward', 'capture_image'), and necessary `params` (e.g., {'distance': 1.0}, {'sensor_id': 'head_cam'}).\n"
            "5. If you cannot perform a request due to missing capabilities or ambiguity, state that clearly.\n\n"
            "**Available Action Interfaces & Actions:**\n\n"
        )
        final_description += "".join(description_parts)
        final_description += "---\n"

        self._logger.debug(f"Generated capabilities description (length: {len(final_description)} chars).")
        return final_description
