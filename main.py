import os
import json
import logging
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse

# ------------------------------------------------------------------------------
# App & logging
# ------------------------------------------------------------------------------
app = FastAPI()
logging.basicConfig(level=logging.INFO)

# ------------------------------------------------------------------------------
# Environment variables (set these in Render)
# ------------------------------------------------------------------------------
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "")
WA_ACCESS_TOKEN = os.getenv("WA_ACCESS_TOKEN", "")
WA_PHONE_NUMBER_ID = os.getenv("WA_PHONE_NUMBER_ID", "")

GRAPH_URL = f"https://graph.facebook.com/v20.0/{WA_PHONE_NUMBER_ID}/messages"

# ------------------------------------------------------------------------------
# Health check (optional but very useful)
# ------------------------------------------------------------------------------
@app.get("/")
async def health():
    return {"status": "ok"}

# ------------------------------------------------------------------------------
# Webhook verification (Meta / WhatsApp)
# ------------------------------------------------------------------------------
@app.get("/webhook")
async def webhook_verify(request: Request):
    qp = request.query_params

    mode = qp.get("hub.mode")
    token = qp.get("hub.verify_token")
    challenge = qp.get("hub.challenge")

    logging.info(
        "Webhook verify attempt: mode=%s token=%s challenge=%s",
        mode,
        token,
        challenge,
    )

    if mode == "subscribe" and token == VERIFY_TOKEN and challenge:
        return PlainTextResponse(challenge)

    raise HTTPException(status_code=403, detail="Verification failed")

# ------------------------------------------------------------------------------
# Send WhatsApp text message
# ------------------------------------------------------------------------------
async def send_whatsapp_text(to: str, text: str):
    headers = {
        "Authorization": f"Bearer {WA_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }
