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
