from cryptography.hazmat.primitives.ciphers import algorithms, modes

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
    DEFAULT_MEMBER_COUNT = 3
    MAX_DELIBERATION_ROUNDS = 2
    PROMPTS = {
        "INITIAL_THOUGHTS": textwrap.dedent("""
            You are a member of an AI collective tasked with reaching a decision.
            The topic for deliberation is: {topic}

            Provide your initial thoughts and proposals regarding this topic.
            Focus on your individual perspective and expertise. Be concise.
            State your main idea or suggestion clearly.
            The decision should be precise and less than 250 characters.
            It should not include symbols as it has to be spoken.

            1. Example with only normal response
            capabilities = [provide_normal_reply(input)]
            2. Example which requires only discussion
            capabilities = [deliberate_and_decide(input)]
            3. Example which requires only actions
            capabilities = [plan_action_sequence([{{'interface': 'Movement', 'action': 'move_forward', 'params': {{'distance': 2.0}}}},
                    {{'interface': 'Perception', 'action': 'capture_image', 'params': {{'sensor_id': 'head_cam'}}}}])]
            4. Example with normal response and actions
            capabilities = [provide_normal_reply(input), plan_action_sequence([{{'interface': 'Movement', 'action': 'move_forward', 'params': {{'distance': 2.0}}}},
                    {{'interface': 'Perception', 'action': 'capture_image', 'params': {{'sensor_id': 'head_cam'}}}}])]
            5. Example with discussion and actions
            capabilities = [deliberate_and_decide(input), plan_action_sequence([{{'interface': 'Movement', 'action': 'move_forward', 'params': {{'distance': 2.0}}}},
                    {{'interface': 'Perception', 'action': 'capture_image', 'params': {{'sensor_id': 'head_cam'}}}}])]
            input is the initial text provided by user.
            Response should only contain capabilities and its values like the above example.
            Example: Move forward
            capabilities = [plan_action_sequence([{{'interface': 'Movement', 'action': 'move_forward', 'params': {{'distance': 2.0}}}}]
        """.strip()).strip(),
        "SYNTHESIZE_AND_DECIDE": textwrap.dedent("""
            You are a member of an AI collective.
            The topic under deliberation is: {topic}
            Other members have provided their initial thoughts. Here are their perspectives:

            {individual_responses}

            Synthesize these points, considering the different ideas presented.
            Identify common ground, potential conflicts, or complementary aspects.
            Based on this collective input, propose a single, consolidated collective decision or recommendation.
            State the final decision clearly at the end of your response.
        """).strip()
    }
