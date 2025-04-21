import io
import logging

from google.cloud import texttospeech
from pydub import AudioSegment # Import pydub
from pydub.playback import play # Import play function from pydub.playback

# --- 1. Prerequisites ---
# BEFORE RUNNING THIS CODE:
# a) Install the necessary libraries:
#    pip install google-cloud-texttospeech pydub
# b) Install FFmpeg or Libav:
#    - Ubuntu/Debian: sudo apt install ffmpeg
#    - macOS: brew install ffmpeg
#    - Windows: Download and add ffmpeg to PATH (https://ffmpeg.org/download.html)
# c) Set up a Google Cloud account, project, and enabled Text-to-Speech API.
# d) Create and download a Service Account Key (JSON file) AND/OR use gcloud auth application-default login.
# e) Set the GOOGLE_APPLICATION_CREDENTIALS environment variable OR rely on Application Default Credentials.
# f) Ensure your system has a compatible audio player that pydub can use (e.g., aplay, afplay).
# ------------------------

class GoogleCloudTTSClient:
    """
    A client class for synthesizing text into speech using Google Cloud
    Text-to-Speech and playing it back, with optional speed adjustment,
    using pydub.
    """

    def __init__(self, voice_name="en-US-Wavenet-F", language_code="en-US", default_playback_speed=1.0):
        """
        Initializes the GoogleCloudTTSClient.

        Args:
            voice_name (str): The name of the default voice to use
                              (e.g., "en-US-Wavenet-F").
                              Find valid names in Google Cloud TTS documentation.
            language_code (str): The default language code for the voice
                                 (e.g., "en-US").
            default_playback_speed (float): The default multiplier for playback
                                            speed (1.0 is normal, 1.5 is 50% faster).
        """
        self._logger = logging.getLogger(self.__class__.__name__)

        self._client = texttospeech.TextToSpeechClient()
        self._default_voice_name = voice_name
        self._default_language_code = language_code
        self._default_playback_speed = default_playback_speed


    def synthesize_and_speak(self, text, voice_name=None, language_code=None, playback_speed=None):
        """
        Synthesizes text into speech using Google Cloud Text-to-Speech,
        adjusts speed with pydub, and plays it using pydub's playback function.

        Args:
            text (str): The input text to synthesize.
            voice_name (str, optional): The name of the voice to use for this
                                        specific request. Defaults to the
                                        voice set during initialization.
            language_code (str, optional): The language code for the voice
                                           for this specific request. Defaults
                                           to the language set during
                                           initialization.
            playback_speed (float, optional): Multiplier for playback speed for
                                              this request (1.0 is normal, 1.5 is 50% faster).
                                              Defaults to the speed set during initialization.


        Returns:
            bool: True if playback was attempted successfully, False otherwise.
        """
        # Use default values if not specified for this call
        current_voice_name = voice_name if voice_name is not None else self._default_voice_name
        current_language_code = language_code if language_code is not None else self._default_language_code
        current_playback_speed = playback_speed if playback_speed is not None else self._default_playback_speed


        self._logger.debug(f"Synthesizing: '{text[:50]}...' using voice {current_voice_name} (speed={current_playback_speed}x)...")

        try:
            # 1. Perform the text-to-speech request (Google Cloud API)
            synthesis_input = texttospeech.SynthesisInput(text=text)
            voice_params = texttospeech.VoiceSelectionParams(
                language_code=current_language_code,
                name=current_voice_name,
            )
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3 # Still request MP3
            )

            response = self._client.synthesize_speech(
                input=synthesis_input, voice=voice_params, audio_config=audio_config
            )

            audio_content = response.audio_content

            # 2. Process audio speed using pydub
            # Use io.BytesIO to treat the bytes data as a file in memory for pydub
            audio_stream_original = io.BytesIO(audio_content)

            # Load the audio data from the stream into pydub
            audio_segment = AudioSegment.from_file(audio_stream_original, format="mp3")

            # Apply the speed change if needed
            if current_playback_speed != 1.0:
                audio_segment = audio_segment.speedup(playback_speed=current_playback_speed)


            # --- 3. Speaking audio segment using pydub's playback ---
            self._logger.info("Speaking...")
            # The play function is blocking, it waits until playback is finished
            play(audio_segment)

            return True

        except Exception as e:
            self._logger.critical(f"An error occurred during synthesis, processing, or playback: {e}")
            return False


# --- Example Usage ---
if __name__ == "__main__":
    # --- Important: Ensure Prerequisites are met before running ---
    # Especially setting the GOOGLE_APPLICATION_CREDENTIALS environment variable
    # OR having Application Default Credentials set up via 'gcloud auth application-default login'!
    # Also ensure pydub and ffmpeg/libav are installed and accessible.


    selected_female_voice = "en-US-Neural2-F" # Using a high-quality Neural2 voice
    voice_language_code = "en-US"

    # Create an instance of the client
    # Set a default speed multiplier, e.g., 1.25x (25% faster)
    tts_client = GoogleCloudTTSClient(
        voice_name=selected_female_voice,
        language_code=voice_language_code,
        default_playback_speed=1.25 # Default speed for this client instance
    )

    # Text to synthesize and play
    text_to_speak_1 = "Hello, this is the first test using the Google Cloud client with pydub playback and speed control."
    text_to_speak_2 = "This version does not use the pygame library for playing audio."

    # Use the client to synthesize and play the text
    success_1 = tts_client.synthesize_and_speak(text_to_speak_1)
