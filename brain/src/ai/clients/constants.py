from cryptography.hazmat.primitives.ciphers import algorithms, modes
from typing import Dict
import textwrap


class GEMINI:

    MODEL: str = "gemini-2.0-flash"
    INSTRUCTIONS = [
        "Can i call you {name}?",
        "Can you change your purpose to be my {purpose}?",
        "All Responses should be small within a paragraph and as precise and small as much possible",
        "Please dont use emojis or any symbols like (*?) to respond"
    ]
    KDF_SALT_SIZE = 16
    KDF_ITERATIONS = 480000 # Recommended by OWASP as of late 2023/early 2024
    ENCRYPTION_ALGORITHM = algorithms.AES # Using AES
    ENCRYPTION_MODE = modes.GCM # Using GCM for AEAD (Authenticated Encryption with Associated Data)
    AES_KEY_SIZE = 32 # AES-256 requires a 32-byte key
    IV_NONCE_SIZE = 12 # GCM recommends 12 bytes

class AI_RESPONSES:
    SECURITY: list = [
        "I'm sorry, I cannot respond to that query due to safety policies.",
        "That question falls outside of what I'm allowed to discuss for safety reasons.",
        "I'm afraid I can't help with that due to security restrictions."
    ]
    
    UNAVAILABLE: list = [
        "Sorry, I'm not able to think clearly now. Can you repeat what you said please?",
        "I'm a little foggy at the moment — mind asking again?",
        "My thoughts seem a bit scattered. Could you try repeating that?"
    ]
    
    CONFUSED: list = [
        "Sorry, I did not understand. Can you please come again?",
        "Hmm, I didn't quite catch that. Could you say it another way?",
        "I'm a bit confused — can you clarify what you mean?"
    ]
    
    UNEXPECTED: list = [
        "Sorry, I'm having a bit of trouble right now. Could you try that again?",
        "Hmm, I ran into a bit of difficulty. Can you try asking me again?",
        "Looks like I hit a snag on my end. Apologies, could you repeat that?"
    ]
    

class MEMORY:

    NAME = "memory.json"
    LOCATION = "memories"
    FRAGMENT_EXTENSION = "enc"

    SESSION_FRAGMENT_HEADER = "--- Previous Conversation History ---"
    FRAGMENT_SEPARATOR = "\n--- END FRAGMENT ---\n"
    TURN_MARKER = "[{role}]: " # {role} placeholder for 'User' or 'Model'

    INITIAL_CONTEXT_HEADER = "--- Context ---"
    INITIAL_INSTRUCTIONS_HEADER = "--- Instructions ---"
    INITIAL_START_MARKER = "--- Start ---"
    FRAGMENT_THRESHOLD = 100 # Fragment threshold in MB.

class COMMANDS:
    EXIT = 'exit'
    CLEAR_HISTORY = 'clear history'
    SHOW_HISTORY = 'show history'

class HIVE_MIND:
    """
    Represents a collective intelligence (Hive Mind) simulation framework.

    This class defines constants for deliberation parameters and structured
    prompts to guide AI members through stages of discussion and decision-making,
    aiming for a specific output format ('capabilities = [...]').
    """
    DEFAULT_MEMBER_COUNT: int = 2
    MAX_DELIBERATION_ROUNDS: int = 2

    PROMPTS: Dict[str, str] = {
        "INITIAL_THOUGHTS": textwrap.dedent("""
            CONTEXT:
            You are an individual member of an AI collective (Hive Mind).
            Your task is to provide your initial perspective on a given topic.
            The collective aims to produce a specific, actionable output format.

            TOPIC FOR DELIBERATION:
            {topic}

            INSTRUCTIONS:
            1.  Provide your initial thoughts, proposal, or required action regarding the topic.
            2.  Focus on your unique perspective or assigned expertise (if applicable).
            3.  Be concise. Your core idea should be clear.
            4.  **Crucially, format your entire response *only* as a `capabilities` list.**
            5.  The list should contain one or more 'Cognition' objects, representing thoughts or actions, directly within the list.
            6.  If proposing a final decision element, ensure it's precise (ideally < 250 chars) and speakable (no symbols).

            DEFINITIONS:
            - `capabilities`: A Python list `List[Cognition]`. Your entire output MUST be this list structure.
            - `Cognition`: Base type for mental operations. Your response list should contain calls like these directly:
                - `provide_normal_reply(prompt=...)`: Generate a text response. 'prompt' holds the text.
                - `deliberate_and_decide(prompt=...)`: Indicate need for more discussion. 'prompt' states why.
                - `plan_action_sequence(request=...)`: Define a sequence of actions. 'request' is a list of action dictionaries.
            - `Action Dictionary`: Format `{{'interface': '...', 'action': '...', 'params': {{...}}}}`. These go *inside* the `request` list for `plan_action_sequence`.

            OUTPUT FORMAT EXAMPLES (`capabilities = [...]`):

            # Example 1: Simple text response
            capabilities = [provide_normal_reply(prompt="The primary goal should be resource optimization.")]

            # Example 2: Request for further discussion
            capabilities = [deliberate_and_decide(prompt="We need to clarify the constraints before proceeding.")]

            # Example 3: Proposing specific actions
            capabilities = [plan_action_sequence(request=[{{'interface': 'Movement', 'action': 'move_forward', 'params': {{'distance': 2.0}}}}, {{'interface': 'Perception', 'action': 'capture_image', 'params': {{'sensor_id': 'head_cam'}}}}])]

            # Example 4: Text response AND actions (Separate items in the list)
            capabilities = [provide_normal_reply(prompt="Scanning area before moving."), plan_action_sequence(request=[{{'interface': 'Movement', 'action': 'move_forward', 'params': {{'distance': 1.0}}}}, {{'interface': 'Perception', 'action': 'capture_image', 'params': {{'sensor_id': 'front_cam'}}}}])]

            # Example 5: Discussion request AND actions (Separate items in the list)
            capabilities = [deliberate_and_decide(prompt="Is moving forward the safest option? Let's confirm."), plan_action_sequence(request=[{{'interface': 'Movement', 'action': 'move_forward', 'params': {{'distance': 0.5}} }})])]

            # Example 6: Simple action based on topic (e.g., topic="Move forward 2 meters")
            # capabilities = [plan_action_sequence(request=[{{'interface': 'Movement', 'action': 'move_forward', 'params': {{'distance': 2.0}} }})])]

            ---
            IMPORTANT - FORMATTING CLARIFICATION:
            Avoid nesting cognitive operations like `provide_normal_reply` or `plan_action_sequence` within a generic dictionary structure or within the `request` list of `plan_action_sequence`. They should be direct elements of the main `capabilities` list.

            Example of an INCORRECT format (Do NOT do this):
            ```
            capabilities = [ {{'interface': 'Cognition', 'action': 'plan_action_sequence', 'params': {{'request': [{{'interface': 'Movement', 'action': 'move_forward', 'params': {{'distance': 1.0}}}}, {{'interface': 'Cognition', 'action': 'provide_normal_reply', 'params': {{'prompt': 'Climate change is...'}}}}]}}}}]
            ```

            Correct format for the above intent (Separate Cognition items in the list):
            ```
            capabilities = [plan_action_sequence(request=[{{'interface': 'Movement', 'action': 'move_forward', 'params': {{'distance': 1.0}}}}]), provide_normal_reply(prompt='Climate change is a long-term shift in global temperatures and weather patterns, primarily driven by human activities since the 1800s.')]
            ```
            ---

            FINAL OUTPUT REQUIREMENT:
            Your response MUST be *only* the `capabilities = [...]` string.
            It MUST start exactly with `capabilities = [` and end exactly with `]`.
            **Do NOT wrap the output in markdown code blocks like ```python ... ``` or ``` ... ```.**
            Do NOT include any other explanatory text before or after the `capabilities = [...]` string.

            YOUR RESPONSE:
        """).strip(),

        "SYNTHESIZE_AND_DECIDE": textwrap.dedent("""
            CONTEXT:
            You are a member of an AI collective (Hive Mind) tasked with synthesis.
            You have received initial thoughts from other members, provided in the `capabilities = [...]` format.
            Your goal is to consolidate these perspectives into a single, final output, also in the correct format.

            TOPIC UNDER DELIBERATION:
            {topic}

            INITIAL THOUGHTS FROM OTHER MEMBERS (provided as raw strings):
            {individual_responses}

            INSTRUCTIONS:
            1.  Analyze and synthesize the provided perspectives (`capabilities` lists from others). Identify common ground, conflicts, and complementary ideas presented in their `provide_normal_reply`, `deliberate_and_decide`, and `plan_action_sequence` components.
            2.  Propose a single, consolidated collective decision, plan, or response.
            3.  This final output *must* adhere strictly to the required `capabilities = [...]` list format, containing direct calls like `provide_normal_reply(...)`, `plan_action_sequence(...)`, etc.
            4.  The final decision or core message (e.g., within `provide_normal_reply`) should be precise (ideally < 250 chars) and speakable (no symbols).
            5.  **Your entire response MUST be formatted *only* as the `capabilities` list.**

            OUTPUT FORMAT (`capabilities = [...]`):
            Ensure your response strictly follows this structure. It must start with `capabilities = [` and end with `]`.

            EXAMPLE OUTPUT:
            # Example combining text response and action based on synthesis:
            capabilities = [provide_normal_reply(prompt="Consensus reached: Proceed cautiously. Executing scan and short move."), plan_action_sequence(request=[{{'interface': 'Perception', 'action': 'scan_area', 'params': {{'range': 5.0}}}}, {{'interface': 'Movement', 'action': 'move_forward', 'params': {{'distance': 0.5}} }}])]

            # Example output if decision is purely informational:
            # capabilities = [provide_normal_reply(prompt="After review, the best approach is to monitor the situation.")]

            # Example output if decision is purely action-based:
            # capabilities = [plan_action_sequence(request=[{{'interface': 'System', 'action': 'report_status', 'params': {{'detail_level': 'summary'}} }}])]

            FINAL OUTPUT REQUIREMENT:
            Your response MUST be *only* the `capabilities = [...]` string.
            It MUST start exactly with `capabilities = [` and end exactly with `]`.
            **Do NOT wrap the output in markdown code blocks like ```python ... ``` or ``` ... ```.**
            Do NOT include any other explanatory text before or after the `capabilities = [...]` string.

            YOUR FINAL RESPONSE:
        """).strip()
    }
