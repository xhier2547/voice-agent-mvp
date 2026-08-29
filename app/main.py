import json
import asyncio
import logging
import datetime
import time
import re
import os
import io
import csv
import uuid
import pypdf
from fastapi import FastAPI, WebSocket, Request, Response, Body, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
import websockets
from app import config, audio, twilio_client, gemini_client

logger = logging.getLogger("APEX_AGENT")

app = FastAPI(title="APEX AGENT Platform")

def extract_text_from_file_bytes(content_bytes: bytes, filename: str) -> tuple[str, str]:
    """
    Extracts text from PDF, CSV, or TXT file bytes.
    Returns (extracted_text, source_type).
    """
    ext = os.path.splitext(filename)[1].lower()
    text = ""
    source_type = "txt"

    if ext == ".pdf":
        source_type = "pdf"
        try:
            pdf_reader = pypdf.PdfReader(io.BytesIO(content_bytes))
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        except Exception as e:
            logger.error(f"PDF extraction error: {e}")

    elif ext == ".csv":
        source_type = "csv"
        try:
            decoded = content_bytes.decode("utf-8-sig", errors="ignore")
            reader = csv.reader(io.StringIO(decoded))
            rows_str = []
            for row in reader:
                if row:
                    rows_str.append(" | ".join([cell.strip() for cell in row if cell.strip()]))
            text = "\n".join(rows_str)
        except Exception as e:
            logger.error(f"CSV extraction error: {e}")

    else:
        source_type = "txt"
        try:
            text = content_bytes.decode("utf-8", errors="ignore")
        except Exception as e:
            logger.error(f"TXT extraction error: {e}")

    return text.strip(), source_type


def semantic_chunk_text(text: str, chunk_size: int = 400, overlap: int = 50) -> list[str]:
    """
    Splits long text into overlapping chunks suitable for RAG vector embeddings.
    """
    if not text:
        return []

    text = re.sub(r'\n{3,}', '\n\n', text)
    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = start + chunk_size
        if end >= text_len:
            chunks.append(text[start:].strip())
            break

        break_point = text.rfind('\n', start, end)
        if break_point == -1 or break_point <= start:
            break_point = text.rfind(' ', start, end)

        if break_point == -1 or break_point <= start:
            break_point = end

        chunk = text[start:break_point].strip()
        if chunk:
            chunks.append(chunk)

        start = max(start + 1, break_point - overlap)

    return chunks


@app.post("/api/knowledge/upload")
async def upload_document_api(file: UploadFile = File(...)):
    try:
        content_bytes = await file.read()
        filename = file.filename or "uploaded_doc.txt"
        
        extracted_text, source_type = extract_text_from_file_bytes(content_bytes, filename)
        if not extracted_text:
            return JSONResponse({"status": "error", "message": "ไม่สามารถสกัดข้อความจากไฟล์ที่อัปโหลดได้ (ไฟล์ว่างหรือรูปแบบไม่ถูกต้อง)"}, status_code=400)

        chunks = semantic_chunk_text(extracted_text, chunk_size=400, overlap=50)
        doc_id = f"doc_{uuid.uuid4().hex[:8]}"
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            with open("data/documents.json", "r", encoding="utf-8") as f:
                documents = json.load(f)
        except Exception:
            documents = []

        doc_meta = {
            "doc_id": doc_id,
            "filename": filename,
            "source_type": source_type,
            "file_size_bytes": len(content_bytes),
            "chunk_count": len(chunks),
            "uploaded_at": now_str,
            "chunks": chunks
        }
        documents.insert(0, doc_meta)

        with open("data/documents.json", "w", encoding="utf-8") as f:
            json.dump(documents, f, ensure_ascii=False, indent=2)

        gemini_client.vector_rag_engine.ingest_dynamic_document(
            doc_id=doc_id,
            filename=filename,
            chunks=chunks,
            source_type=source_type
        )

        logger.info(f"Indexed document '{filename}' ({len(chunks)} chunks) into APEX AGENT ChromaDB.")
        return {
            "status": "success",
            "message": f"อัปโหลดและดรรชนีเอกสาร '{filename}' สำเร็จ! ({len(chunks)} Chunks)",
            "data": doc_meta
        }
    except Exception as e:
        logger.error(f"Error processing uploaded document: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.get("/api/knowledge/documents")
async def get_documents_api():
    try:
        try:
            with open("data/documents.json", "r", encoding="utf-8") as f:
                documents = json.load(f)
        except Exception:
            documents = []
        return {"status": "success", "data": documents}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.delete("/api/knowledge/documents/{doc_id}")
async def delete_document_api(doc_id: str):
    try:
        try:
            with open("data/documents.json", "r", encoding="utf-8") as f:
                documents = json.load(f)
        except Exception:
            documents = []

        updated_docs = [d for d in documents if d.get("doc_id") != doc_id]

        with open("data/documents.json", "w", encoding="utf-8") as f:
            json.dump(updated_docs, f, ensure_ascii=False, indent=2)

        gemini_client.vector_rag_engine.delete_dynamic_document(doc_id)

        return {"status": "success", "message": "ลบเอกสารออกจากระบบและ Vector Store เรียบร้อยแล้ว!"}
    except Exception as e:
        logger.error(f"Error deleting document {doc_id}: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.get("/api/knowledge")
async def get_knowledge_api():
    try:
        with open("data/knowledge.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        return {"status": "success", "data": data}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/knowledge")
async def save_knowledge_api(payload: dict = Body(...)):
    try:
        with open("data/knowledge.json", "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        gemini_client.vector_rag_engine.sync_knowledge()
        logger.info("Updated data/knowledge.json and synced ChromaDB Vector Store.")
        return {"status": "success", "message": "บันทึกฐานข้อมูลและดรรชนี Vector Database เรียบร้อยแล้ว!"}
    except Exception as e:
        logger.error(f"Failed to update knowledge base: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/call-logs")
async def get_call_logs_api():
    try:
        with open("data/call_logs.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        return {"status": "success", "data": data}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/reservations")
async def get_reservations_api():
    try:
        with open("data/reservations.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        return {"status": "success", "data": data}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/analytics/sentiment-intent")
async def get_sentiment_intent_analytics_api():
    try:
        try:
            with open("data/call_logs.json", "r", encoding="utf-8") as f:
                logs = json.load(f)
        except Exception:
            logs = {}
            
        sentiment_counts = {"Positive": 0, "Neutral": 0, "Negative": 0}
        intent_counts = {}
        total_calls = 0
        customer_list = []
        
        for phone, customer_data in logs.items():
            cust_name = customer_data.get("caller_name", "ลูกค้า")
            c_calls = customer_data.get("total_calls", 0)
            last_time = customer_data.get("last_call_time", "")
            last_sent = customer_data.get("last_sentiment", "Neutral")
            last_intent = customer_data.get("last_intent", "สอบถามข้อมูลทั่วไป")
            last_summary = customer_data.get("last_summary", "")
            
            history = customer_data.get("history", [])
            total_calls += len(history) if history else c_calls
            
            for h in history:
                sent = h.get("sentiment", "Neutral")
                if sent in sentiment_counts:
                    sentiment_counts[sent] += 1
                else:
                    sentiment_counts["Neutral"] += 1
                    
                intent = h.get("primary_intent", "สอบถามข้อมูลทั่วไป")
                intent_counts[intent] = intent_counts.get(intent, 0) + 1

            customer_list.append({
                "phone": phone,
                "caller_name": cust_name,
                "total_calls": c_calls,
                "last_call_time": last_time,
                "last_sentiment": last_sent,
                "last_intent": last_intent,
                "last_summary": last_summary,
                "history_count": len(history)
            })

        grand_total = max(1, sum(sentiment_counts.values()))
        sentiment_percentages = {
            k: round((v / grand_total) * 100, 1) for k, v in sentiment_counts.items()
        }

        return {
            "status": "success",
            "data": {
                "total_calls": sum(sentiment_counts.values()),
                "sentiment_counts": sentiment_counts,
                "sentiment_percentages": sentiment_percentages,
                "intent_counts": intent_counts,
                "customers": customer_list
            }
        }
    except Exception as e:
        logger.error(f"Error serving analytics API: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/transcripts/{phone}")
async def get_customer_transcripts_api(phone: str):
    try:
        try:
            with open("data/call_logs.json", "r", encoding="utf-8") as f:
                logs = json.load(f)
        except Exception:
            logs = {}

        if phone not in logs:
            return JSONResponse({"status": "error", "message": "Customer phone not found"}, status_code=404)

        return {"status": "success", "data": logs[phone]}
    except Exception as e:
        logger.error(f"Error retrieving transcripts for {phone}: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/recordings/{filename}")
async def get_recording_api(filename: str):
    filepath = os.path.join("recordings", filename)
    if os.path.exists(filepath):
        return FileResponse(filepath, media_type="audio/wav")
    return JSONResponse({"status": "error", "message": "Recording file not found"}, status_code=404)

import urllib.request
import urllib.error

def analyze_call_intelligence(transcript_list: list) -> dict:
    """
    Analyzes the conversation transcript using Gemini REST API to extract:
    - summary: 1-2 sentence overview
    - sentiment: "Positive" | "Neutral" | "Negative"
    - sentiment_score: float 0.0 to 1.0
    - sentiment_reason: short explanation
    - primary_intent: main customer intent category
    """
    default_res = {
        "summary": "ลูกค้าสนทนากับระบบผู้ช่วยเสียง",
        "sentiment": "Neutral",
        "sentiment_score": 0.5,
        "sentiment_reason": "บทสนทนาทั่วไป",
        "primary_intent": "สอบถามข้อมูลทั่วไป"
    }

    if not transcript_list:
        return default_res

    formatted_transcript = ""
    for turn in transcript_list:
        role = "ลูกค้า (User)" if turn.get("role") == "user" else "ผู้ช่วย AI (Gemini)"
        text = turn.get("text", "")
        formatted_transcript += f"{role}: {text}\n"

    prompt = f"""ต่อไปนี้คือบทสนทนาระหว่างลูกค้าและผู้ช่วย AI ทางโทรศัพท์ของร้าน DripAI Coffee & Space:

{formatted_transcript}

โปรดวิเคราะห์บทสนทนานี้และตอบกลับเป็น JSON เท่านั้นในรูปแบบต่อไปนี้ (ห้ามมี Markdown หรือข้อความอื่น):
{{
  "summary": "สรุปความต้องการของลูกค้าและข้อสรุปการสนทนา 1-2 ประโยค",
  "sentiment": "Positive" | "Neutral" | "Negative",
  "sentiment_score": 0.95,
  "sentiment_reason": "เหตุผลสั้นๆ สำหรับอารมณ์ของลูกค้า",
  "primary_intent": "เลือกหมวดหมู่อย่างใดอย่างหนึ่งจาก: 'สอบถามโปรโมชั่น', 'จองโต๊ะ', 'สอบถามสถานที่และเวลา', 'สอบถามเมนู', 'สมัคร/เช็กแต้มสมาชิก', 'อื่นๆ'"
}}"""

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={config.GEMINI_API_KEY}"
        req_data = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json"
            }
        }
        req_body = json.dumps(req_data).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=req_body,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            candidates = res_data.get("candidates", [])
            if candidates:
                content = candidates[0].get("content", {})
                parts = content.get("parts", [])
                if parts:
                    raw_text = parts[0].get("text", "").strip()
                    if raw_text:
                        parsed = json.loads(raw_text)
                        return {
                            "summary": parsed.get("summary", default_res["summary"]),
                            "sentiment": parsed.get("sentiment", default_res["sentiment"]),
                            "sentiment_score": float(parsed.get("sentiment_score", 0.5)),
                            "sentiment_reason": parsed.get("sentiment_reason", default_res["sentiment_reason"]),
                            "primary_intent": parsed.get("primary_intent", default_res["primary_intent"])
                        }
    except Exception as e:
        logger.error(f"Error analyzing call intelligence: {e}")

    return default_res

def generate_conversation_summary(transcript_list: list) -> str:
    res = analyze_call_intelligence(transcript_list)
    return res.get("summary", "ลูกค้าสนทนากับระบบผู้ช่วยเสียง")

def save_call_log(
    phone: str,
    caller_name: str,
    summary: str = None,
    recording_file: str = None,
    duration_sec: float = 0.0,
    transcript: list = None,
    tools_called: list = None,
    sentiment: str = "Neutral",
    sentiment_score: float = 0.5,
    sentiment_reason: str = "บทสนทนาทั่วไป",
    primary_intent: str = "สอบถามข้อมูลทั่วไป"
):
    try:
        try:
            with open("data/call_logs.json", "r", encoding="utf-8") as f:
                logs = json.load(f)
        except Exception:
            logs = {}
        
        phone_key = phone or "081-234-5678"
        if phone_key not in logs:
            logs[phone_key] = {
                "caller_name": caller_name or "Vera Sun",
                "phone": phone_key,
                "total_calls": 0,
                "last_call_time": "",
                "last_summary": "ลูกค้าโทรเข้ามาสนทนากับระบบ Voice Agent",
                "last_sentiment": sentiment,
                "last_intent": primary_intent,
                "recording_file": None,
                "history": []
            }
        
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logs[phone_key]["caller_name"] = caller_name or logs[phone_key]["caller_name"]
        logs[phone_key]["total_calls"] += 1
        logs[phone_key]["last_call_time"] = now_str
        logs[phone_key]["last_summary"] = summary or logs[phone_key]["last_summary"]
        logs[phone_key]["last_sentiment"] = sentiment
        logs[phone_key]["last_intent"] = primary_intent
        if recording_file:
            logs[phone_key]["recording_file"] = recording_file

        call_id = f"call_{phone_key}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logs[phone_key]["history"].append({
            "call_id": call_id,
            "timestamp": now_str,
            "topic": primary_intent or "บันทึกการโทรสนทนาโต้ตอบสด",
            "recording_file": recording_file,
            "duration_sec": round(duration_sec, 1),
            "summary": summary or "ลูกค้าเข้าชมระบบและสนทนากับระบบผู้ช่วยเสียง",
            "sentiment": sentiment,
            "sentiment_score": sentiment_score,
            "sentiment_reason": sentiment_reason,
            "primary_intent": primary_intent,
            "transcript": transcript or [],
            "tools_called": tools_called or []
        })

        with open("data/call_logs.json", "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved call log, sentiment ({sentiment}), intent ({primary_intent}) & transcript for {phone_key}")
    except Exception as e:
        logger.error(f"Error saving call log: {e}")

def load_phone_modal_template() -> str:
    try:
        with open("app/templates/phone_modal.html", "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.warning(f"Could not load phone_modal.html template: {e}")
        return ""

@app.get("/", response_class=HTMLResponse)
async def get_index():
    phone_modal_html = load_phone_modal_template()
    try:
        with open("data/knowledge.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {
            "company_name": "DripAI Coffee & Space",
            "operating_hours": "เปิดให้บริการทุกวัน เวลา 07:00 น. ถึง 20:00 น.",
            "location": "ชั้น 1 อาคารทรู ดิจิทัล พาร์ค สุขุมวิท 101 กรุงเทพฯ",
            "contact_number": "02-123-4567",
            "wifi_password": "DripAICoffeeGuest (ความเร็ว 500/500 Mbps)",
            "promotions": [],
            "faq": []
        }
        
    promos_html = ""
    for p in data.get("promotions", []):
        promos_html += f"<li><strong>{p.get('name')}:</strong> {p.get('detail')}</li>"
    if not promos_html:
        promos_html = "<li>ไม่มีโปรโมชั่นในขณะนี้</li>"
        
    faq_html = ""
    for item in data.get("faq", []):
        faq_html += f"""
        <div class="faq-item">
            <div class="faq-q">{item.get('question')}</div>
            <div class="faq-a">{item.get('answer')}</div>
        </div>
        """
    if not faq_html:
        faq_html = "<p style='color: var(--text-muted); font-size: 13px;'>ไม่มีคำถามที่พบบ่อย</p>"

    # Read our newly created index.html template
    try:
        with open("app/templates/index.html", "r", encoding="utf-8") as f:
            html_template = f.read()
    except Exception as e:
        logger.error(f"Failed to read index.html template: {e}")
        return HTMLResponse(content=f"Error loading template: {e}", status_code=500)

    # Perform simple template replacements
    html_content = html_template
    html_content = html_content.replace("{{COMPANY_NAME}}", data.get("company_name", "DripAI Coffee & Space"))
    html_content = html_content.replace("{{OPERATING_HOURS}}", data.get("operating_hours", ""))
    html_content = html_content.replace("{{LOCATION}}", data.get("location", ""))
    html_content = html_content.replace("{{CONTACT_NUMBER}}", data.get("contact_number", ""))
    html_content = html_content.replace("{{WIFI_PASSWORD}}", data.get("wifi_password", ""))
    html_content = html_content.replace("{{PROMOS_HTML}}", promos_html)
    html_content = html_content.replace("{{FAQ_HTML}}", faq_html)
    html_content = html_content.replace("{{PHONE_MODAL_HTML}}", phone_modal_html)

    return HTMLResponse(content=html_content)

@app.post("/incoming-call")
async def incoming_call(request: Request):
    form_data = await request.form()
    from_number = form_data.get("From", "+66812345678")
    print(f"DEBUG: Incoming call from: {from_number}", flush=True)
    
    # Try x-forwarded-host first (often sent by ngrok/proxies), then fallback to host
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    print(f"DEBUG: Resolved host for Twilio Stream: {host}", flush=True)
    
    twiml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="wss://{host}/media-stream?phone={from_number}" />
    </Connect>
</Response>
"""
    print(f"DEBUG: Generated TwiML: {twiml_response.strip()}", flush=True)
    return Response(content=twiml_response, media_type="application/xml")

@app.websocket("/media-stream")
async def handle_media_stream(twilio_ws: WebSocket):
    await twilio_ws.accept()
    print("DEBUG: Accepted Twilio WebSocket connection.", flush=True)
    
    phone = twilio_ws.query_params.get("phone", "081-234-5678")
    print(f"DEBUG: Twilio WebSocket connected. Caller Phone from query param: {phone}", flush=True)
    
    if not config.GEMINI_API_KEY or "PLACEHOLDER" in config.GEMINI_API_KEY:
        print("DEBUG ERROR: GEMINI_API_KEY is not configured or is a placeholder.", flush=True)
        await twilio_ws.close()
        return
        
    gemini_url = f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key={config.GEMINI_API_KEY}"
    
    session = {
        "stream_sid": None,
        "call_sid": None,
        "transferring": False
    }
    
    # Transcript & Stats Instrumentation
    start_time = time.time()
    transcript_history = []
    tools_called = []
    caller_name = "ลูกค้า"
    try:
        with open("data/call_logs.json", "r", encoding="utf-8") as f:
            logs = json.load(f)
            if phone in logs:
                caller_name = logs[phone].get("caller_name", "ลูกค้า")
    except Exception:
        pass

    setup_event = asyncio.Event()
    
    try:
        async with websockets.connect(gemini_url) as gemini_ws:
            print("DEBUG: Connected to Gemini Live API WebSocket.", flush=True)
            
            # Send initial setup message first with customer memory!
            sys_instruction = gemini_client.get_system_instruction(caller_phone=phone, caller_name=caller_name)
            setup_msg = gemini_client.build_setup_message(sys_instruction)
            await gemini_ws.send(json.dumps(setup_msg))
            print("DEBUG: Sent setup message to Gemini with Twilio memory.", flush=True)
            
            # Task: Stream from Twilio to Gemini
            async def twilio_to_gemini_task():
                twilio_to_gemini_state = None
                try:
                    await setup_event.wait()
                    async for message in twilio_ws.iter_json():
                        if session["transferring"]:
                            break
                            
                        event = message.get("event")
                        if event == "start":
                            start_data = message.get("start", {})
                            session["stream_sid"] = message.get("streamSid")
                            session["call_sid"] = start_data.get("callSid")
                            print(f"DEBUG: Twilio stream started. Stream SID: {session['stream_sid']}, Call SID: {session['call_sid']}", flush=True)
                            
                        elif event == "media":
                            if not session["stream_sid"]:
                                session["stream_sid"] = message.get("streamSid")
                                
                            media = message.get("media", {})
                            payload = media.get("payload")
                            if payload:
                                # Resample and encode to PCM 16kHz
                                pcm_b64, twilio_to_gemini_state = audio.twilio_to_gemini(payload, twilio_to_gemini_state)
                                if pcm_b64:
                                    gemini_msg = {
                                        "realtimeInput": {
                                            "mediaChunks": [
                                                {
                                                    "mimeType": "audio/pcm",
                                                    "data": pcm_b64
                                                }
                                            ]
                                        }
                                    }
                                    await gemini_ws.send(json.dumps(gemini_msg))
                                    
                        elif event == "stop":
                            print("DEBUG: Twilio stream stopped.", flush=True)
                            break
                except Exception as e:
                    print(f"DEBUG ERROR: Error in Twilio to Gemini task: {e}", flush=True)
                    
            # Task: Stream from Gemini to Twilio
            async def gemini_to_twilio_task():
                gemini_to_twilio_state = None
                try:
                    # Process messages from Gemini
                    async for message_str in gemini_ws:
                        if session["transferring"]:
                            break
                            
                        data = json.loads(message_str)
                        
                        if "setupComplete" in data:
                            print("DEBUG: Gemini Live API setup complete.", flush=True)
                            setup_event.set()
                            # Trigger initial welcoming greeting for Twilio
                            greeting_prompt = "กรุณากล่าวทักทายต้อนรับลูกค้าเข้าสู่ร้าน DripAI Coffee & Space (หากทราบชื่อลูกค้าจากระบบให้ทักทายด้วยชื่ออย่างเป็นกันเอง) และถามความต้องการของเขาทันทีสั้นๆ"
                            trigger_msg = {
                                "clientContent": {
                                    "turns": [
                                        {
                                            "role": "user",
                                            "parts": [{"text": greeting_prompt}]
                                        }
                                    ],
                                    "turnComplete": True
                                }
                            }
                            await gemini_ws.send(json.dumps(trigger_msg))
                            
                        elif "serverContent" in data:
                            server_content = data["serverContent"]
                            
                            # Capture Transcripts for history logging
                            if "inputTranscription" in server_content:
                                transcript = server_content["inputTranscription"].get("text", "").strip()
                                if transcript:
                                    if transcript_history and transcript_history[-1]["role"] == "user":
                                        prev_text = transcript_history[-1]["text"]
                                        needs_space = bool(re.search(r'\w$', prev_text) and re.search(r'^\w', transcript))
                                        transcript_history[-1]["text"] = prev_text + (" " if needs_space else "") + transcript
                                    else:
                                        transcript_history.append({
                                            "role": "user",
                                            "text": transcript,
                                            "time": datetime.datetime.now().strftime("%H:%M:%S")
                                        })
                            if "outputTranscription" in server_content:
                                transcript = server_content["outputTranscription"].get("text", "").strip()
                                if transcript:
                                    if transcript_history and transcript_history[-1]["role"] == "model":
                                        prev_text = transcript_history[-1]["text"]
                                        needs_space = bool(re.search(r'\w$', prev_text) and re.search(r'^\w', transcript))
                                        transcript_history[-1]["text"] = prev_text + (" " if needs_space else "") + transcript
                                    else:
                                        transcript_history.append({
                                            "role": "model",
                                            "text": transcript,
                                            "time": datetime.datetime.now().strftime("%H:%M:%S")
                                        })

                            # Check for Barge-in (Interruption)
                            if server_content.get("interrupted"):
                                print("DEBUG: Interruption detected (Barge-in)! Clearing Twilio buffers.", flush=True)
                                if session["stream_sid"]:
                                    clear_msg = {
                                        "event": "clear",
                                        "streamSid": session["stream_sid"]
                                    }
                                    await twilio_ws.send_json(clear_msg)
                                continue
                                
                            # Convert output audio chunks and send to Twilio
                            model_turn = server_content.get("modelTurn")
                            if model_turn:
                                parts = model_turn.get("parts", [])
                                for part in parts:
                                    inline_data = part.get("inlineData")
                                    if inline_data and inline_data.get("mimeType", "").startswith("audio/pcm"):
                                        pcm_24k_b64 = inline_data.get("data")
                                        if session["stream_sid"]:
                                            ulaw_b64, gemini_to_twilio_state = audio.gemini_to_twilio(pcm_24k_b64, gemini_to_twilio_state)
                                            if ulaw_b64:
                                                media_msg = {
                                                    "event": "media",
                                                    "streamSid": session["stream_sid"],
                                                    "media": {
                                                        "payload": ulaw_b64
                                                     }
                                                }
                                                await twilio_ws.send_json(media_msg)
                                                 
                        elif "toolCall" in data:
                            tool_call = data["toolCall"]
                            function_calls = tool_call.get("functionCalls", [])
                            for fc in function_calls:
                                fn_name = fc.get("name")
                                call_id = fc.get("id")
                                args = fc.get("args", {})
                                print(f"DEBUG: Gemini requested tool call '{fn_name}'. ID: {call_id}", flush=True)
                                if fn_name not in tools_called:
                                    tools_called.append(fn_name)

                                if fn_name == "query_knowledge":
                                    result = gemini_client.execute_query_knowledge(args.get("query"))
                                    tool_resp = {
                                        "toolResponse": {
                                            "functionResponses": [
                                                {
                                                    "response": {"output": result},
                                                    "id": call_id
                                                }
                                            ]
                                        }
                                    }
                                    await gemini_ws.send(json.dumps(tool_resp))
                                elif fn_name == "end_call":
                                    result = gemini_client.execute_end_call(args.get("reason"))
                                    tool_resp = {
                                        "toolResponse": {
                                            "functionResponses": [
                                                {
                                                    "response": {"output": result},
                                                    "id": call_id
                                                }
                                            ]
                                        }
                                    }
                                    await gemini_ws.send(json.dumps(tool_resp))
                                elif fn_name == "book_table":
                                    result = gemini_client.execute_book_table(
                                        name=args.get("name"),
                                        phone=args.get("phone"),
                                        date_time=args.get("date_time"),
                                        guests=args.get("guests")
                                    )
                                    tool_resp = {
                                        "toolResponse": {
                                            "functionResponses": [
                                                {
                                                    "response": {"output": result},
                                                    "id": call_id
                                                }
                                            ]
                                        }
                                    }
                                    await gemini_ws.send(json.dumps(tool_resp))
                                elif fn_name == "check_member_points":
                                    result = gemini_client.execute_check_member_points(args.get("phone"))
                                    tool_resp = {
                                        "toolResponse": {
                                            "functionResponses": [
                                                {
                                                    "response": {"output": result},
                                                    "id": call_id
                                                }
                                            ]
                                        }
                                    }
                                    await gemini_ws.send(json.dumps(tool_resp))
                                elif fn_name == "send_sms_info":
                                    result = gemini_client.execute_send_sms_info(args.get("phone"), args.get("info_type"))
                                    tool_resp = {
                                        "toolResponse": {
                                            "functionResponses": [
                                                {
                                                    "response": {"output": result},
                                                    "id": call_id
                                                }
                                            ]
                                        }
                                    }
                                    await gemini_ws.send(json.dumps(tool_resp))
                                elif fn_name == "check_reservation":
                                    result = gemini_client.execute_check_reservation(args.get("phone"))
                                    tool_resp = {
                                        "toolResponse": {
                                            "functionResponses": [
                                                {
                                                    "response": {"output": result},
                                                    "id": call_id
                                                }
                                            ]
                                        }
                                    }
                                    await gemini_ws.send(json.dumps(tool_resp))
                                elif fn_name == "transfer_call":
                                    if session["call_sid"]:
                                        session["transferring"] = True
                                        
                                        response_msg = {
                                            "toolResponse": {
                                                "functionResponses": [
                                                    {
                                                        "response": {
                                                            "output": {"status": "Call transfer initiated"}
                                                        },
                                                        "id": call_id
                                                    }
                                                ]
                                            }
                                        }
                                        await gemini_ws.send(json.dumps(response_msg))
                                        print("DEBUG: Sent toolResponse to Gemini.", flush=True)
                                        
                                        print(f"DEBUG: Triggering Twilio call transfer for Call SID: {session['call_sid']}", flush=True)
                                        await asyncio.to_thread(twilio_client.transfer_call, session["call_sid"])
                                        break
                except Exception as e:
                    print(f"DEBUG ERROR: Error in Gemini to Twilio task: {e}", flush=True)
                    
            # Gather tasks
            await asyncio.gather(twilio_to_gemini_task(), gemini_to_twilio_task())
            
    except websockets.exceptions.ConnectionClosed:
        print("DEBUG: Gemini WebSocket connection closed.", flush=True)
    except Exception as e:
        print(f"DEBUG ERROR: Error in media stream relay: {e}", flush=True)
        import traceback
        traceback.print_exc()
    finally:
        print("DEBUG: Cleaning up connections...", flush=True)
        duration_sec = time.time() - start_time
        try:
            await twilio_ws.close()
        except Exception:
            pass
        
        # Save transcript and summary to logs
        if transcript_history:
            summary = generate_conversation_summary(transcript_history)
            save_call_log(
                phone=phone,
                caller_name=caller_name,
                summary=summary,
                recording_file=None,
                duration_sec=duration_sec,
                transcript=transcript_history,
                tools_called=tools_called
            )
        print("DEBUG: WebSocket connections cleaned up.", flush=True)

@app.websocket("/local-stream")
async def handle_local_stream(client_ws: WebSocket):
    await client_ws.accept()
    print("DEBUG: Accepted local WebSocket connection.", flush=True)
    
    if not config.GEMINI_API_KEY or "PLACEHOLDER" in config.GEMINI_API_KEY:
        print("DEBUG ERROR: GEMINI_API_KEY is not configured.", flush=True)
        await client_ws.send_json({"event": "status", "text": "Error: GEMINI_API_KEY not configured"})
        await client_ws.close()
        return
        
    gemini_url = f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key={config.GEMINI_API_KEY}"
    
    start_time = time.time()
    transcript_history = []
    tools_called = []
    
    session = {
        "transferring": False,

        # latency & chunk instrumentation
        "turn_id": 0,
        "turn_active": False,
        "turn_start": None,
        "vad_end": None,
        "last_audio_sent": None,
        "gemini_send": None,
        "first_frame": None,
        "first_audio": None,

        "audio_chunks_sent": 0,
        "vad_audio_chunks": None,
        "client_speaking": True,
        "pending_end_call": False,
    }
    setup_event = asyncio.Event()
    
    try:
        async with websockets.connect(gemini_url) as gemini_ws:
            print("DEBUG: Connected to Gemini Live API WebSocket for local stream.", flush=True)
            # Wait for browser's setup event to inject memory
            first_message = None
            p = "081-234-5678"
            n = "Vera Sun"
            try:
                first_message = await asyncio.wait_for(client_ws.receive_json(), timeout=2.0)
                if first_message and first_message.get("event") == "setup":
                    p = first_message.get("phone", p)
                    n = first_message.get("name", n)
            except Exception as e:
                print(f"DEBUG WARNING: Error reading setup message from browser: {e}", flush=True)

            # Send setup message BEFORE starting audio tasks
            sys_instruction = gemini_client.get_system_instruction(caller_phone=p, caller_name=n)
            setup_msg = gemini_client.build_setup_message(sys_instruction)
            await gemini_ws.send(json.dumps(setup_msg))
            print(f"DEBUG: Sent setup message to Gemini for local stream (phone={p}, name={n}).", flush=True)
            
            def now_ms():
                return time.perf_counter() * 1000

            def generate_ping_sound(duration_sec=0.7, sample_rate=24000) -> str:
                import math
                import struct
                import base64
                num_samples = int(duration_sec * sample_rate)
                audio_data = bytearray()
                freq = 440.0  # Soft A4 chime
                for i in range(num_samples):
                    t = i / sample_rate
                    decay = math.exp(-5.0 * t)
                    value = int(32767 * 0.15 * math.sin(2 * math.pi * freq * t) * decay)
                    audio_data.extend(struct.pack("<h", value))
                return base64.b64encode(audio_data).decode("utf-8")

            async def send_conversational_filler(text="อืม... สักครู่นะคะ..."):
                try:
                    await client_ws.send_json({
                        "event": "text",
                        "text": text
                    })
                    ping_b64 = generate_ping_sound()
                    await client_ws.send_json({
                        "event": "audio",
                        "data": ping_b64
                    })
                except Exception as e:
                    logger.warning(f"Failed to send conversational filler: {e}")

            recorder = audio.CallAudioRecorder(phone=p, caller_name=n)

            # Task: Stream from client web browser to Gemini
            async def client_to_gemini_task():
                nonlocal first_message
                try:
                    await setup_event.wait()
                    
                    # Handle already consumed setup message
                    if first_message:
                        event = first_message.get("event")
                        if event == "setup":
                            pass
                        first_message = None

                    async for message in client_ws.iter_json():
                        if session["transferring"]:
                            break
                        event = message.get("event")
                        if event == "setup":
                            p = message.get("phone")
                            n = message.get("name")
                            if p: recorder.phone = p
                            if n: recorder.caller_name = n
                        elif event == "turn_start":
                            # DEBUG: detect overlapping turns
                            if session["turn_active"]:
                                logger.warning(
                                    f"[TURN OVERLAP] "
                                    f"New turn started while TURN {session['turn_id']} is still active"
                                )

                            session["turn_id"] += 1
                            session["turn_active"] = True
                            session["client_speaking"] = True

                            session["speech_start_ms"] = now_ms()
                            session["speech_end_ms"] = None
                            session["gemini_first_ms"] = None
                            session["gemini_audio_ms"] = None
                            session["vad_audio_chunks"] = None

                            logger.info(
                                f"[TURN {session['turn_id']}] START"
                            )
                        elif event == "vad_end":
                            session["speech_end_ms"] = now_ms()
                            session["vad_audio_chunks"] = session["audio_chunks_sent"]

                            logger.info(
                                f"[TURN {session['turn_id']}] VAD_END "
                                f"audio_chunks={session['vad_audio_chunks']}"
                            )
                        elif event == "audio":
                            pcm_b64 = message.get("data")
                            if pcm_b64:
                                now_pc = time.perf_counter()
                                if not session.get("raw_mic_audio_start_time"):
                                    session["raw_mic_audio_start_time"] = now_pc
                                    t_now = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
                                    print(f"\n🎙️ [MIC AUDIO ARRIVED {t_now}] Raw microphone audio stream started arriving at server", flush=True)
                                session["raw_mic_audio_last_time"] = now_pc

                                if session.get("client_speaking", True):
                                    gemini_msg = {
                                        "realtimeInput": {
                                            "mediaChunks": [
                                                {
                                                    "mimeType": "audio/pcm;rate=16000",
                                                    "data": pcm_b64
                                                }
                                            ]
                                        }
                                    }

                                    await gemini_ws.send(json.dumps(gemini_msg))
                                    session["audio_chunks_sent"] += 1

                                try:
                                    recorder.add_user_audio(pcm_b64)
                                except Exception as e:
                                    logger.warning(
                                        f"Recorder user audio failed: {e}"
                                    )
                        elif event == "text":
                            user_text = message.get("text")
                            if user_text:
                                try:
                                    print(f"DEBUG User Text Input: {user_text}", flush=True)
                                except Exception:
                                    pass
                                transcript_history.append({
                                    "role": "user",
                                    "text": user_text,
                                    "time": datetime.datetime.now().strftime("%H:%M:%S")
                                })
                                try:
                                    t0_rag = time.perf_counter()
                                    rag_match = gemini_client.match_knowledge(user_text)
                                    rag_ms = round((time.perf_counter() - t0_rag) * 1000, 1)
                                    logger.info(f"TIMING: RAG Vector Search completed in {rag_ms}ms")
                                    await client_ws.send_json({
                                        "event": "rag_info",
                                        "query": user_text,
                                        "section": rag_match["section"],
                                        "content": rag_match["content"],
                                        "file": rag_match["file"],
                                        "method": rag_match.get("method", "Vector RAG"),
                                        "duration_ms": rag_ms
                                    })
                                except Exception:
                                    pass


                                text_msg = {
                                    "clientContent": {
                                        "turns": [
                                            {
                                                "role": "user",
                                                "parts": [{"text": user_text}]
                                            }
                                        ],
                                        "turnComplete": True
                                    }
                                }
                                await gemini_ws.send(json.dumps(text_msg))
                except Exception as e:
                    print(f"DEBUG ERROR: Error in client to Gemini task: {e}", flush=True)
                    
            # Task: Stream from Gemini to client web browser
            async def gemini_to_client_task():
                try:
                    async for message_str in gemini_ws:
                        if session["transferring"]:
                            break
                            
                        data = json.loads(message_str)
                        
                        if "setupComplete" in data:
                            print("DEBUG: Gemini Live API setup complete for local stream.", flush=True)
                            setup_event.set()
                            await client_ws.send_json({"event": "status", "text": "Ready to chat! Start speaking..."})
                            # Trigger initial welcoming greeting for local stream
                            greeting_prompt = "กรุณากล่าวทักทายต้อนรับลูกค้าเข้าสู่ร้าน DripAI Coffee & Space (หากทราบชื่อลูกค้าจากระบบให้ทักทายด้วยชื่ออย่างเป็นกันเอง) และถามความต้องการของเขาทันทีสั้นๆ"
                            trigger_msg = {
                                "clientContent": {
                                    "turns": [
                                        {
                                            "role": "user",
                                            "parts": [{"text": greeting_prompt}]
                                        }
                                    ],
                                    "turnComplete": True
                                }
                            }
                            await gemini_ws.send(json.dumps(trigger_msg))

                        elif "serverContent" in data:
                            server_content = data["serverContent"]

                            if "inputTranscription" in server_content:
                                transcript = server_content["inputTranscription"].get("text", "").strip()
                                if transcript:
                                    now_pc = time.perf_counter()
                                    session["last_speech_time"] = now_pc
                                    if not session.get("turn_speech_start_time"):
                                        session["turn_speech_start_time"] = now_pc
                                    
                                    t_now = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
                                    mic_start_t = session.get("raw_mic_audio_start_time") or now_pc
                                    stt_lag_ms = (now_pc - mic_start_t) * 1000
                                    
                                    if not session.get("first_stt_text_time"):
                                        session["first_stt_text_time"] = now_pc
                                        print(f"[TIMING {t_now}] GEMINI STT FIRST TEXT: '{transcript}' (Raw Audio Arrived -> Text Output Latency: {stt_lag_ms:.0f} ms / {stt_lag_ms/1000:.2f}s)", flush=True)
                                    else:
                                        print(f"[TIMING {t_now}] GEMINI STT TEXT FRAGMENT: '{transcript}' (Lag since audio start: {stt_lag_ms/1000:.2f}s)", flush=True)

                                    if transcript_history and transcript_history[-1]["role"] == "user":
                                        prev_text = transcript_history[-1]["text"]
                                        needs_space = bool(re.search(r'\w$', prev_text) and re.search(r'^\w', transcript))
                                        transcript_history[-1]["text"] = prev_text + (" " if needs_space else "") + transcript
                                    else:
                                        transcript_history.append({
                                            "role": "user",
                                            "text": transcript,
                                            "time": datetime.datetime.now().strftime("%H:%M:%S")
                                        })
                                    try:
                                        await client_ws.send_json({
                                            "event": "user_transcript",
                                            "text": transcript
                                        })
                                    except Exception:
                                        pass

                            if "outputTranscription" in server_content:
                                transcript = server_content["outputTranscription"].get("text", "").strip()
                                if transcript:
                                    now_pc = time.perf_counter()
                                    t_now = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
                                    if not session.get("turn_first_ai_text_time"):
                                        session["turn_first_ai_text_time"] = now_pc
                                        last_sp = session.get("last_speech_time") or now_pc
                                        turn_sp = session.get("turn_speech_start_time") or last_sp
                                        sil_ms = (now_pc - last_sp) * 1000
                                        tot_ms = (now_pc - turn_sp) * 1000
                                        print(f"\n[TIMING {t_now}] AI FIRST TEXT FRAGMENT: '{transcript}'", flush=True)
                                        print(f"  └─► Silence-to-Text Latency: {sil_ms:.0f} ms ({sil_ms/1000:.2f}s)", flush=True)
                                        print(f"  └─► Total Turn Time: {tot_ms:.0f} ms ({tot_ms/1000:.2f}s)", flush=True)
                                    else:
                                        print(f"[TIMING {t_now}] AI Text Fragment: '{transcript}'", flush=True)

                                    if transcript_history and transcript_history[-1]["role"] == "model":
                                        prev_text = transcript_history[-1]["text"]
                                        needs_space = bool(re.search(r'\w$', prev_text) and re.search(r'^\w', transcript))
                                        transcript_history[-1]["text"] = prev_text + (" " if needs_space else "") + transcript
                                    else:
                                        transcript_history.append({
                                            "role": "model",
                                            "text": transcript,
                                            "time": datetime.datetime.now().strftime("%H:%M:%S")
                                        })
                                    try:
                                        await client_ws.send_json({
                                            "event": "ai_transcript",
                                            "text": transcript
                                        })
                                    except Exception:
                                        pass

                            if (
                                session["turn_active"]
                                and session["gemini_first_ms"] is None
                            ):
                                session["gemini_first_ms"] = now_ms()
                                # Keep continuous audio streaming to Gemini so server-side VAD can detect barge-in
                                session["client_speaking"] = True
                                
                                latency = 0
                                if session["speech_end_ms"] is not None:
                                    latency = session["gemini_first_ms"] - session["speech_end_ms"]

                                logger.info(
                                    f"[TURN {session['turn_id']}] FIRST_GEMINI_MESSAGE "
                                    f"latency={latency:.1f}ms"
                                )

                            if server_content.get("turnComplete"):
                                logger.info(
                                    f"[TURN {session['turn_id']}] TURN_COMPLETE"
                                )

                                try:
                                    await client_ws.send_json({
                                        "event": "turn_complete",
                                        "turn_id": session["turn_id"]
                                    })
                                except Exception:
                                    pass

                                if session.get("pending_end_call"):
                                    logger.info(f"[TURN {session['turn_id']}] END_CALL pending -> scheduling hangup in 2.5s after turn complete")
                                    session["pending_end_call"] = False
                                    async def delayed_hangup():
                                        await asyncio.sleep(2.5)
                                        try:
                                            await client_ws.send_json({"event": "end_call"})
                                        except Exception:
                                            pass
                                        await asyncio.sleep(0.6)
                                        try:
                                            await client_ws.close()
                                        except Exception:
                                            pass
                                    asyncio.create_task(delayed_hangup())

                                session["turn_active"] = False
                                session["client_speaking"] = True  # Start listening again
                                session["turn_first_ai_text_time"] = None
                                session["turn_first_ai_audio_time"] = None
                                session["turn_speech_start_time"] = None
                                session["raw_mic_audio_start_time"] = None
                                session["raw_mic_audio_last_time"] = None
                                session["first_stt_text_time"] = None

                                if session.get("pending_end_call"):
                                    logger.info(f"[TURN {session['turn_id']}] END_CALL pending -> scheduling hangup in 3.5s after turn complete")
                                    async def delayed_hangup():
                                        await asyncio.sleep(3.5)
                                        try:
                                            await client_ws.send_json({"event": "end_call"})
                                        except Exception:
                                            pass
                                    asyncio.create_task(delayed_hangup())

                            if server_content.get("interrupted"):
                                logger.info(
                                    f"[TURN {session['turn_id']}] INTERRUPTED / BARGE-IN"
                                )

                                try:
                                    await client_ws.send_json({
                                        "event": "clear",
                                        "turn_id": session["turn_id"]
                                    })
                                except Exception:
                                    pass

                                session["turn_active"] = False
                                session["client_speaking"] = True  # Start listening again

                                continue

                            model_turn = server_content.get("modelTurn")
                            if model_turn:
                                parts = model_turn.get("parts", [])
                                for part in parts:
                                    text = part.get("text")
                                    if text:
                                        clean_text = text.strip()
                                        if not (clean_text.startswith("**") or "I have identified" in clean_text or "Retrieving" in clean_text or "Gathering" in clean_text or "Confirming" in clean_text or "I've" in clean_text):
                                            try:
                                                print(f"DEBUG Gemini Text: {clean_text}", flush=True)
                                            except Exception:
                                                pass
                                            try:
                                                await client_ws.send_json({
                                                    "event": "text",
                                                    "text": clean_text
                                                })
                                            except Exception:
                                                break
                                    inline_data = part.get("inlineData")
                                    if inline_data and inline_data.get("mimeType", "").startswith("audio/pcm"):
                                        pcm_24k_b64 = inline_data.get("data")

                                        if not session.get("turn_first_ai_audio_time"):
                                            session["turn_first_ai_audio_time"] = time.perf_counter()
                                            now_pc = time.perf_counter()
                                            t_now = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
                                            last_sp = session.get("last_speech_time") or now_pc
                                            turn_sp = session.get("turn_speech_start_time") or last_sp
                                            sil_ms = (now_pc - last_sp) * 1000
                                            tot_ms = (now_pc - turn_sp) * 1000
                                            print(f"\n" + "="*75, flush=True)
                                            print(f"🚀 [TIMING {t_now}] 🔊 FIRST AI AUDIO PCM PACKET SENT TO BROWSER!", flush=True)
                                            print(f"   ⏱️ Silence-to-Audio Latency (User stopped speech -> AI speaks): {sil_ms:.0f} ms ({sil_ms/1000:.2f}s)", flush=True)
                                            print(f"   ⏱️ Total Turn Time (First user word -> AI speaks): {tot_ms:.0f} ms ({tot_ms/1000:.2f}s)", flush=True)
                                            print(f"="*75 + "\n", flush=True)

                                        if (
                                            session["turn_active"]
                                            and session["gemini_audio_ms"] is None
                                        ):
                                            session["gemini_audio_ms"] = now_ms()

                                            latency_ms = 0
                                            if session["gemini_first_ms"] is not None:
                                                latency_ms = session["gemini_audio_ms"] - session["gemini_first_ms"]

                                            logger.info(
                                                f"[TURN {session['turn_id']}] FIRST_AUDIO "
                                                f"delta={latency_ms:.1f}ms"
                                            )

                                        try:
                                            await client_ws.send_json({
                                                "event": "audio",
                                                "data": pcm_24k_b64
                                            })
                                        except Exception:
                                            break

                                        try:
                                            recorder.add_bot_audio(pcm_24k_b64)
                                        except Exception as e:
                                            logger.warning(f"Recorder output failed: {e}")
                                        
                        elif "toolCall" in data:
                            try:
                                await client_ws.send_json({
                                    "event": "clear",
                                    "reason": "tool_call",
                                    "streamSid": None
                                })
                            except Exception:
                                pass
                            tool_call = data["toolCall"]
                            function_calls = tool_call.get("functionCalls", [])
                            for fc in function_calls:
                                fn_name = fc.get("name")
                                call_id = fc.get("id")
                                args = fc.get("args", {})
                                t_now = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
                                print(f"\n[TIMING {t_now}] 🛠️ TOOL CALL INVOKED BY GEMINI: '{fn_name}' args={args}", flush=True)
                                logger.info(f"[TURN {session['turn_id']}] TOOL_CALL fn={fn_name} id={call_id}")
                                if fn_name not in tools_called:
                                    tools_called.append(fn_name)

                                if fn_name == "end_call":
                                    result = gemini_client.execute_end_call(args.get("reason"))
                                    session["pending_end_call"] = True
                                    try:
                                        await client_ws.send_json({
                                            "event": "tool_info",
                                            "tool": "📞 end_call",
                                            "target": "จบการสนทนาและวางสาย",
                                            "description": result.get("message")
                                        })
                                    except Exception:
                                        pass
                                    tool_resp = {
                                        "toolResponse": {
                                            "functionResponses": [
                                                {
                                                    "response": {"output": result},
                                                    "id": call_id
                                                }
                                            ]
                                        }
                                    }
                                    await gemini_ws.send(json.dumps(tool_resp))

                                elif fn_name == "book_table":
                                    result = gemini_client.execute_book_table(
                                        name=args.get("name"),
                                        phone=args.get("phone"),
                                        date_time=args.get("date_time"),
                                        guests=args.get("guests")
                                    )
                                    try:
                                        await client_ws.send_json({
                                            "event": "tool_info",
                                            "tool": "📅 book_table",
                                            "target": args.get("name", "ลูกค้า"),
                                            "description": result.get("message")
                                        })
                                    except Exception:
                                        pass
                                    tool_resp = {
                                        "toolResponse": {
                                            "functionResponses": [
                                                {
                                                    "response": {"output": result},
                                                    "id": call_id
                                                }
                                            ]
                                        }
                                    }
                                    await gemini_ws.send(json.dumps(tool_resp))

                                elif fn_name == "check_member_points":
                                    result = gemini_client.execute_check_member_points(args.get("phone"))
                                    try:
                                        await client_ws.send_json({
                                            "event": "tool_info",
                                            "tool": "🎁 check_member_points",
                                            "target": args.get("phone", "สมาชิก"),
                                            "description": result.get("message")
                                        })
                                    except Exception:
                                        pass
                                    tool_resp = {
                                        "toolResponse": {
                                            "functionResponses": [
                                                {
                                                    "response": {"output": result},
                                                    "id": call_id
                                                }
                                            ]
                                        }
                                    }
                                    await gemini_ws.send(json.dumps(tool_resp))

                                elif fn_name == "send_sms_info":
                                    result = gemini_client.execute_send_sms_info(args.get("phone"), args.get("info_type"))
                                    try:
                                        await client_ws.send_json({
                                            "event": "tool_info",
                                            "tool": "📲 send_sms_info",
                                            "target": args.get("phone", "ลูกค้า"),
                                            "description": result.get("message")
                                        })
                                    except Exception:
                                        pass
                                    tool_resp = {
                                        "toolResponse": {
                                            "functionResponses": [
                                                {
                                                    "response": {"output": result},
                                                    "id": call_id
                                                }
                                            ]
                                        }
                                    }
                                    await gemini_ws.send(json.dumps(tool_resp))

                                elif fn_name == "check_reservation":
                                    result = gemini_client.execute_check_reservation(args.get("phone"))
                                    try:
                                        await client_ws.send_json({
                                            "event": "tool_info",
                                            "tool": "🔍 check_reservation",
                                            "target": args.get("phone", "การจอง"),
                                            "description": result.get("message")
                                        })
                                    except Exception:
                                        pass
                                    tool_resp = {
                                        "toolResponse": {
                                            "functionResponses": [
                                                {
                                                    "response": {"output": result},
                                                    "id": call_id
                                                }
                                            ]
                                        }
                                    }
                                    await gemini_ws.send(json.dumps(tool_resp))

                                elif fn_name == "query_knowledge":
                                    query_text = args.get("query", "")
                                    result = gemini_client.execute_query_knowledge(query_text)
                                    try:
                                        await client_ws.send_json({
                                            "event": "tool_info",
                                            "tool": "🔍 query_knowledge",
                                            "target": query_text or "คลังความรู้",
                                            "description": result.get("message")
                                        })
                                    except Exception:
                                        pass
                                    tool_resp = {
                                        "toolResponse": {
                                            "functionResponses": [
                                                {
                                                    "response": {"output": result},
                                                    "id": call_id
                                                }
                                            ]
                                        }
                                    }
                                    await gemini_ws.send(json.dumps(tool_resp))

                                elif fn_name == "transfer_call":
                                    session["transferring"] = True
                                    try:
                                        await client_ws.send_json({
                                            "event": "tool_info",
                                            "tool": "📞 transfer_call",
                                            "target": config.TRANSFER_NUMBER,
                                            "description": "กำลังโอนสายไปยังพนักงาน..."
                                        })
                                    except Exception:
                                        pass
                                    tool_resp = {
                                        "toolResponse": {
                                            "functionResponses": [
                                                {
                                                    "response": {"output": {"status": "transferring"}},
                                                    "id": call_id
                                                }
                                            ]
                                        }
                                    }
                                    await gemini_ws.send(json.dumps(tool_resp))
                                    try:
                                        await client_ws.send_json({"event": "transfer"})
                                    except Exception:
                                        pass
                                    break
                except Exception as e:
                    logger.exception(f"Error in Gemini to client task: {e}")
                    
            await asyncio.gather(client_to_gemini_task(), gemini_to_client_task())
            
    except websockets.exceptions.ConnectionClosed as e:
        logger.error(f"Gemini WebSocket connection closed for local stream: code={e.code}, reason={e.reason}")
        try:
            await client_ws.send_json({"event": "status", "text": f"Disconnected: {e.reason or 'Code ' + str(e.code)}"})
        except Exception:
            pass
    except Exception as e:
        logger.exception(f"Error in local media stream relay: {e}")
    finally:
        logger.info("Cleaning up local connections...")
        duration_sec = time.time() - start_time
        rec_file = recorder.save()
        # Save transcript and summary to logs
        if transcript_history:
            intel = analyze_call_intelligence(transcript_history)
            save_call_log(
                phone=recorder.phone,
                caller_name=recorder.caller_name,
                summary=intel.get("summary"),
                recording_file=rec_file,
                duration_sec=duration_sec,
                transcript=transcript_history,
                tools_called=tools_called,
                sentiment=intel.get("sentiment", "Neutral"),
                sentiment_score=intel.get("sentiment_score", 0.5),
                sentiment_reason=intel.get("sentiment_reason", "บทสนทนาทั่วไป"),
                primary_intent=intel.get("primary_intent", "สอบถามข้อมูลทั่วไป")
            )
        try:
            await client_ws.close()
        except Exception:
            pass
        logger.info("Local WebSocket connections cleaned up.")


