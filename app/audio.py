import audioop
import base64
import logging

logger = logging.getLogger("VoiceAgent")

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
