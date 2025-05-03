import logging
import textwrap
import asyncio
from typing import List, Dict, Any, Tuple

# Assuming GeminiClient and CapabilityArsenal are correctly located
from src.ai.clients.gemini.client import GeminiClient
from src.ai.capabilities.arsenal import CapabilityArsenal
from src.ai.clients.constants import GEMINI as GeminiConstants, HIVE_MIND

class HiveMind:
    """
    Orchestrates multiple AI members (specifically GeminiClients) to collectively
    deliberate on a given topic or task and arrive at a joint decision using
    asynchronous communication.
    """

    def __init__(
        self,
        api_key: str,
        config: Dict[str, Any],
        member_count: int = HIVE_MIND.DEFAULT_MEMBER_COUNT, # Default to 3
        model_name: str = GeminiConstants.MODEL,
        max_output_tokens: int = 250, # Give HiveMind members more room
        max_deliberation_rounds: int = HIVE_MIND.MAX_DELIBERATION_ROUNDS, # How many rounds of "discussion" - Note: Currently hardcoded to 2 rounds
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
            max_deliberation_rounds: The maximum number of simulated discussion rounds.
                                     (Currently deliberation is fixed at 2 rounds).
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
        self._max_deliberation_rounds: int = max_deliberation_rounds # Store but not actively used for round count limit in current structure

        # CapabilityArsenal loading is synchronous, okay here
        capability_arsenal = CapabilityArsenal()
        self.capabilities = capability_arsenal.get_capabilities()

        # Initialization is synchronous
        self._initialize_council()

        # Removed self.debate(self.capabilities) from __init__ as debate is now async

    def _initialize_member(self, client_config):
        # Assuming GeminiClient init is synchronous
        return GeminiClient(
            api_key=self._api_key,
            config=client_config,
            model_name=self._model_name,
            max_output_tokens=self._max_output_tokens,
        )

    def _initialize_council(self) -> None:
        """Initializes the specified number of council members."""
        self._logger.info(f"[{self.name}] Initializing {self._member_count} Council members...")
        for i in range(self._member_count):
            member_name = f"{self.name} Member {i+1}"
            config = self.config.copy()
            config['name'] = member_name

            try:
                member = self._initialize_member(config)
                self._members.append(member)
                self._logger.info(f"[{self.name}] Initialized {member_name} successfully.")
            except Exception as e:
                 self._logger.error(f"[{self.name}] Failed to initialize council member {i+1} ({member_name}): {e}", exc_info=True)
                 raise RuntimeError(f"[{self.name}] Failed to initialize all council members.") from e

        self._logger.info(f"[{self.name}] All {len(self._members)} council members initialized.")

    async def debate(self, topic: str) -> Tuple[Dict[int, str], List[Dict[str, str]]]:
        """
        Asynchronously queries all members on a given topic and collects responses.

        Args:
            topic: The prompt or question to pose to each member.

        Returns:
            A tuple containing:
            - A dictionary mapping member index to their response string (or error message).
            - A list of discussion log entries for this debate round.

        Raises:
            RuntimeError: If the underlying client communication fails unexpectedly
                          beyond individual member errors (which are logged and returned).
        """
        discussion_log: List[Dict[str, str]] = []
        responses: Dict[int, str] = {}

        async def _fetch_response(index: int, member: GeminiClient, prompt: str):
            """Helper coroutine to communicate with a single member and handle errors."""
            member_name = member.name
            self._logger.debug(f"[{self.name}] -> Asking {member_name} about '{prompt[:50]}...' (async)")
            log_entry_prompt = {"member": member_name, "role": "user (CM)", "message": prompt}
            try:
                # *** CRITICAL ASSUMPTION: member.communicate is an async method ***
                # If GeminiClient.communicate is synchronous, you'll need to wrap it:
                # loop = asyncio.get_running_loop()
                # response = await loop.run_in_executor(None, member.communicate, prompt)
                response = await member.communicate(prompt) # Await the async call

                self._logger.debug(f"[{self.name}] <- {member_name} responded (async): {response[:100]}...")
                log_entry_response = {"member": member_name, "role": "model", "message": response}
                return index, response, log_entry_prompt, log_entry_response
            except Exception as e:
                self._logger.error(f"[{self.name}] Error during async debate for member {member_name}: {e}", exc_info=True)
                error_message = f"Error: Could not get response from {member_name}. Details: {e}"
                log_entry_error = {"member": member_name, "role": "error", "message": str(e)}
                # Return index, error message string, prompt log, error log
                return index, error_message, log_entry_prompt, log_entry_error

        # Create communication tasks for all members
        tasks = [
            _fetch_response(i, member, topic)
            for i, member in enumerate(self._members)
        ]

        # Run tasks concurrently and gather results
        # results will be a list of tuples: (index, response_or_error_msg, log_prompt, log_response_or_error)
        results = await asyncio.gather(*tasks)

        # Process results and build the final dictionary and log
        for index, response_or_error, log_prompt, log_response_or_error in results:
            responses[index] = response_or_error
            discussion_log.append(log_prompt)
            discussion_log.append(log_response_or_error)

        return responses, discussion_log

    async def deliberate(self, topic_or_task: str) -> str:
        """
        Orchestrates an asynchronous discussion among the AI members to reach a
        collective decision.

        Args:
            topic_or_task: The topic, question, command, or task for the collective
                           to deliberate on.

        Returns:
            A string representing the collective decision or outcome.

        Raises:
            RuntimeError: If deliberation fails significantly (e.g., no members respond).
        """
        if not self._members:
            raise RuntimeError(f"[{self.name}] No AI members initialized for deliberation.")

        self._logger.info(f"[{self.name}] Starting deliberation on: {topic_or_task}")
        full_discussion_log: List[Dict[str, str]] = []

        try:
            # --- Round 1: Individual Initial Thoughts (Async) ---
            self._logger.info(f"[{self.name}] Round 1: Gathering initial individual thoughts...")
            initial_prompt = HIVE_MIND.PROMPTS["INITIAL_THOUGHTS"].format(topic=topic_or_task)
            # Use the async debate method
            initial_responses, round1_log = await self.debate(initial_prompt)
            full_discussion_log.extend(round1_log)

            # Format initial responses for the next round
            formatted_responses = "\n\n".join([
                f"{self._members[i].name}:\n{response}"
                for i, response in initial_responses.items()
                # Avoid including error messages directly in the synthesis prompt if needed,
                # or clearly label them. Here we include them as is.
            ])
            self._logger.debug(f"[{self.name}] Collected initial responses:\n{formatted_responses[:500]}...")

            if not initial_responses or all(res.startswith("Error:") for res in initial_responses.values()):
                 error_msg = f"[{self.name}] Failed to get any valid initial responses from members."
                 self._logger.error(error_msg)
                 # Potentially return early or raise, depending on desired robustness
                 # For now, we'll proceed to synthesis but log the error.
                 # raise RuntimeError(error_msg) # Option to fail fast


            # --- Round 2: Synthesis and Collective Proposal (Async) ---
            self._logger.info(f"[{self.name}] Round 2: Synthesizing and proposing collective decision...")
            synthesis_prompt = HIVE_MIND.PROMPTS["SYNTHESIZE_AND_DECIDE"].format(
                topic=topic_or_task,
                individual_responses=formatted_responses # Include all responses (incl. errors) from Round 1
            )

            # Reuse the async debate method for synthesis
            synthesis_responses, round2_log = await self.debate(synthesis_prompt)
            full_discussion_log.extend(round2_log)


            if not synthesis_responses or all(res.startswith("Error:") for res in synthesis_responses.values()):
                 error_msg = f"[{self.name}] Failed to get any valid synthesis responses from members."
                 self._logger.error(error_msg)
                 # Decide on fallback - maybe return the formatted initial thoughts?
                 fallback_decision = f"[{self.name}] Deliberation failed during synthesis. Initial thoughts were:\n{formatted_responses}"
                 self._log_discussion(full_discussion_log) # Log what happened
                 return fallback_decision # Return a fallback instead of raising


            # --- Final Decision Selection ---
            # Simple strategy: take the synthesis response from the first member.
            # Could be made more robust (e.g., check for errors, majority vote, etc.)
            final_decision_member_index = 0
            final_decision_text = synthesis_responses.get(final_decision_member_index, "Error: Could not retrieve final decision.")
            final_decision_provider_name = self._members[final_decision_member_index].name

            if final_decision_text.startswith("Error:"):
                 self._logger.warning(f"[{self.name}] Designated member {final_decision_provider_name} failed synthesis. Attempting fallback.")
                 # Fallback: Find the first non-error synthesis response
                 fallback_found = False
                 for idx, response in synthesis_responses.items():
                     if not response.startswith("Error:"):
                         final_decision_text = response
                         final_decision_provider_name = self._members[idx].name
                         self._logger.info(f"[{self.name}] Using fallback synthesis from {final_decision_provider_name}.")
                         fallback_found = True
                         break
                 if not fallback_found:
                     self._logger.error(f"[{self.name}] All members failed synthesis. No final decision possible.")
                     combined_synthesis_text = "\n\n".join([f"{self._members[i].name}'s synthesis attempt:\n{res}" for i, res in synthesis_responses.items()])
                     final_decision_text = f"[{self.name}] Deliberation failed: All members encountered errors during synthesis.\n\n{combined_synthesis_text}"
            else:
                 self._logger.info(f"[{self.name}] Deliberation complete. Final decision provided by {final_decision_provider_name}.")


            self._logger.debug(f"[{self.name}] Final Decision: {final_decision_text[:200]}...")
            self._log_discussion(full_discussion_log) # Log the full discussion


            return final_decision_text

        except Exception as e:
            # Catch unexpected errors during the orchestration logic itself
            self._logger.critical(f"[{self.name}] An unexpected error occurred during deliberation orchestration: {type(e).__name__}: {e}", exc_info=True)
            error_response = f"[{self.name}] Deliberation failed due to an internal orchestration error: {e}"
            # Log whatever discussion happened before the crash
            self._log_discussion(full_discussion_log)
            # Re-raise or return error message - raising is often better for signalling failure
            raise RuntimeError(error_response) from e


    def shutdown(self) -> None:
        """
        Shuts down all managed AI members.
        (Note: Assumes GeminiClient doesn't require explicit async shutdown)
        """
        self._logger.info(f"[{self.name}] Shutting down all AI members...")
        # If GeminiClient had async cleanup (e.g., closing sessions),
        # this would need to be an async method using asyncio.gather
        for i, client in enumerate(self._members):
            member_name = client.name
            self._logger.debug(f"[{self.name}] Shutting down {member_name}...")
            # Add any client-specific shutdown logic here if needed
            # client.close() or similar

        self._members = [] # Clear the list of members
        self._logger.info(f"[{self.name}] All members shut down.")

    def _log_discussion(self, discussion_log: List[Dict[str, str]]):
        """Helper method to log the detailed discussion turns."""
        self._logger.debug(f"[{self.name}] --- Full Deliberation Log ---")
        if not discussion_log:
            self._logger.debug(f"[{self.name}]   (No discussion log entries)")
            return
        for turn in discussion_log:
            member = turn.get('member', 'Unknown Member')
            role = turn.get('role', 'Unknown Role')
            message = turn.get('message', '')
            # Shorten potentially long messages/prompts for debug log clarity
            short_message = textwrap.shorten(message.replace('\n', ' '), width=150, placeholder='...')
            self._logger.debug(f"[{self.name}]   {member} ({role}): {short_message}")
        self._logger.debug(f"[{self.name}] --- End Deliberation Log ---")
