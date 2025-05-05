import asyncio
import io
import logging
import threading

from gtts import gTTS
from pydub import AudioSegment
from pydub.playback import play # Import play function from pydub.playback


class GttsTTSClient:
    """
    A client class for synthesizing text into speech using the gtts library
    (Google Translate TTS) and playing it back, with optional speed adjustment
    using pydub. Requires internet access. Relies on an unofficial Google endpoint.
    Modified for asynchronous usage within an asyncio event loop.
    """

    def __init__(self, lang="en", default_playback_speed=1.0):
        """
        Initializes the GttsTTSClient.

        Args:
            lang (str): Default language code (e.g., "en", "fr", "es").
            default_playback_speed (float): Default multiplier for playback speed.
        """
        self._logger = logging.getLogger(self.__class__.__name__)
        self._default_lang = lang
        self._default_playback_speed = default_playback_speed
        # Capture the loop from the thread that *instantiates* the client.
        # This assumes instantiation happens in the main asyncio thread context.
        try:
            self._main_loop = asyncio.get_running_loop()
        except RuntimeError:
            self._logger.warning("GttsTTSClient instantiated outside a running asyncio loop. "
                                 "Will try to get loop during async call.")
            self._main_loop = None
        self._logger.info(f"GttsTTSClient initialized (lang={lang}, speed={default_playback_speed}x)")

    def _synthesize_and_play_blocking(self, text, lang, playback_speed):
        """
        Internal blocking function containing the core TTS and playback logic.
        Designed to be run in an executor thread.
        """
        self._logger.debug(f"Executing blocking TTS/play for: '{text[:50]}...' "
                          f"(Thread: {threading.current_thread().name})")
        try:
            # 1. Synthesize audio using gtts (network request)
            tts = gTTS(text=text, lang=lang, slow=False)
            audio_stream_original = io.BytesIO()
            tts.write_to_fp(audio_stream_original)
            audio_stream_original.seek(0)

            # 2. Process audio speed using pydub
            audio_segment = AudioSegment.from_file(audio_stream_original, format="mp3")
            if playback_speed != 1.0:
                 # Ensure playback_speed is treated as float for pydub
                 audio_segment = audio_segment.speedup(playback_speed=float(playback_speed))


            # --- 3. Speaking using pydub's blocking playback ---
            self._logger.info(f"🎤 Speaking... (Thread: {threading.current_thread().name})")
            play(audio_segment) # This blocks the *executor* thread, not the main loop
            self._logger.debug(f"Playback finished (Thread: {threading.current_thread().name})")
            return True

        except Exception as e:
            # Log exceptions occurring within the executor thread
            self._logger.error(f"Error during blocking synthesis/playback "
                               f"(Thread: {threading.current_thread().name}): {e}", exc_info=False) # exc_info=False avoids huge logs from executor threads
            return False

    async def synthesize_and_speak(self, text, lang=None, playback_speed=None):
        """
        Asynchronously synthesizes text to speech and plays it back without
        blocking the main asyncio event loop.

        Runs the blocking gTTS/pydub operations in an executor thread.

        Args:
            text (str): The input text to synthesize.
            lang (str, optional): Language code for this request. Defaults to init lang.
            playback_speed (float, optional): Playback speed for this request. Defaults to init speed.

        Returns:
            bool: True if the playback task was successfully scheduled, False on immediate error.
                  Note: The actual playback might still fail later in the background thread.
        """
        if not text:
            self._logger.warning("synthesize_and_speak called with empty text.")
            return False

        current_lang = lang if lang is not None else self._default_lang
        current_playback_speed = playback_speed if playback_speed is not None else self._default_playback_speed

        self._logger.debug(f"Scheduling TTS/play: '{text[:50]}...' (lang={current_lang}, speed={current_playback_speed}x)")

        loop = self._main_loop or asyncio.get_running_loop() # Get loop if not captured at init
        if not loop:
             self._logger.error("Could not obtain asyncio event loop to run TTS task.")
             return False

        try:
            # Schedule the blocking function to run in the default executor
            await loop.run_in_executor(
                None,  # Uses the default ThreadPoolExecutor
                self._synthesize_and_play_blocking,
                text,
                current_lang,
                current_playback_speed
            )
            # Note: run_in_executor returns the result of the blocking function,
            # but we don't strictly need it here unless we want to log success/failure *after* it runs.
            # The main goal is just to schedule it without blocking await.
            self._logger.debug(f"Successfully scheduled TTS/play task for: '{text[:50]}...'")
            return True # Indicates successful scheduling

        except RuntimeError as e:
             # Catch potential errors if the loop is closed during scheduling
             self._logger.error(f"RuntimeError scheduling TTS task (loop likely closing): {e}")
             return False
        except Exception as e:
            # Catch any other unexpected errors during scheduling
            self._logger.error(f"Unexpected error scheduling TTS task: {e}", exc_info=True)
            return False
