import logging
import textwrap
import time

from src.ai.clients.gemini.client import GeminiClient
from src.ai.capabilities.arsenal import CapabilityArsenal
from typing import List, Dict, Any

from src.ai.clients.constants import GEMINI as GeminiConstants, HIVE_MIND


class HiveMind:
    """
    Orchestrates multiple AI members (specifically GeminiClients) to collectively
    deliberate on a given topic or task and arrive at a joint decision.
    """

    def __init__(
        self,
        api_key: str,
        config: Dict[str, Any],
        member_count: int = HIVE_MIND.DEFAULT_MEMBER_COUNT, # Default to 3
        model_name: str = GeminiConstants.MODEL,
        max_output_tokens: int = 250, # Give HiveMind members more room
        max_deliberation_rounds: int = HIVE_MIND.MAX_DELIBERATION_ROUNDS, # How many rounds of "discussion"
    ) -> None:
        """
        Initializes the Collective Mind with multiple AI members.

        Args:
            api_key: Google Gemini API key used for all members.
            config: Base configuration dictionary for the collective. Client-specific
                    configs like 'name' will be added per client.
            member_count: The number of AI members in the collective. Defaults to 3.
            model_name: The Gemini model name for all members.
            max_output_tokens: Max tokens for each client's response during deliberation.
            temperature: Temperature for each client during deliberation.
            max_deliberation_rounds: The maximum number of simulated discussion rounds
                                     (e.g., Brainstorm + Synthesize = 2 rounds).
        """
        self._logger = logging.getLogger(self.__class__.__name__)
        self._api_key: str = api_key
        self.config: Dict[str, Any] = config if config is not None else {}
        self.name: str = self.config.get('collective_name', 'Collective Mind')
        self.purpose: str = self.config.get('collective_purpose', 'reach collective decisions')

        if member_count <= 0:
             raise ValueError("Number of members must be positive.")
        self._member_count = member_count

        self._members: List[GeminiClient] = []
        self._model_name: str = model_name
        self._max_output_tokens: int = max_output_tokens
        self._max_deliberation_rounds: int = max_deliberation_rounds
        capability_arsenal = CapabilityArsenal()
        self.capabilities = capability_arsenal.get_capabilities()

        self._initialize_council()
        self.debate(self.capabilities)

    def _initialize_member(self, client_config):
        return GeminiClient(
            api_key=self._api_key,
            config=client_config,
            speech_assistant=None,
            model_name=self._model_name,
            max_output_tokens=self._max_output_tokens,
        )

    def _initialize_council(self) -> None:
        """Initializes the specified number of council members."""
        self._logger.info(f"[{self.name}] Initializing {self._member_count} Council members...")
        for i in range(self._member_count):
            member_name = f"{self.name} Member {i+1}"

            # Pass relevant config and parameters to the client
            # We don't pass the HiveMind's speech assistant to individual members by default
            # as their internal conversation with the CM shouldn't necessarily be spoken aloud.
            config = self.config.copy()
            config['name'] = member_name # Set the individual client's name
            # You might add client-specific config here if needed

            try:
                member = self._initialize_member(config)
                self._members.append(member)
                self._logger.info(f"[{self.name}] Initialized {member_name} successfully.")
            except Exception as e:
                 self._logger.error(f"[{self.name}] Failed to initialize council member {i+1} ({member_name}): {e}", exc_info=True)
                 # Depending on requirements, you might raise an exception or continue with fewer members
                 raise RuntimeError(f"[{self.name}] Failed to initialize all council members.") from e

        self._logger.info(f"[{self.name}] All {len(self._members)} council members initialized.")

    def debate(self, topic):
        discussion_log: List[Dict[str, str]] = [] # To store the turns of the orchestrated discussion
        initial_responses: Dict[int, str] = {} # Map member index to response
        for i, member in enumerate(self._members):
            member_name = member.name
            self._logger.debug(f"[{self.name}] -> Asking {member_name} for initial thoughts...")
            try:
                response = member.communicate(topic)
                initial_responses[i] = response
                self._logger.debug(f"[{self.name}] <- {member_name} responded: {response[:100]}...")
                discussion_log.append({"member": member_name, "role": "user (CM)", "message": topic}) # CM's prompt to member
                discussion_log.append({"member": member_name, "role": "model", "message": response}) # Member's response
            except Exception as e:
                self._logger.error(f"[{self.name}] Error during Round 1, member {member_name}: {e}", exc_info=True)
                # Decide how to handle failure: skip member, use placeholder, or fail deliberation?
                # For now, let's store an error message and continue, but log it.
                initial_responses[i] = f"Error: Could not get response from {member_name}. {e}"
                discussion_log.append({"member": member_name, "role": "user (CM)", "message": topic})
                discussion_log.append({"member": member_name, "role": "error", "message": str(e)})

        return initial_responses, discussion_log

    def deliberate(self, topic_or_task: str) -> str:
        """
        Orchestrates a discussion among the AI members to reach a collective decision.

        Args:
            topic_or_task: The topic, question, command, or task for the collective
                           to deliberate on.

        Returns:
            A string representing the collective decision or outcome.

        Raises:
            RuntimeError: If deliberation fails at any stage.
        """
        if not self._members:
            raise RuntimeError(f"[{self.name}] No AI members initialized for deliberation.")

        self._logger.info(f"[{self.name}] Starting deliberation on: {topic_or_task}")

        try:
            # --- Round 1: Individual Initial Thoughts ---
            self._logger.info(f"[{self.name}] Round 1: Gathering initial individual thoughts...")
            initial_prompt = HIVE_MIND.PROMPTS["INITIAL_THOUGHTS"].format(topic=topic_or_task)
            initial_responses, discussion_log = self.debate(initial_prompt)


            # Format initial responses for the next round
            formatted_responses = "\n\n".join([
                f"{self._members[i].name}:\n{response}"
                for i, response in initial_responses.items()
            ])
            self._logger.debug(f"[{self.name}] Collected initial responses:\n{formatted_responses[:500]}...")

            if not initial_responses or all(res.startswith("Error:") for res in initial_responses.values()):
                 error_msg = f"[{self.name}] Failed to get any valid initial responses from members."
                 self._logger.error(error_msg)
                 raise RuntimeError(error_msg)


            # --- Round 2: Synthesis and Collective Proposal ---
            self._logger.info(f"[{self.name}] Round 2: Synthesizing and proposing collective decision...")
            synthesis_responses: Dict[int, str] = {}
            synthesis_prompt = HIVE_MIND.PROMPTS["SYNTHESIZE_AND_DECIDE"].format(
                topic=topic_or_task,
                individual_responses=formatted_responses # Include all responses from Round 1
            )

            for i, client in enumerate(self._members):
                member_name = client.name
                self._logger.debug(f"[{self.name}] -> Asking {member_name} to synthesize and propose decision...")
                try:
                    response = client.communicate(synthesis_prompt)
                    synthesis_responses[i] = response
                    self._logger.debug(f"[{self.name}] <- {member_name} responded: {response[:100]}...")
                    discussion_log.append({"member": member_name, "role": "user (CM)", "message": synthesis_prompt})
                    discussion_log.append({"member": member_name, "role": "model", "message": response})
                except Exception as e:
                    self._logger.error(f"[{self.name}] Error during Round 2, client {member_name}: {e}", exc_info=True)
                    synthesis_responses[i] = f"Error: Could not get synthesis response from {member_name}. {e}"
                    discussion_log.append({"member": member_name, "role": "user (CM)", "message": synthesis_prompt})
                    discussion_log.append({"member": member_name, "role": "error", "message": str(e)})

            if not synthesis_responses or all(res.startswith("Error:") for res in synthesis_responses.values()):
                 error_msg = f"[{self.name}] Failed to get any valid synthesis responses from members."
                 self._logger.error(error_msg)
                 raise RuntimeError(error_msg)

            # We will take the synthesis response from the first client as the collective decision.
            # A more complex approach would involve analyzing all synthesis responses.
            final_decision_member_index = 0 # Could be made configurable or based on response quality
            final_decision_text = synthesis_responses.get(final_decision_member_index, "Could not retrieve final decision.")

            if final_decision_text.startswith("Error:"):
                 self._logger.warning(f"[{self.name}] Final decision comes from a client that errored in synthesis round.")
                 # Fallback to a simpler combined response if the designated client failed
                 combined_synthesis_text = "\n\n".join([f"{self._members[i].name}'s synthesis:\n{res}" for i, res in synthesis_responses.items()])
                 final_decision_text = f"Deliberation complete. Multiple synthesis responses received. One member reported an error. Here are the synthesis results:\n\n{combined_synthesis_text}"
            else:
                 pass

            self._logger.info(f"[{self.name}] Deliberation complete. Final decision from {self._members[final_decision_member_index].name}: {final_decision_text}...")

            # Log the full discussion internally if needed for debugging/analysis
            self._log_discussion(discussion_log) # Implement a method to log this list nicely


            return final_decision_text

        except Exception as e:
            self._logger.critical(f"[{self.name}] An unexpected error occurred during deliberation: {type(e).__name__}: {e}", exc_info=True)
            # Attempt to return an error message or default if possible
            error_response = f"[{self.name}] Deliberation failed due to an internal error: {e}"
            raise RuntimeError(error_response) from e # Re-raise the exception


    def shutdown(self) -> None:
        """
        Shuts down all managed AI members, ensuring their current session history
        is saved as memory fragments.
        """
        self._logger.info(f"[{self.name}] Shutting down all AI members...")
        for i, client in enumerate(self._members):
            member_name = client.name
            self._logger.debug(f"[{self.name}] Shutting down {member_name}...")

        self._members = [] # Clear the list of members
        self._logger.info(f"[{self.name}] All members shut down.")

    # Helper method (optional) to log the detailed discussion turns
    def _log_discussion(self, discussion_log: List[Dict[str, str]]):
        self._logger.debug(f"[{self.name}] --- Full Deliberation Log ---")
        for turn in discussion_log:
            member = turn.get('member', 'CM')
            role = turn.get('role', 'Unknown')
            message = textwrap.shorten(turn.get('message', ''), width=200, placeholder='...')
            self._logger.debug(f"[{self.name}]   {member} ({role}): {message}")
        self._logger.debug(f"[{self.name}] --- End Deliberation Log ---")
