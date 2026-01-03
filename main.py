import os
import json
import logging
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse

app = FastAPI()
logging.basicConfig(level=logging.INFO)

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "")
WA_ACCESS_TOKEN = os.getenv("WA_ACCESS_TOKEN", "")
WA_PHONE_NUMBER_ID = os.getenv("WA_PHONE_NUMBER_ID", "")

GRAPH_URL = f"https://graph.facebook.com/v20.0/{WA_PHONE_NUMBER_ID}/messages"


@app.on_event("startup")
async def dump_routes():
    # This will print all registered routes in Render logs on every deploy
    for r in app.routes:
        logging.info("ROUTE REGISTERED: %s %s", getattr(r, "methods", None), getattr(r, "path", None))


@app.get("/")
async def health():
    return {"status": "ok"}


@app.get("/webhook")
async def webhook_verify(request: Request):
    qp = request.query_params
    mode = qp.get("hub.mode")
    token = qp.get("hub.verify_token")
    challenge = qp.get("hub.challenge")

    logging.info("Webhook verify attempt: mode=%s token=%s challenge=%s", mode, token, challenge)

    if mode == "subscribe" and token == VERIFY_TOKEN and challenge:
        return PlainTextResponse(challenge)

    raise HTTPException(status_code=403, detail="Verification failed")


async def send_whatsapp_text(to: str, text: str):
    if not WA_ACCESS_TOKEN or not WA_PHONE_NUMBER_ID:
        raise RuntimeError("Missing WA_ACCESS_TOKEN or WA_PHONE_NUMBER_ID")

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
            raise RuntimeError(f"Send failed: {r.status_code} {r.text}")


@app.post("/webhook")
async def webhook_receive(request: Request):
    raw = await request.body()
    logging.info("WEBHOOK POST RECEIVED (HANDLER): %s", raw[:2000])

    try:
        body = json.loads(raw or b"{}")

        # WhatsApp sends object="whatsapp_business_account"
        if body.get("object") != "whatsapp_business_account":
            return {"status": "ignored"}

        entry = body.get("entry") or []
        if not entry:
            return {"status": "ignored"}

        changes = (entry[0].get("changes") or [])
        if not changes:
            return {"status": "ignored"}

        value = changes[0].get("value") or {}
        messages = value.get("messages") or []
        if not messages:
            return {"status": "ignored"}

        msg = messages[0]
        from_number = msg.get("from")
        msg_type = msg.get("type")

        logging.info("Incoming message type=%s from=%s", msg_type, from_number)

        if msg_type == "text":
            text_in = (msg.get("text") or {}).get("body", "")
            if from_number and text_in:
                await send_whatsapp_text(from_number, text_in)

        return {"status": "ok"}

    except Exception as e:
        logging.exception("Webhook handling error")
        return {"status": "error", "detail": str(e)}
