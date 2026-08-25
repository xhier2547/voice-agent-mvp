import os
from dotenv import load_dotenv

# Load environmental variables
load_dotenv(override=True)

def get_gemini_model():
    load_dotenv(override=True)
    return os.getenv("GEMINI_MODEL", "models/gemini-2.5-flash-native-audio-latest")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TRANSFER_NUMBER = os.getenv("TRANSFER_NUMBER", "+66812345678")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "models/gemini-2.5-flash-native-audio-latest")
GEMINI_VOICE = os.getenv("GEMINI_VOICE", "Aoede")
PORT = int(os.getenv("PORT", 8000))
