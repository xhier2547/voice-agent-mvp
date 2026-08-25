import logging
from twilio.rest import Client
from app import config

logger = logging.getLogger("VoiceAgent")

def transfer_call(call_sid: str) -> bool:
    """
    Redirects/transfers an active call to the configured TRANSFER_NUMBER
    by updating the call with a new TwiML Dial payload using Twilio REST API.
    """
    if not call_sid:
        logger.error("Cannot transfer call: No Call SID provided.")
        return False
        
    if not config.TWILIO_ACCOUNT_SID or "PLACEHOLDER" in config.TWILIO_ACCOUNT_SID:
        logger.error("Cannot transfer call: Twilio credentials are not configured.")
        return False

    try:
        client = Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)
        
        # Dial TwiML response in Thai
        twiml_payload = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say language="th-TH">กำลังโอนสายไปยังเจ้าหน้าที่สักครู่ค่ะ</Say>
    <Dial>{config.TRANSFER_NUMBER}</Dial>
</Response>
"""
        client.calls(call_sid).update(twiml=twiml_payload)
        logger.info(f"Successfully triggered call transfer for SID {call_sid} to {config.TRANSFER_NUMBER}")
        return True
    except Exception as e:
        logger.error(f"Error transferring call via Twilio REST API: {e}")
        return False
