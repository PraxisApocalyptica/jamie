from cryptography.hazmat.primitives.ciphers import algorithms, modes


class GEMINI:

    MODEL: str = "gemini-2.0-flash"
    HISTORY = [
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

    NAME = "memory.json.enc"
    TYPE = "memories"

    HEADER = "--- Previous Conversation History ---"
    TURN_MARKER = "[{role}]: " # {role} placeholder for 'User' or 'Model'

    INITIAL_CONTEXT_HEADER = "--- Context ---"
    INITIAL_INSTRUCTIONS_HEADER = "--- Instructions ---"
    INITIAL_START_MARKER = "--- Start ---"

class COMMANDS:
    EXIT = 'exit'
    CLEAR_HISTORY = 'clear history'
    SHOW_HISTORY = 'show history'
