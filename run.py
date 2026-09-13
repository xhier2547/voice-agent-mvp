import sys
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import uvicorn
import logging
from app import config

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("VoiceAgent")

if __name__ == "__main__":
    logger.info(f"Starting modular Voice Agent MVP on port {config.PORT}...")
    # Run uvicorn pointing to the 'app' package, main module, and 'app' variable (access_log=False hides HTTP GET noise)
    uvicorn.run("app.main:app", host="0.0.0.0", port=config.PORT, reload=True, access_log=False)
    
# RUN INSTRUCTION:
# Run this file with: python run.py
