import io
import logging

from gtts import gTTS
from pydub import AudioSegment
from pydub.playback import play # Import play function from pydub.playback

# --- 1. Prerequisites ---
# BEFORE RUNNING THIS CODE:
# a) Install the necessary libraries:
#    pip install gtts pydub
# b) Install FFmpeg or Libav:
#    - Ubuntu/Debian: sudo apt install ffmpeg
#    - macOS: brew install ffmpeg
#    - Windows: Download and add ffmpeg to PATH (https://ffmpeg.org/download.html)
# c) Requires an active internet connection for gtts synthesis.
# d) Ensure your system has a compatible audio player that pydub can use (e.g., aplay, afplay).
# ------------------------

class GttsTTSClient:
    """
    A client class for synthesizing text into speech using the gtts library
    (Google Translate TTS) and playing it back, with optional speed adjustment
    using pydub. Requires internet access. Relies on an unofficial Google endpoint.
    """

    def __init__(self, lang="en", default_playback_speed=1.0):
        """
        Initializes the GttsTTSClient.

        Args:
            lang (str): The default language code to use (e.g., "en", "fr", "es").
                        Find valid codes from Google Translate's supported languages.
            default_playback_speed (float): The default multiplier for playback
                                            speed (1.0 is normal, 1.5 is 50% faster).
        """
        self._logger = logging.getLogger(self.__class__.__name__)
        self._default_lang = lang
        self._default_playback_speed = default_playback_speed

    def synthesize_and_speak(self, text, lang=None, playback_speed=None):
        """
        Synthesizes text into speech using gtts, adjusts speed with pydub,
        and plays it using pydub's playback function.

        Args:
            text (str): The input text to synthesize.
            lang (str, optional): The language code to use for this specific
                                  request. Defaults to the language set during
                                  initialization.
            playback_speed (float, optional): Multiplier for playback speed for
                                              this request (1.0 is normal, 1.5 is 50% faster).
                                              Defaults to the speed set during initialization.

        Returns:
            bool: True if playback was attempted successfully, False otherwise.
        """
        # Use default values if not specified for this call
        current_lang = lang if lang is not None else self._default_lang
        current_playback_speed = playback_speed if playback_speed is not None else self._default_playback_speed

        self._logger.debug(f"Synthesizing: '{text[:50]}...' using gtts (lang={current_lang}, speed={current_playback_speed}x)...")

        try:
            # 1. Synthesize audio using gtts (network request)
            # Set slow=False for normal speed before any modification
            tts = gTTS(text=text, lang=current_lang, slow=False)

            # Write the audio data to an in-memory stream
            audio_stream_original = io.BytesIO()
            tts.write_to_fp(audio_stream_original)
            audio_stream_original.seek(0) # Rewind for reading

            # 2. Process audio speed using pydub
            # Load the audio data from the stream into pydub
            audio_segment = AudioSegment.from_file(audio_stream_original, format="mp3")

            # Apply the speed change
            # Using speedup method - it handles tempo and pitch adjustment
            # A speed of 1.0 means no change
            if current_playback_speed != 1.0:
                audio_segment = audio_segment.speedup(playback_speed=current_playback_speed)


            # --- 3. Speaking using pydub's playback ---
            self._logger.info("🎤 Speaking...")
            # The play function is blocking, it waits until playback is finished
            play(audio_segment)

            return True

        except Exception as e:
            self._logger.critical(f"An error occurred during synthesis, processing, or playback: {e}")
            return False


# --- Example Usage (Gtts with Speed Control using pydub playback) ---
if __name__ == "__main__":

    # Create an instance of the client
    # You can set the default language and a default speed multiplier here
    gtts_tts_client = GttsTTSClient(lang="en", default_playback_speed=1.2)

    # Text to speak
    text_to_speak_1 = "Hello, this is a test using the gtts library."

    # Use the client to synthesize and play the text
    success_1 = gtts_tts_client.synthesize_and_speak(text_to_speak_1)
