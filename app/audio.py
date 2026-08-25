import audioop
import base64
import logging
import wave
import os
import datetime

logger = logging.getLogger("VoiceAgent")

class CallAudioRecorder:
    def __init__(self, phone: str = "081-234-5678", caller_name: str = "Vera Sun"):
        self.phone = phone or "081-234-5678"
        self.caller_name = caller_name or "Vera Sun"
        self.sample_rate = 16000
        clean_phone = "".join(c for c in self.phone if c.isalnum() or c == '-')
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filename = f"call_{clean_phone}_{timestamp}.wav"
        self.filepath = os.path.join("recordings", self.filename)
        self.frames = bytearray()
        self.rate_state = None
        os.makedirs("recordings", exist_ok=True)

    def add_user_audio(self, pcm_16k_b64: str):
        """Adds user's incoming mic 16kHz PCM audio bytes."""
        try:
            pcm_bytes = base64.b64decode(pcm_16k_b64)
            if pcm_bytes:
                self.frames.extend(pcm_bytes)
        except Exception as e:
            logger.warning(f"Error adding user audio to recorder: {e}")

    def add_bot_audio(self, pcm_24k_b64: str):
        """Downsamples bot's 24kHz PCM audio response to 16kHz PCM and adds to recording."""
        try:
            pcm_24k = base64.b64decode(pcm_24k_b64)
            if pcm_24k:
                pcm_16k, self.rate_state = audioop.ratecv(
                    pcm_24k, 2, 1, 24000, 16000, self.rate_state
                )
                self.frames.extend(pcm_16k)
        except Exception as e:
            logger.warning(f"Error adding bot audio to recorder: {e}")

    def save(self) -> str:
        """Saves accumulated PCM frames into a standard WAV file."""
        if not self.frames or len(self.frames) < 1000:
            return None
        try:
            with wave.open(self.filepath, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2) # 16-bit PCM
                wf.setframerate(self.sample_rate) # 16000 Hz
                wf.writeframes(self.frames)
            logger.info(f"Saved call audio recording to: {self.filepath}")
            return self.filename
        except Exception as e:
            logger.error(f"Failed to save call audio recording: {e}")
            return None

def twilio_to_gemini(ulaw_b64: str, state):
    """
    Decodes Twilio's base64 G.711 mu-law (8kHz) audio to 16-bit PCM,
    resamples it to 16kHz PCM, and returns base64 encoded string + new state.
    """
    try:
        ulaw_data = base64.b64decode(ulaw_b64)
        if len(ulaw_data) == 0:
            return None, state
        
        # 1. Convert 8kHz mu-law to 8kHz linear PCM (16-bit, signed)
        pcm_8k = audioop.ulaw2lin(ulaw_data, 2)
        
        # 2. Resample 8kHz PCM to 16kHz PCM
        pcm_16k, new_state = audioop.ratecv(
            pcm_8k, 2, 1, 8000, 16000, state
        )
        
        # 3. Base64 encode PCM 16kHz audio chunk
        pcm_b64 = base64.b64encode(pcm_16k).decode("utf-8")
        return pcm_b64, new_state
    except Exception as e:
        logger.error(f"Error transcoding Twilio to Gemini audio: {e}")
        return None, state

def gemini_to_twilio(pcm_24k_b64: str, state):
    """
    Decodes Gemini's base64 PCM 24kHz audio, resamples it to 8kHz PCM,
    converts it to G.711 mu-law, and returns base64 encoded string + new state.
    """
    try:
        pcm_24k = base64.b64decode(pcm_24k_b64)
        if len(pcm_24k) == 0:
            return None, state
            
        # 1. Resample 24kHz PCM to 8kHz PCM
        pcm_8k, new_state = audioop.ratecv(
            pcm_24k, 2, 1, 24000, 8000, state
        )
        
        # 2. Convert 8kHz PCM to 8kHz mu-law
        ulaw_data = audioop.lin2ulaw(pcm_8k, 2)
        
        # 3. Base64 encode mu-law audio chunk
        ulaw_b64 = base64.b64encode(ulaw_data).decode("utf-8")
        return ulaw_b64, new_state
    except Exception as e:
        logger.error(f"Error transcoding Gemini to Twilio audio: {e}")
        return None, state
