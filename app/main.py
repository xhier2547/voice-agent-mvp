from IPython.core import magic_arguments
from IPython.core import magic_arguments
import json
import asyncio
import logging
import datetime
import time
from fastapi import FastAPI, WebSocket, Request, Response, Body
import os
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
import websockets
from app import config, audio, twilio_client, gemini_client

logger = logging.getLogger("VoiceAgent")

app = FastAPI()

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

@app.get("/api/recordings/{filename}")
async def get_recording_api(filename: str):
    filepath = os.path.join("recordings", filename)
    if os.path.exists(filepath):
        return FileResponse(filepath, media_type="audio/wav")
    return JSONResponse({"status": "error", "message": "Recording file not found"}, status_code=404)

def save_call_log(phone: str, caller_name: str, summary: str = None, recording_file: str = None):
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
                "recording_file": None,
                "history": []
            }
        
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logs[phone_key]["caller_name"] = caller_name or logs[phone_key]["caller_name"]
        logs[phone_key]["total_calls"] += 1
        logs[phone_key]["last_call_time"] = now_str
        if summary:
            logs[phone_key]["last_summary"] = summary
        if recording_file:
            logs[phone_key]["recording_file"] = recording_file

        logs[phone_key]["history"].append({
            "timestamp": now_str,
            "topic": "บันทึกการโทรสนทนาโต้ตอบสด",
            "recording_file": recording_file
        })

        with open("data/call_logs.json", "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved call log & audio recording for {phone_key}: {recording_file}")
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
    
    phone = twilio_ws.query_params.get("phone")
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
    
    setup_event = asyncio.Event()
    
    try:
        async with websockets.connect(gemini_url) as gemini_ws:
            print("DEBUG: Connected to Gemini Live API WebSocket.", flush=True)
            
            # Send initial setup message first with customer memory!
            sys_instruction = gemini_client.get_system_instruction(caller_phone=phone)
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
        try:
            await twilio_ws.close()
        except Exception:
            pass
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
                                print(f"DEBUG User Text Input: {user_text}", flush=True)
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

                                session["turn_active"] = False
                                session["client_speaking"] = True  # Start listening again

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
                                            print(f"DEBUG Gemini Text: {clean_text}", flush=True)
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
                                logger.info(f"[TURN {session['turn_id']}] TOOL_CALL fn={fn_name} id={call_id}")

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
        rec_file = recorder.save()
        if rec_file:
            save_call_log(phone=recorder.phone, caller_name=recorder.caller_name, recording_file=rec_file)
        try:
            await client_ws.close()
        except Exception:
            pass
        logger.info("Local WebSocket connections cleaned up.")


