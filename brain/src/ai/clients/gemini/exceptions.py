# --- Exceptions ---
class GeminiAPIError(Exception):
    """Custom exception for errors during Gemini API interaction."""
    pass

class GeminiResponseParsingError(GeminiAPIError):
    """Custom exception for errors parsing the Gemini API response."""
    pass

class GeminiBlockedError(GeminiAPIError):
    """Custom exception when the Gemini API blocks a prompt or response."""
    pass