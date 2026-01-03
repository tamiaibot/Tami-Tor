import os
import json
import logging
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse

app = FastAPI()
logging.basicConfig(level=logging.INFO)

# Environment variables
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "")
WA_ACCESS_TOKEN = os.getenv("WA_ACCESS_TOKEN", "")
WA_PHONE_NUMBER_ID = os.getenv("WA_PHONE_NUMBER_ID", "")

GRAPH_URL = f"https://graph.facebook.com/v20.0/{WA_PHONE_NUMBER_ID}/messages"


@app.get("/webhook")
async def webhook_verify(
    hub_mode: str | None = None,
    hub_verify_token: str | None = None,
    hub_challenge: str | None = None,
):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return PlainTextResponse(hub_challenge or "")
    raise HTTPException(status_code=403, detail="Verification failed")


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

    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(GRAPH_URL, headers=headers, json=payload)
        if r.status_code >= 300:
            raise RuntimeError(f"Send failed: {r.text}")


@app.post("/webhook")
async def webhook_receive(request: Request):
    body = await request.json()
    logging.info("Incoming: %s", json.dumps(body, ensure_ascii=False))

    try:
        entry = body.get("entry", [])
        if not entry:
            return {"status": "ignored"}

        changes = entry[0].get("changes", [])
        value = changes[0].get("value", {})
        messages = value.get("messages", [])

        if not messages:
            return {"status": "ignored"}

        msg = messages[0]
        from_number = msg.get("from")
        msg_type = msg.get("type")

        if msg_type == "text":
            text = msg["text"]["body"]
            await send_whatsapp_text(from_number, text)

        return {"status": "ok"}

    except Exception as e:
        logging.exception("Webhook error")
        return {"status": "error", "detail": str(e)}
