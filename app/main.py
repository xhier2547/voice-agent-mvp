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

    SPEECH_THRESHOLD = None
    html_content = f"""
    <!DOCTYPE html>
    <html lang="th">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>DripAI Voice Agent Sandbox</title>
        <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Inter:wght@400;500;600;700&family=Noto+Sans+Thai:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <style>
            :root {{
                --bg-color: #f4f4f5;
                --card-bg: #ffffff;
                --border-color: #e4e4e7;
                --text-color: #09090b;
                --text-muted: #71717a;
                --accent-color: #18181b;
                --accent-hover: #27272a;
                --success-color: #10b981;
                --warning-color: #f59e0b;
                --radius-card: 20px;
                --shadow-soft: 0 4px 20px -2px rgba(0, 0, 0, 0.05), 0 0 0 1px rgba(228, 228, 231, 0.6);
            }}

            * {{
                box-sizing: border-box;
                margin: 0;
                padding: 0;
            }}

            body {{
                font-family: 'Plus Jakarta Sans', 'Inter', 'Noto Sans Thai', sans-serif;
                background-color: var(--bg-color);
                color: var(--text-color);
                min-height: 100vh;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
                padding: 24px;
                line-height: 1.5;
            }}

            header {{
                max-width: 1200px;
                margin: 0 auto 24px auto;
                width: 100%;
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 12px 0;
                border-bottom: 1px solid var(--border-color);
            }}

            .logo-container {{
                display: flex;
                align-items: center;
                gap: 12px;
            }}

            .logo-icon {{
                width: 44px;
                height: 44px;
                background: #18181b;
                border-radius: 12px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: 800;
                font-size: 22px;
                color: white;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
            }}

            .logo-text h1 {{
                font-size: 22px;
                font-weight: 800;
                letter-spacing: -0.5px;
                color: #09090b;
            }}

            .logo-text p {{
                font-size: 11px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 1px;
                color: var(--text-muted);
            }}

            .badge {{
                background: #ffffff;
                color: #09090b;
                border: 1px solid var(--border-color);
                padding: 8px 16px;
                border-radius: 20px;
                font-size: 12px;
                font-weight: 600;
                display: flex;
                align-items: center;
                gap: 8px;
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.03);
            }}

            .badge-dot {{
                width: 8px;
                height: 8px;
                background-color: var(--success-color);
                border-radius: 50%;
                display: inline-block;
            }}

            main {{
                max-width: 1200px;
                margin: 0 auto;
                width: 100%;
                flex: 1;
                display: grid;
                grid-template-columns: 1.2fr 1.8fr;
                gap: 24px;
                align-items: start;
            }}

            @media (max-width: 900px) {{
                main {{
                    grid-template-columns: 1fr;
                }}
            }}

            .card {{
                background: var(--card-bg);
                border: 1px solid var(--border-color);
                border-radius: var(--radius-card);
                padding: 28px;
                box-shadow: var(--shadow-soft);
            }}

            .agent-card {{
                display: flex;
                flex-direction: column;
                align-items: center;
                position: relative;
            }}

            .visualizer-container {{
                width: 100%;
                height: 100px;
                margin-bottom: 20px;
                position: relative;
                display: flex;
                align-items: center;
                justify-content: center;
                background: #fafafa;
                border: 1px solid var(--border-color);
                border-radius: 14px;
                overflow: hidden;
            }}

            canvas {{
                width: 100%;
                height: 100%;
                position: absolute;
                top: 0;
                left: 0;
            }}

            .avatar-button {{
                width: 140px;
                height: 140px;
                border-radius: 50%;
                background: #18181b;
                border: 4px solid var(--border-color);
                display: flex;
                align-items: center;
                justify-content: center;
                cursor: pointer;
                position: relative;
                z-index: 10;
                outline: none;
                transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
                box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
                color: white;
            }}

            .avatar-button:hover {{
                transform: scale(1.04);
                background: #27272a;
            }}

            .avatar-button.connecting {{
                border-color: var(--warning-color);
                animation: pulse-warn 1.5s infinite;
            }}

            .avatar-button.connected {{
                border-color: #09090b;
                box-shadow: 0 0 25px rgba(9, 9, 11, 0.15);
            }}

            .avatar-button.speaking {{
                border-color: var(--success-color);
                animation: pulse-success 1.5s infinite;
            }}

            .avatar-icon {{
                font-size: 48px;
                transition: transform 0.3s ease;
            }}

            .avatar-button:active .avatar-icon {{
                transform: scale(0.9);
            }}

            .status-text {{
                margin-top: 20px;
                font-size: 17px;
                font-weight: 700;
                letter-spacing: -0.3px;
                text-align: center;
                color: var(--text-color);
            }}

            .status-subtitle {{
                margin-top: 4px;
                font-size: 13px;
                color: var(--text-muted);
                text-align: center;
            }}

            .instruction-tip {{
                margin-top: 20px;
                background: #f4f4f5;
                border-radius: 12px;
                padding: 12px 16px;
                font-size: 12px;
                color: var(--text-muted);
                display: flex;
                align-items: center;
                gap: 10px;
                border: 1px solid var(--border-color);
                width: 100%;
            }}

            .tab-card {{
                display: flex;
                flex-direction: column;
                min-height: 600px;
            }}

            .tab-headers {{
                display: flex;
                gap: 8px;
                border-bottom: 1px solid var(--border-color);
                padding-bottom: 14px;
                margin-bottom: 20px;
            }}

            .tab-btn {{
                background: #f4f4f5;
                border: 1px solid var(--border-color);
                color: var(--text-muted);
                font-family: inherit;
                font-size: 13px;
                font-weight: 600;
                padding: 8px 16px;
                cursor: pointer;
                border-radius: 10px;
                transition: all 0.2s ease;
            }}

            .tab-btn.active {{
                background: #18181b;
                color: #ffffff;
                border-color: #18181b;
            }}

            .tab-content {{
                flex: 1;
                overflow-y: auto;
                display: none;
            }}

            .tab-content.active {{
                display: block;
            }}

            .console {{
                background: #09090b;
                border: 1px solid var(--border-color);
                border-radius: 14px;
                font-family: 'Courier New', Courier, monospace;
                font-size: 12px;
                padding: 16px;
                height: 100%;
                overflow-y: auto;
                color: #34d399;
            }}

            .console-line {{
                margin-bottom: 8px;
                line-height: 1.5;
                word-break: break-all;
            }}

            .console-time {{
                color: #71717a;
                margin-right: 8px;
            }}

            .console-system {{
                color: #38bdf8;
            }}

            .console-gemini {{
                color: #c084fc;
            }}

            .console-tool {{
                color: #fbbf24;
                font-weight: bold;
            }}

            .faq-list {{
                display: flex;
                flex-direction: column;
                gap: 12px;
            }}

            .faq-item {{
                background: #fafafa;
                border: 1px solid var(--border-color);
                border-radius: 12px;
                padding: 16px;
            }}

            .faq-q {{
                font-weight: 700;
                font-size: 14px;
                color: #09090b;
                margin-bottom: 6px;
                display: flex;
                gap: 8px;
            }}

            .faq-q::before {{
                content: "Q:";
                color: #18181b;
            }}

            .faq-a {{
                font-size: 13px;
                color: var(--text-muted);
                line-height: 1.6;
            }}

            .info-grid {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 12px;
                margin-bottom: 20px;
            }}

            .info-box {{
                background: #fafafa;
                border-radius: 12px;
                padding: 14px;
                border: 1px solid var(--border-color);
            }}

            .info-label {{
                font-size: 11px;
                color: var(--text-muted);
                text-transform: uppercase;
                letter-spacing: 0.8px;
                font-weight: 700;
                margin-bottom: 4px;
            }}

            .info-value {{
                font-size: 13px;
                font-weight: 700;
                color: #09090b;
            }}

            .promos-box ul {{
                padding-left: 20px;
                font-size: 13px;
                line-height: 1.6;
                color: var(--text-muted);
            }}

            .chat-box-container {{
                width: 100%;
                margin: 20px 0 10px 0;
                background: #fafafa;
                border: 1px solid var(--border-color);
                border-radius: 16px;
                padding: 16px;
                display: flex;
                flex-direction: column;
                gap: 12px;
            }}

            .chat-header {{
                font-size: 13px;
                font-weight: 700;
                color: #09090b;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}

            .speaking-badge {{
                font-size: 11px;
                background: #18181b;
                color: #ffffff;
                padding: 3px 10px;
                border-radius: 12px;
                font-weight: 600;
            }}

            .chat-messages {{
                height: 180px;
                overflow-y: auto;
                display: flex;
                flex-direction: column;
                gap: 10px;
                padding-right: 4px;
            }}

            .chat-msg {{
                font-size: 13px;
                line-height: 1.5;
                padding: 10px 14px;
                border-radius: 14px;
                max-width: 90%;
                word-break: break-word;
            }}

            .chat-msg.system {{
                background: #e4e4e7;
                color: #52525b;
                align-self: center;
                font-size: 12px;
                font-weight: 500;
            }}

            .chat-msg.user {{
                background: #18181b;
                color: #ffffff;
                align-self: flex-end;
                border-bottom-right-radius: 2px;
            }}

            .chat-msg.bot {{
                background: #f1f5f9;
                border: 1px solid var(--border-color);
                color: #0f172a;
                align-self: flex-start;
                border-bottom-left-radius: 2px;
                font-weight: 500;
            }}

            .chat-input-container {{
                display: flex;
                gap: 8px;
            }}

            .chat-input-container input {{
                flex: 1;
                background: #ffffff;
                border: 1px solid var(--border-color);
                border-radius: 10px;
                padding: 10px 14px;
                color: #09090b;
                font-family: inherit;
                font-size: 13px;
                outline: none;
                transition: border-color 0.2s;
            }}

            .chat-input-container input:focus {{
                border-color: #18181b;
            }}

            .send-btn {{
                background: #18181b;
                border: none;
                color: white;
                font-weight: 600;
                font-size: 13px;
                padding: 0 18px;
                border-radius: 10px;
                cursor: pointer;
                transition: background 0.2s;
            }}

            .send-btn:hover:not(:disabled) {{
                background: #27272a;
            }}

            .send-btn:hover:not(:disabled) {{
                background: #4f46e5;
            }}

            .send-btn:disabled {{
                opacity: 0.5;
                cursor: not-allowed;
            }}

            .console-rag {{
                background: rgba(99, 102, 241, 0.08);
                border: 1px solid rgba(99, 102, 241, 0.25);
                border-radius: 12px;
                padding: 12px 16px;
                margin-bottom: 12px;
            }}

            .rag-header {{
                color: #a5b4fc;
                font-weight: 600;
                margin-bottom: 8px;
                font-size: 12px;
                display: flex;
                align-items: center;
                gap: 6px;
            }}

            .rag-body {{
                font-size: 11px;
                line-height: 1.7;
                color: #e0e7ff;
                padding-left: 12px;
                border-left: 2px solid var(--accent-color);
            }}

            .rag-tag {{
                color: #9ca3af;
                font-weight: 500;
            }}

            .console-tool {{
                background: rgba(245, 158, 11, 0.08);
                border: 1px solid rgba(245, 158, 11, 0.3);
                border-radius: 12px;
                padding: 12px 16px;
                margin-bottom: 12px;
            }}

            .tool-header {{
                color: #fcd34d;
                font-weight: 600;
                margin-bottom: 8px;
                font-size: 12px;
                display: flex;
                align-items: center;
                gap: 6px;
            }}

            .tool-body {{
                font-size: 11px;
                line-height: 1.7;
                color: #fef3c7;
                padding-left: 12px;
                border-left: 2px solid var(--warning-color);
            }}

            .console-milestone {{
                background: rgba(16, 185, 129, 0.08);
                border: 1px solid rgba(16, 185, 129, 0.25);
                border-radius: 8px;
                padding: 6px 12px;
                margin-bottom: 6px;
                font-family: monospace;
                font-size: 11px;
                color: #6ee7b7;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}

            .console-summary {{
                background: rgba(99, 102, 241, 0.12);
                border: 1px solid rgba(99, 102, 241, 0.4);
                border-radius: 12px;
                padding: 14px 16px;
                margin-bottom: 14px;
                font-family: monospace;
                font-size: 12px;
                color: #e0e7ff;
            }}

            .summary-title {{
                font-weight: 800;
                font-size: 13px;
                color: #818cf8;
                margin-bottom: 8px;
                display: flex;
                align-items: center;
                gap: 8px;
            }}

            .summary-row {{
                display: flex;
                justify-content: space-between;
                padding: 3px 0;
                border-bottom: 1px dashed rgba(255,255,255,0.1);
            }}

            .summary-row.total {{
                border-top: 1px solid rgba(255,255,255,0.3);
                border-bottom: none;
                font-weight: 700;
                color: #34d399;
                margin-top: 6px;
                padding-top: 6px;
            }}


            .modal-overlay {{
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.85);
                backdrop-filter: blur(8px);
                z-index: 100;
                display: flex;
                align-items: center;
                justify-content: center;
                opacity: 0;
                pointer-events: none;
                transition: opacity 0.3s ease;
            }}

            .modal-overlay.active {{
                opacity: 1;
                pointer-events: all;
            }}

            .modal {{
                background: #111524;
                border: 1px solid rgba(99, 102, 241, 0.3);
                border-radius: 28px;
                padding: 40px;
                max-width: 450px;
                width: 90%;
                text-align: center;
                box-shadow: 0 20px 50px rgba(99, 102, 241, 0.15);
                transform: scale(0.9);
                transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
            }}

            .modal-overlay.active .modal {{
                transform: scale(1);
            }}

            /* iOS Phone Call Simulator Overlay */
            .phone-modal-overlay {{
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.88);
                backdrop-filter: blur(12px);
                z-index: 2000;
                display: flex;
                align-items: center;
                justify-content: center;
                opacity: 0;
                pointer-events: none;
                transition: all 0.35s cubic-bezier(0.16, 1, 0.3, 1);
            }}

            .phone-modal-overlay.active {{
                opacity: 1;
                pointer-events: all;
            }}

            .iphone-shell {{
                width: 360px;
                height: 720px;
                background: #09090b;
                border-radius: 48px;
                padding: 10px;
                box-shadow: 0 25px 80px rgba(0,0,0,0.9), 0 0 0 2px rgba(255,255,255,0.15), inset 0 0 0 2px rgba(255,255,255,0.1);
                position: relative;
                transform: scale(0.9);
                transition: transform 0.35s cubic-bezier(0.16, 1, 0.3, 1);
                display: flex;
                flex-direction: column;
            }}

            .phone-modal-overlay.active .iphone-shell {{
                transform: scale(1);
            }}

            .phone-inner-screen {{
                width: 100%;
                height: 100%;
                border-radius: 38px;
                background: linear-gradient(165deg, #1f0b18 0%, #440e2b 45%, #0b1c28 100%);
                display: flex;
                flex-direction: column;
                justify-content: space-between;
                padding: 16px 20px 24px 20px;
                color: white;
                position: relative;
                overflow: hidden;
            }}

            .phone-notch-bar {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                font-size: 13px;
                font-weight: 600;
                padding: 0 8px;
                margin-top: 4px;
                color: rgba(255, 255, 255, 0.9);
            }}

            .notch-pill {{
                width: 110px;
                height: 22px;
                background: #000;
                border-bottom-left-radius: 14px;
                border-bottom-right-radius: 14px;
                position: absolute;
                top: 0;
                left: 50%;
                transform: translateX(-50%);
                z-index: 10;
            }}

            .phone-caller-header {{
                margin-top: 36px;
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                padding: 0 4px;
            }}

            .caller-info {{
                display: flex;
                flex-direction: column;
                gap: 4px;
            }}

            .caller-name-text {{
                font-size: 26px;
                font-weight: 600;
                letter-spacing: -0.5px;
                color: #ffffff;
            }}

            .caller-status-time {{
                font-size: 15px;
                color: rgba(255, 255, 255, 0.75);
                display: flex;
                align-items: center;
                gap: 6px;
                font-variant-numeric: tabular-nums;
            }}

            .caller-avatar-circle {{
                width: 60px;
                height: 60px;
                border-radius: 50%;
                background: linear-gradient(135deg, #ec4899, #8b5cf6);
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 28px;
                border: 2px solid rgba(255, 255, 255, 0.25);
                box-shadow: 0 8px 20px rgba(0,0,0,0.4);
                overflow: hidden;
            }}

            .phone-chat-preview {{
                background: rgba(0, 0, 0, 0.25);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 16px;
                padding: 10px 14px;
                font-size: 12px;
                line-height: 1.5;
                color: rgba(255, 255, 255, 0.9);
                max-height: 90px;
                overflow-y: auto;
                margin: 10px 0;
            }}

            .phone-actions-grid {{
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 18px 12px;
                margin-bottom: 16px;
            }}

            .phone-action-btn-wrapper {{
                display: flex;
                flex-direction: column;
                align-items: center;
                gap: 6px;
            }}

            .phone-action-circle {{
                width: 60px;
                height: 60px;
                border-radius: 50%;
                background: rgba(255, 255, 255, 0.15);
                backdrop-filter: blur(12px);
                border: 1px solid rgba(255, 255, 255, 0.1);
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 22px;
                color: white;
                cursor: pointer;
                transition: all 0.2s ease;
            }}

            .phone-action-circle:hover {{
                background: rgba(255, 255, 255, 0.3);
                transform: scale(1.05);
            }}

            .phone-action-circle.active {{
                background: white;
                color: #1c0915;
            }}

            .phone-action-label {{
                font-size: 11px;
                color: rgba(255, 255, 255, 0.85);
            }}

            .phone-hangup-row {{
                display: flex;
                justify-content: center;
                margin-bottom: 8px;
            }}

            .phone-hangup-btn {{
                width: 64px;
                height: 64px;
                border-radius: 50%;
                background: #ff3b30;
                border: none;
                color: white;
                font-size: 28px;
                display: flex;
                align-items: center;
                justify-content: center;
                cursor: pointer;
                box-shadow: 0 8px 25px rgba(255, 59, 48, 0.5);
                transition: all 0.2s ease;
            }}

            .phone-hangup-btn:hover {{
                transform: scale(1.08);
                background: #e03126;
            }}

            .phone-home-indicator {{
                width: 120px;
                height: 4px;
                background: rgba(255, 255, 255, 0.6);
                border-radius: 2px;
                margin: 0 auto;
            }}

            .phone-animation {{
                width: 80px;
                height: 80px;
                background: var(--success-color);
                border-radius: 50%;
                margin: 0 auto 24px auto;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 36px;
                color: white;
                animation: phone-shake 1s infinite alternate;
                box-shadow: 0 0 30px var(--success-glow);
            }}

            .modal h2 {{
                font-size: 22px;
                font-weight: 700;
                margin-bottom: 12px;
            }}

            .modal p {{
                color: var(--text-muted);
                font-size: 14px;
                line-height: 1.6;
                margin-bottom: 30px;
            }}

            .modal-btn {{
                background: var(--accent-color);
                border: none;
                color: white;
                font-weight: 600;
                font-size: 14px;
                padding: 12px 30px;
                border-radius: 12px;
                cursor: pointer;
                transition: all 0.2s ease;
                box-shadow: 0 4px 15px var(--accent-glow);
            }}

            .modal-btn:hover {{
                transform: translateY(-2px);
                background-color: #4f46e5;
            }}

            @keyframes pulse-warn {{
                0% {{ box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.4); }}
                70% {{ box-shadow: 0 0 0 20px rgba(245, 158, 11, 0); }}
                100% {{ box-shadow: 0 0 0 0 rgba(245, 158, 11, 0); }}
            }}

            @keyframes pulse-success {{
                0% {{ box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.4); }}
                70% {{ box-shadow: 0 0 0 25px rgba(16, 185, 129, 0); }}
                100% {{ box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }}
            }}

            @keyframes phone-shake {{
                0% {{ transform: rotate(-10deg) scale(1); }}
                100% {{ transform: rotate(10deg) scale(1.1); }}
            }}

            footer {{
                max-width: 1200px;
                margin: 20px auto 0 auto;
                width: 100%;
                text-align: center;
                font-size: 12px;
                color: var(--text-muted);
                border-top: 1px solid var(--border-color);
                padding-top: 20px;
            }}

            ::-webkit-scrollbar {{
                width: 6px;
            }}
            ::-webkit-scrollbar-track {{
                background: transparent;
            }}
            ::-webkit-scrollbar-thumb {{
                background: rgba(255, 255, 255, 0.1);
                border-radius: 4px;
            }}
            ::-webkit-scrollbar-thumb:hover {{
                background: rgba(255, 255, 255, 0.2);
            }}
        </style>
    </head>
    <body>
        <header>
            <div class="logo-container">
                <div class="logo-icon">☕</div>
                <div class="logo-text">
                    <h1>{data.get('company_name')}</h1>
                    <p>Gemini Live Multimodal Voice Agent</p>
                </div>
            </div>
            <div class="badge">
                <span class="badge-dot"></span>
                Local Testing Server
            </div>
        </header>

        <main>
            <!-- Left Panel: Voice Agent Controls -->
            <div class="card agent-card">
                <!-- Phone Call Simulator Dialer Box (Top Position) -->
                <div class="dialer-box" style="margin-bottom: 16px; background: #fafafa; border: 1px solid var(--border-color); border-radius: 16px; padding: 16px;">
                    <div style="font-size: 13px; font-weight: 700; color: #09090b; margin-bottom: 12px; display: flex; align-items: center; gap: 6px;">
                        <span>📱</span>
                        <span>จำลองการโทรเข้า (Call Simulator)</span>
                    </div>
                    <div style="display: flex; flex-direction: column; gap: 10px;">
                        <div style="display: flex; flex-direction: column; gap: 4px;">
                            <label style="font-size: 11px; font-weight: 600; color: var(--text-muted);">👤 ชื่อผู้โทร (Caller Name):</label>
                            <input type="text" id="dialer-name" value="Vera Sun" placeholder="กรอกชื่อของคุณ" style="background: #ffffff; border: 1px solid var(--border-color); border-radius: 10px; padding: 8px 12px; color: #09090b; font-size: 13px; outline: none;">
                        </div>
                        <div style="display: flex; flex-direction: column; gap: 4px;">
                            <label style="font-size: 11px; font-weight: 600; color: var(--text-muted);">📞 เบอร์โทรศัพท์ (Phone Number):</label>
                            <input type="tel" id="dialer-phone" value="081-234-5678" placeholder="08X-XXX-XXXX" style="background: #ffffff; border: 1px solid var(--border-color); border-radius: 10px; padding: 8px 12px; color: #09090b; font-size: 13px; outline: none;">
                        </div>
                        <button id="dialer-start-btn" style="background: #18181b; border: none; color: white; font-weight: 600; font-size: 13px; padding: 12px; border-radius: 12px; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 8px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1); transition: all 0.2s ease; margin-top: 4px;">
                            <span>📞 กดเพื่อโทรออก (Call Now)</span>
                        </button>
                    </div>
                </div>

                <div class="visualizer-container">
                    <canvas id="waveform"></canvas>
                </div>

                <button class="avatar-button" id="avatar-btn">
                    <span class="avatar-icon" id="avatar-icon">📞</span>
                </button>

                <div class="status-text" id="status-text">เริ่มการทดสอบเสียง</div>
                <div class="status-subtitle" id="status-subtitle">คลิกวงกลมด้านบนเพื่อเริ่มเชื่อมต่อ</div>

                <!-- Live Chat & STT Transcript Box -->
                <div class="chat-box-container">
                    <div class="chat-header">
                        <span>💬 บทสนทนาสด (Live STT & Transcript)</span>
                        <span id="speaking-badge" class="speaking-badge" style="display:none;">🎤 พร้อมรับเสียง</span>
                    </div>
                    <div class="chat-messages" id="chat-messages">
                        <div class="chat-msg system">กดวงกลมเพื่อเริ่มเชื่อมต่อไมโครโฟน...</div>
                    </div>
                    <div class="chat-input-container">
                        <input type="text" id="chat-input" placeholder="พิมพ์ข้อความคุยกับ AI (เช่น ร้านเปิดกี่โมง)..." disabled>
                        <button id="send-btn" class="send-btn" disabled>ส่ง</button>
                    </div>
                </div>

                <div class="instruction-tip">
                    <span>🎧</span>
                    <span>แนะนำให้สวมหูฟังขณะสนทนา เพื่อความลื่นไหลและป้องกันเสียงสะท้อน</span>
                </div>
            </div>

            <!-- Right Panel: Info & Logs Tab Console -->
            <div class="card tab-card">
                <div class="tab-headers">
                    <button class="tab-btn active" data-tab="tab-faq">คลังความรู้บอท (RAG Context)</button>
                    <button class="tab-btn" data-tab="tab-console">บันทึกเหตุการณ์บอท (Live Console)</button>
                    <button class="tab-btn" data-tab="tab-manage">⚙️ จัดการฐานข้อมูล (RAG Admin)</button>
                    <button class="tab-btn" data-tab="tab-history">📜 ประวัติการโทร & การจอง</button>
                </div>

                <!-- Tab 1: FAQ / Knowledge Base -->
                <div class="tab-content active" id="tab-faq">
                    <div class="info-grid">
                        <div class="info-box">
                            <div class="info-label">เวลาเปิดทำการ</div>
                            <div class="info-value">{data.get('operating_hours')}</div>
                        </div>
                        <div class="info-box">
                            <div class="info-label">เบอร์ติดต่อพนักงาน</div>
                            <div class="info-value">{data.get('contact_number')}</div>
                        </div>
                        <div class="info-box" style="grid-column: span 2;">
                            <div class="info-label">ที่ตั้งร้าน</div>
                            <div class="info-value">{data.get('location')}</div>
                        </div>
                        <div class="info-box" style="grid-column: span 2;">
                            <div class="info-label">รหัส Wi-Fi</div>
                            <div class="info-value">{data.get('wifi_password')}</div>
                        </div>
                    </div>

                    <div class="info-box promos-box" style="margin-bottom: 20px;">
                        <div class="info-label">โปรโมชั่นของร้าน</div>
                        <ul>
                            {promos_html}
                        </ul>
                    </div>

                    <div class="faq-list">
                        {faq_html}
                    </div>
                </div>

                <!-- Tab 2: Logs Console -->
                <div class="tab-content" id="tab-console">
                    <div class="console" id="console">
                        <div class="console-line console-system">
                            <span class="console-time">[{datetime.datetime.now().strftime('%H:%M:%S')}]</span>
                            <span>System initialized. Click the Call button on the left to start sandbox.</span>
                        </div>
                    </div>
                </div>

                <!-- Tab 3: RAG Database Manager -->
                <div class="tab-content" id="tab-manage">
                    <div style="display: flex; flex-direction: column; gap: 16px;">
                        <div style="font-size: 13px; font-weight: 700; color: #09090b; display: flex; justify-content: space-between; align-items: center;">
                            <span>⚙️ แก้ไขฐานข้อมูลคลังความรู้บอท (data/knowledge.json)</span>
                            <span id="save-status-badge" style="font-size: 11px; padding: 4px 12px; border-radius: 12px; background: #10b981; color: #ffffff; font-weight: 600; display: none;">✓ บันทึกสำเร็จ</span>
                        </div>

                        <!-- General Info Form -->
                        <div style="background: #fafafa; border: 1px solid var(--border-color); border-radius: 14px; padding: 16px; display: flex; flex-direction: column; gap: 10px;">
                            <div style="font-size: 12px; font-weight: 700; color: #09090b;">📌 ข้อมูลทั่วไปของร้าน</div>
                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                                <div>
                                    <label style="font-size: 11px; font-weight: 600; color: var(--text-muted);">ชื่อร้าน/บริษัท:</label>
                                    <input type="text" id="edit-company" value="{data.get('company_name')}" style="width: 100%; background: #ffffff; border: 1px solid var(--border-color); border-radius: 8px; padding: 8px; color: #09090b; font-size: 12px; outline: none;">
                                </div>
                                <div>
                                    <label style="font-size: 11px; font-weight: 600; color: var(--text-muted);">เบอร์ติดต่อพนักงาน:</label>
                                    <input type="text" id="edit-contact" value="{data.get('contact_number')}" style="width: 100%; background: #ffffff; border: 1px solid var(--border-color); border-radius: 8px; padding: 8px; color: #09090b; font-size: 12px; outline: none;">
                                </div>
                            </div>
                            <div>
                                <label style="font-size: 11px; font-weight: 600; color: var(--text-muted);">เวลาเปิดทำการ:</label>
                                <input type="text" id="edit-hours" value="{data.get('operating_hours')}" style="width: 100%; background: #ffffff; border: 1px solid var(--border-color); border-radius: 8px; padding: 8px; color: #09090b; font-size: 12px; outline: none;">
                            </div>
                            <div>
                                <label style="font-size: 11px; font-weight: 600; color: var(--text-muted);">สถานที่ตั้งร้าน:</label>
                                <input type="text" id="edit-location" value="{data.get('location')}" style="width: 100%; background: #ffffff; border: 1px solid var(--border-color); border-radius: 8px; padding: 8px; color: #09090b; font-size: 12px; outline: none;">
                            </div>
                            <div>
                                <label style="font-size: 11px; font-weight: 600; color: var(--text-muted);">รหัส Wi-Fi:</label>
                                <input type="text" id="edit-wifi" value="{data.get('wifi_password')}" style="width: 100%; background: #ffffff; border: 1px solid var(--border-color); border-radius: 8px; padding: 8px; color: #09090b; font-size: 12px; outline: none;">
                            </div>
                        </div>

                        <!-- Promotions CRUD Manager -->
                        <div style="background: #fafafa; border: 1px solid var(--border-color); border-radius: 14px; padding: 16px;">
                            <div style="font-size: 12px; font-weight: 700; color: #09090b; margin-bottom: 10px;">🎁 โปรโมชั่นของร้าน</div>
                            <div id="promos-edit-list" style="display: flex; flex-direction: column; gap: 8px; margin-bottom: 12px;">
                                <!-- JS populates promo rows -->
                            </div>
                            <button id="add-promo-btn" style="background: #ffffff; border: 1px solid var(--border-color); color: #09090b; padding: 6px 12px; border-radius: 8px; font-size: 11px; font-weight: 600; cursor: pointer;">➕ เพิ่มโปรโมชั่น</button>
                        </div>

                        <!-- FAQ CRUD Manager -->
                        <div style="background: #fafafa; border: 1px solid var(--border-color); border-radius: 14px; padding: 16px;">
                            <div style="font-size: 12px; font-weight: 700; color: #09090b; margin-bottom: 10px;">❓ คำถามที่พบบ่อย (FAQ)</div>
                            <div id="faq-edit-list" style="display: flex; flex-direction: column; gap: 10px; margin-bottom: 12px;">
                                <!-- JS populates FAQ rows -->
                            </div>
                            <button id="add-faq-btn" style="background: #ffffff; border: 1px solid var(--border-color); color: #09090b; padding: 6px 12px; border-radius: 8px; font-size: 11px; font-weight: 600; cursor: pointer;">➕ เพิ่มคำถาม FAQ</button>
                        </div>

                        <!-- Save Button -->
                        <button id="save-knowledge-btn" style="background: #18181b; border: none; color: white; font-weight: 700; font-size: 13px; padding: 12px; border-radius: 12px; cursor: pointer; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1); transition: all 0.2s ease;">
                            💾 บันทึกฐานข้อมูลทั้งหมด (Save Changes)
                        </button>
                    </div>
                </div>

                <!-- Tab 4: Customer History & Reservations -->
                <div class="tab-content" id="tab-history">
                    <div style="display: flex; flex-direction: column; gap: 16px;">
                        <div style="font-size: 13px; font-weight: 700; color: #09090b; display: flex; justify-content: space-between; align-items: center;">
                            <span>📜 ประวัติความจำลูกค้าและการจอง (Customer Memory & Reservations)</span>
                            <button id="refresh-history-btn" style="background: #ffffff; border: 1px solid var(--border-color); color: #09090b; padding: 6px 12px; border-radius: 8px; font-size: 11px; font-weight: 600; cursor: pointer;">🔄 รีเฟรชข้อมูล</button>
                        </div>

                        <!-- Customer Memory Cards -->
                        <div style="background: #fafafa; border: 1px solid var(--border-color); border-radius: 14px; padding: 16px;">
                            <div style="font-size: 12px; font-weight: 700; color: #09090b; margin-bottom: 10px;">🧠 ประวัติความจำลูกค้า (Customer Memory Logs)</div>
                            <div id="customer-logs-list" style="display: flex; flex-direction: column; gap: 10px;">
                                <!-- JS populates logs -->
                            </div>
                        </div>

                        <!-- Reservations Table -->
                        <div style="background: #fafafa; border: 1px solid var(--border-color); border-radius: 14px; padding: 16px;">
                            <div style="font-size: 12px; font-weight: 700; color: #09090b; margin-bottom: 10px;">📅 รายการจองโต๊ะ / ห้องประชุม (Reservations)</div>
                            <div id="reservations-list" style="display: flex; flex-direction: column; gap: 10px;">
                                <!-- JS populates reservations -->
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </main>

        <!-- Call Transfer Simulator Modal -->
        <div class="modal-overlay" id="modal-overlay">
            <div class="modal">
                <div class="phone-animation">📞</div>
                <h2>โอนสายไปยังพนักงาน</h2>
                <p>Gemini Live ได้เรียกใช้ฟังก์ชัน <strong>transfer_call()</strong> สำเร็จ!<br>
                   หากอยู่ในระบบจริง สายจะถูกทำการโอนไปยังเบอร์ <strong>{data.get('contact_number')}</strong> ทันที</p>
                <button class="modal-btn" onclick="closeTransferModal()">ปิดหน้าต่างจำลอง</button>
            </div>
        </div>

        <!-- Inject Standalone Phone Simulator Component -->
        {phone_modal_html}

        <footer>
            DripAI Coffee & Space &copy; 2026. Powered by Google Gemini Live API.
        </footer>

        <script>
            // Console elements
            const consoleEl = document.getElementById('console');
            const chatMessages = document.getElementById('chat-messages');
            const chatInput = document.getElementById('chat-input');
            const sendBtn = document.getElementById('send-btn');
            const speakingBadge = document.getElementById('speaking-badge');
            let isReceivingAudio = false;
            let audioResetTimer = null;

            function escapeHtml(str) {{
                return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
            }}

            let activeUserMessageBody = null;
            let activeBotMessageBody = null;

            function addChatMessage(text, sender) {{
                if (!chatMessages) return;
                const msgDiv = document.createElement('div');
                msgDiv.className = `chat-msg ${{sender}}`;
                
                if (sender === 'user') {{
                    msgDiv.innerHTML = `<strong>👤 คุณ:</strong> <span class="user-text-body">${{escapeHtml(text)}}</span>`;
                }} else if (sender === 'bot') {{
                    msgDiv.innerHTML = `<strong>🤖 Gemini:</strong> <span class="bot-text-body">${{escapeHtml(text)}}</span>`;
                }} else {{
                    msgDiv.textContent = text;
                }}
                
                chatMessages.appendChild(msgDiv);
                chatMessages.scrollTop = chatMessages.scrollHeight;
                return msgDiv;
            }}

            function sendTextMessage() {{
                if (!chatInput) return;
                const val = chatInput.value.trim();
                if (val && ws && ws.readyState === WebSocket.OPEN) {{
                    ws.send(JSON.stringify({{ event: 'text', text: val }}));
                    addChatMessage(val, 'user');
                    log('👤 คุณ: ' + val, 'user');
                    chatInput.value = '';
                }}
            }}

            if (sendBtn) sendBtn.addEventListener('click', sendTextMessage);
            if (chatInput) {{
                chatInput.addEventListener('keypress', (e) => {{
                    if (e.key === 'Enter') sendTextMessage();
                }});
            }}
            
            function logRagMatch(query, section, content, file, method, duration_ms) {{
                const time = new Date().toLocaleTimeString();
                const container = document.createElement('div');
                container.className = 'console-rag';
                const speedTag = duration_ms ? `<span style="color:#10b981; font-weight:bold; margin-left:6px;">[${{duration_ms}}ms]</span>` : '';
                container.innerHTML = `
                    <div class="rag-header"><span class="console-time">[${{time}}]</span> 🧠 <strong>RAG KNOWLEDGE MATCHED</strong> ${{speedTag}}</div>
                    <div class="rag-body">
                        <div><span class="rag-tag">🔍 คำถามที่พบ:</span> "${{escapeHtml(query)}}"</div>
                        <div><span class="rag-tag">📁 ดึงจากหมวดหมู่:</span> <strong>${{escapeHtml(section)}}</strong></div>
                        <div><span class="rag-tag">📄 ข้อมูลในคลัง (RAG Content):</span> "${{escapeHtml(content)}}"</div>
                        <div><span class="rag-tag">⚡ วิธีการค้นหา:</span> <strong style="color:#10b981">${{escapeHtml(method || 'Vector RAG')}}</strong></div>
                        <div><span class="rag-tag">💾 ไฟล์แหล่งอ้างอิง:</span> <code style="color:#818cf8">${{escapeHtml(file)}}</code></div>
                    </div>
                `;
                consoleEl.appendChild(container);
                consoleEl.scrollTop = consoleEl.scrollHeight;
            }}

            function logToolExecution(tool, target, description) {{
                const time = new Date().toLocaleTimeString();
                const container = document.createElement('div');
                container.className = 'console-tool';
                container.innerHTML = `
                    <div class="tool-header"><span class="console-time">[${{time}}]</span> 📞 <strong>FUNCTION CALL EXECUTED: ${{escapeHtml(tool)}}()</strong></div>
                    <div class="tool-body">
                        <div><span class="tool-tag">🎯 เบอร์ปลายทาง:</span> <strong>${{escapeHtml(target)}}</strong></div>
                        <div><span class="tool-tag">📝 รายละเอียด:</span> ${{escapeHtml(description)}}</div>
                    </div>
                `;
                consoleEl.appendChild(container);
                consoleEl.scrollTop = consoleEl.scrollHeight;
            }}

            function log(message, type = 'system') {{
                const time = new Date().toLocaleTimeString();
                const line = document.createElement('div');
                line.className = `console-line console-${{type}}`;
                
                const timeSpan = document.createElement('span');
                timeSpan.className = 'console-time';
                timeSpan.textContent = `[${{time}}]`;
                
                const textSpan = document.createElement('span');
                textSpan.textContent = message;
                
                line.appendChild(timeSpan);
                line.appendChild(textSpan);
                consoleEl.appendChild(line);
                consoleEl.scrollTop = consoleEl.scrollHeight;
            }}

            // Latency Tracker & Milestone Instrumentation
            const latencyTracker = {{
                speechStart: null,
                speechEnd: null,
                geminiSend: null,
                geminiFirstResponse: null,
                firstAudio: null,
                playback: null,
                isSpeaking: false,
                silenceTimer: null,
                hasFirstResponseForTurn: false,
                hasFirstAudioForTurn: false,
                hasPlaybackForTurn: false,
                ragTime: 0
            }};

            function resetTurnMetrics() {{
                latencyTracker.speechStart = null;
                latencyTracker.speechEnd = null;
                latencyTracker.geminiSend = null;
                latencyTracker.geminiFirstResponse = null;
                latencyTracker.firstAudio = null;
                latencyTracker.playback = null;
                latencyTracker.hasFirstResponseForTurn = false;
                latencyTracker.hasFirstAudioForTurn = false;
                latencyTracker.hasPlaybackForTurn = false;
            }}

            function logMilestone(name, description, timeMs = null) {{
                const now = timeMs !== null ? timeMs : performance.now();
                const timeStr = new Date().toLocaleTimeString() + '.' + String(Math.floor(now % 1000)).padStart(3, '0');
                const relTime = latencyTracker.speechStart ? `+${{Math.round(now - latencyTracker.speechStart)}}ms` : '0ms';
                
                console.log(`⏱️ [MILESTONE] ${{name}} | Rel: ${{relTime}} | ${{description}}`);
                
                if (consoleEl) {{
                    const div = document.createElement('div');
                    div.className = 'console-milestone';
                    div.innerHTML = `
                        <span><strong>${{escapeHtml(name)}}</strong> - ${{escapeHtml(description)}}</span>
                        <span style="opacity:0.85; font-weight:bold;">${{escapeHtml(relTime)}} [${{timeStr}}]</span>
                    `;
                    consoleEl.appendChild(div);
                    consoleEl.scrollTop = consoleEl.scrollHeight;
                }}
            }}

            function renderLatencySummary() {{
                const lt = latencyTracker;
                if (!lt.speechEnd || !lt.playback) return;

                const vadWindowMs = lt.vadEnd && lt.speechEnd ? Math.max(0, Math.round(lt.vadEnd - lt.speechEnd)) : 600;
                const geminiNetLag = lt.geminiFirstResponse && lt.vadEnd ? Math.max(0, Math.round(lt.geminiFirstResponse - lt.vadEnd)) : 0;
                const audioGenLag = lt.firstAudio && lt.geminiFirstResponse ? Math.max(0, Math.round(lt.firstAudio - lt.geminiFirstResponse)) : 0;
                const browserPlaybackLag = lt.playback && lt.firstAudio ? Math.max(0, Math.round(lt.playback - lt.firstAudio)) : 0;
                const totalE2E = Math.max(0, Math.round(lt.playback - lt.speechEnd));
                const userSpeakDuration = lt.speechEnd && lt.speechStart ? Math.max(0, Math.round(lt.speechEnd - lt.speechStart)) : 0;

                // Identify primary bottleneck
                let bottleneck = "Gemini Model Inference / WebSocket";
                let maxVal = geminiNetLag;
                if (vadWindowMs > maxVal) {{ bottleneck = "VAD Silence Timeout / Hangover"; maxVal = vadWindowMs; }}
                if (audioGenLag > maxVal) {{ bottleneck = "Gemini Audio Packetization"; maxVal = audioGenLag; }}
                if (browserPlaybackLag > maxVal) {{ bottleneck = "Browser AudioContext Buffer Scheduling"; maxVal = browserPlaybackLag; }}

                if (consoleEl) {{
                    const card = document.createElement('div');
                    card.className = 'console-summary';
                    card.innerHTML = `
                        <div class="summary-title">📊 LATENCY BOTTLENECK ANALYSIS SUMMARY</div>
                        <div class="summary-row"><span>1. SPEECH START</span><span>0 ms</span></div>
                        <div class="summary-row"><span>2. SPEECH END</span><span>+${{userSpeakDuration}} ms (User spoke ${{userSpeakDuration}}ms)</span></div>
                        <div class="summary-row"><span>3. CLIENT VAD END (Silence Window)</span><span>+${{vadWindowMs}} ms</span></div>
                        <div class="summary-row"><span>4. SERVER & GEMINI INFERENCE</span><span>+${{geminiNetLag}} ms</span></div>
                        <div class="summary-row"><span>5. FIRST AUDIO (TTS Packetization)</span><span>+${{audioGenLag}} ms</span></div>
                        <div class="summary-row"><span>6. PLAYBACK (Browser AudioContext)</span><span>+${{browserPlaybackLag}} ms</span></div>
                        <div class="summary-row total"><span>⏱️ TOTAL TURNAROUND (SPEECH END -> PLAYBACK)</span><span>${{totalE2E}} ms (${{(totalE2E/1000).toFixed(2)}}s)</span></div>
                        <div style="margin-top:8px; font-size:11px; color:#fcd34d; background:rgba(245,158,11,0.1); padding:6px 10px; border-radius:6px; border:1px solid rgba(245,158,11,0.3);">🔍 BOTTLENECK CAUSE: <strong>${{escapeHtml(bottleneck)}}</strong> (${{maxVal}} ms)</div>
                    `;
                    consoleEl.appendChild(card);
                    consoleEl.scrollTop = consoleEl.scrollHeight;
                }}
            }}


            // Tabs switching
            const tabBtns = document.querySelectorAll('.tab-btn');
            const tabContents = document.querySelectorAll('.tab-content');

            tabBtns.forEach(btn => {{
                btn.addEventListener('click', () => {{
                    const tabId = btn.getAttribute('data-tab');
                    tabBtns.forEach(b => b.classList.remove('active'));
                    tabContents.forEach(c => c.classList.remove('active'));
                    
                    btn.classList.add('active');
                    document.getElementById(tabId).classList.add('active');
                }});
            }});

            // Audio & Connection
            let ws = null;
            let audioContext = null;
            let scriptNode = null;
            let micStream = null;
            let isConnected = false;
            
            // Audio Player
            class AudioPlayer {{
                constructor(sampleRate = 24000) {{
                    this.sampleRate = sampleRate;
                    this.audioCtx = null;
                    this.nextStartTime = 0;
                    this.activeSources = [];
                    this.onPlaybackStateChange = null;
                }}

                init(ctx = null) {{
                    if (ctx) {{
                        this.audioCtx = ctx;
                    }} else if (!this.audioCtx) {{
                        this.audioCtx = new (window.AudioContext || window.webkitAudioContext)({{ latencyHint: 'interactive' }});
                    }}
                    if (this.nextStartTime < this.audioCtx.currentTime) {{
                        this.nextStartTime = this.audioCtx.currentTime;
                    }}
                }}

                playChunk(pcm16Base64) {{
                    this.init();
                    if (this.audioCtx.state === 'suspended') {{
                        this.audioCtx.resume();
                    }}

                    const binaryString = window.atob(pcm16Base64);
                    const len = binaryString.length;
                    const bytes = new Uint8Array(len);
                    for (let i = 0; i < len; i++) {{
                        bytes[i] = binaryString.charCodeAt(i);
                    }}

                    const pcm16 = new Int16Array(bytes.buffer);
                    const float32 = new Float32Array(pcm16.length);
                    for (let i = 0; i < pcm16.length; i++) {{
                        float32[i] = pcm16[i] / 32768.0;
                    }}

                    const audioBuffer = this.audioCtx.createBuffer(1, float32.length, this.sampleRate);
                    audioBuffer.copyToChannel(float32, 0);

                    const source = this.audioCtx.createBufferSource();
                    source.buffer = audioBuffer;
                    source.connect(this.audioCtx.destination);

                    const currentTime = this.audioCtx.currentTime;
                    if (this.nextStartTime < currentTime) {{
                        this.nextStartTime = currentTime;
                    }}
                    
                    source.start(this.nextStartTime);
                    this.nextStartTime += audioBuffer.duration;
                    this.activeSources.push(source);
                    
                    if (this.onPlaybackStateChange) {{
                        this.onPlaybackStateChange(true);
                    }}

                    source.onended = () => {{
                        const idx = this.activeSources.indexOf(source);
                        if (idx > -1) this.activeSources.splice(idx, 1);
                        if (this.activeSources.length === 0 && this.onPlaybackStateChange) {{
                            this.onPlaybackStateChange(false);
                        }}
                    }};
                }}

                clear() {{
                    this.activeSources.forEach(source => {{
                        try {{
                            source.stop();
                        }} catch(e) {{}}
                    }});
                    this.activeSources = [];
                    if (this.audioCtx) {{
                        this.nextStartTime = this.audioCtx.currentTime;
                    }}
                    if (this.onPlaybackStateChange) {{
                        this.onPlaybackStateChange(false);
                    }}
                }}
            }}

            const player = new AudioPlayer(24000);
            
            // Waveform visualization
            const canvas = document.getElementById('waveform');
            const canvasCtx = canvas.getContext('2d');
            let animationId;
            let inputAnalyst = null;
            let outputAnalyst = null;

            function resizeCanvas() {{
                canvas.width = canvas.parentElement.clientWidth;
                canvas.height = canvas.parentElement.clientHeight;
            }}
            window.addEventListener('resize', resizeCanvas);
            resizeCanvas();

            function drawWave() {{
                animationId = requestAnimationFrame(drawWave);
                
                canvasCtx.fillStyle = '#0b0f19';
                canvasCtx.fillRect(0, 0, canvas.width, canvas.height);
                
                let dataArray = new Uint8Array(128);
                
                // Pick active analyst node
                let analyst = null;
                let strokeColor = '#6366f1';
                let glowColor = 'rgba(99, 102, 241, 0.5)';
                
                if (player.activeSources.length > 0 && outputAnalyst) {{
                    // Gemini is speaking
                    analyst = outputAnalyst;
                    strokeColor = '#10b981';
                    glowColor = 'rgba(16, 185, 129, 0.5)';
                }} else if (inputAnalyst) {{
                    // User is speaking / Mic active
                    analyst = inputAnalyst;
                    strokeColor = '#6366f1';
                    glowColor = 'rgba(99, 102, 241, 0.5)';
                }}
                
                if (analyst) {{
                    analyst.getByteTimeDomainData(dataArray);
                    
                    canvasCtx.lineWidth = 3;
                    canvasCtx.strokeStyle = strokeColor;
                    canvasCtx.shadowBlur = 10;
                    canvasCtx.shadowColor = glowColor;
                    canvasCtx.beginPath();
                    
                    let sliceWidth = canvas.width * 1.0 / dataArray.length;
                    let x = 0;
                    
                    for (let i = 0; i < dataArray.length; i++) {{
                        let v = dataArray[i] / 128.0;
                        let y = v * canvas.height / 2;
                        
                        if (i === 0) {{
                            canvasCtx.moveTo(x, y);
                        }} else {{
                            canvasCtx.lineTo(x, y);
                        }}
                        
                        x += sliceWidth;
                    }}
                    
                    canvasCtx.lineTo(canvas.width, canvas.height / 2);
                    canvasCtx.stroke();
                    canvasCtx.shadowBlur = 0; // reset
                }} else {{
                    // Draw a flat line
                    canvasCtx.lineWidth = 1;
                    canvasCtx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
                    canvasCtx.beginPath();
                    canvasCtx.moveTo(0, canvas.height / 2);
                    canvasCtx.lineTo(canvas.width, canvas.height / 2);
                    canvasCtx.stroke();
                }}
            }}

            // Knowledge Base Admin Manager JS
            let currentKnowledgeData = null;

            async function loadKnowledgeAdmin() {{
                try {{
                    const res = await fetch('/api/knowledge');
                    const json = await res.json();
                    if (json.status === 'success') {{
                        currentKnowledgeData = json.data;
                        renderKnowledgeAdmin();
                    }}
                }} catch (e) {{
                    console.error('Failed to load knowledge:', e);
                }}
            }}

            function renderKnowledgeAdmin() {{
                if (!currentKnowledgeData) return;
                
                // Set Inputs
                document.getElementById('edit-company').value = currentKnowledgeData.company_name || '';
                document.getElementById('edit-contact').value = currentKnowledgeData.contact_number || '';
                document.getElementById('edit-hours').value = currentKnowledgeData.operating_hours || '';
                document.getElementById('edit-location').value = currentKnowledgeData.location || '';
                document.getElementById('edit-wifi').value = currentKnowledgeData.wifi_password || '';

                // Render Promotions
                const promosContainer = document.getElementById('promos-edit-list');
                if (promosContainer) {{
                    promosContainer.innerHTML = '';
                    (currentKnowledgeData.promotions || []).forEach((promo, idx) => {{
                        const row = document.createElement('div');
                        row.style.cssText = 'display: grid; grid-template-columns: 1fr 2fr auto; gap: 8px; align-items: center; background: #ffffff; padding: 8px; border-radius: 8px; border: 1px solid var(--border-color);';
                        row.innerHTML = `
                            <input type="text" value="${{escapeHtml(promo.name)}}" data-promo-idx="${{idx}}" data-field="name" class="promo-input" style="background:#ffffff; border:1px solid var(--border-color); border-radius:6px; padding:6px; color:#09090b; font-size:12px; outline:none;">
                            <input type="text" value="${{escapeHtml(promo.detail)}}" data-promo-idx="${{idx}}" data-field="detail" class="promo-input" style="background:#ffffff; border:1px solid var(--border-color); border-radius:6px; padding:6px; color:#09090b; font-size:12px; outline:none;">
                            <button onclick="deletePromo(${{idx}})" style="background:#fee2e2; border:1px solid #fca5a5; color:#ef4444; padding:6px 10px; border-radius:6px; font-size:11px; font-weight:600; cursor:pointer;">🗑️ ลบ</button>
                        `;
                        promosContainer.appendChild(row);
                    }});
                }}

                // Render FAQ
                const faqContainer = document.getElementById('faq-edit-list');
                if (faqContainer) {{
                    faqContainer.innerHTML = '';
                    (currentKnowledgeData.faq || []).forEach((item, idx) => {{
                        const box = document.createElement('div');
                        box.style.cssText = 'display: flex; flex-direction: column; gap: 6px; background: #ffffff; padding: 10px; border-radius: 8px; border: 1px solid var(--border-color);';
                        box.innerHTML = `
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span style="font-size: 11px; color: #09090b; font-weight: 700;">คำถามที่ ${{idx + 1}}</span>
                                <button onclick="deleteFaq(${{idx}})" style="background:#fee2e2; border:1px solid #fca5a5; color:#ef4444; padding:4px 8px; border-radius:6px; font-size:11px; font-weight:600; cursor:pointer;">🗑️ ลบ</button>
                            </div>
                            <input type="text" value="${{escapeHtml(item.question)}}" data-faq-idx="${{idx}}" data-field="question" class="faq-input" placeholder="คำถาม" style="background:#ffffff; border:1px solid var(--border-color); border-radius:6px; padding:6px; color:#09090b; font-size:12px; outline:none;">
                            <textarea data-faq-idx="${{idx}}" data-field="answer" class="faq-input" placeholder="คำตอบ" style="background:#ffffff; border:1px solid var(--border-color); border-radius:6px; padding:6px; color:#09090b; font-size:12px; outline:none; rows: 2;">${{escapeHtml(item.answer)}}</textarea>
                        `;
                        faqContainer.appendChild(box);
                    }});
                }}
            }}

            window.deletePromo = function(idx) {{
                if (!currentKnowledgeData) return;
                currentKnowledgeData.promotions.splice(idx, 1);
                renderKnowledgeAdmin();
            }};

            window.deleteFaq = function(idx) {{
                if (!currentKnowledgeData) return;
                currentKnowledgeData.faq.splice(idx, 1);
                renderKnowledgeAdmin();
            }};

            // Add promo button
            const addPromoBtn = document.getElementById('add-promo-btn');
            if (addPromoBtn) {{
                addPromoBtn.addEventListener('click', () => {{
                    if (!currentKnowledgeData) currentKnowledgeData = {{ promotions: [] }};
                    if (!currentKnowledgeData.promotions) currentKnowledgeData.promotions = [];
                    currentKnowledgeData.promotions.push({{ name: 'โปรโมชั่นใหม่', detail: 'รายละเอียดโปรโมชั่น...' }});
                    renderKnowledgeAdmin();
                }});
            }}

            // Add FAQ button
            const addFaqBtn = document.getElementById('add-faq-btn');
            if (addFaqBtn) {{
                addFaqBtn.addEventListener('click', () => {{
                    if (!currentKnowledgeData) currentKnowledgeData = {{ faq: [] }};
                    if (!currentKnowledgeData.faq) currentKnowledgeData.faq = [];
                    currentKnowledgeData.faq.push({{ question: 'คำถามใหม่?', answer: 'รายละเอียดคำตอบ...' }});
                    renderKnowledgeAdmin();
                }});
            }}

            // Save knowledge button
            const saveKnowledgeBtn = document.getElementById('save-knowledge-btn');
            if (saveKnowledgeBtn) {{
                saveKnowledgeBtn.addEventListener('click', async () => {{
                    if (!currentKnowledgeData) return;
                    
                    // Collect current form inputs
                    currentKnowledgeData.company_name = document.getElementById('edit-company').value.trim();
                    currentKnowledgeData.contact_number = document.getElementById('edit-contact').value.trim();
                    currentKnowledgeData.operating_hours = document.getElementById('edit-hours').value.trim();
                    currentKnowledgeData.location = document.getElementById('edit-location').value.trim();
                    currentKnowledgeData.wifi_password = document.getElementById('edit-wifi').value.trim();

                    // Collect promotions
                    const promoInputs = document.querySelectorAll('.promo-input');
                    promoInputs.forEach(inp => {{
                        const idx = parseInt(inp.getAttribute('data-promo-idx'));
                        const field = inp.getAttribute('data-field');
                        if (currentKnowledgeData.promotions[idx]) {{
                            currentKnowledgeData.promotions[idx][field] = inp.value.trim();
                        }}
                    }});

                    // Collect FAQs
                    const faqInputs = document.querySelectorAll('.faq-input');
                    faqInputs.forEach(inp => {{
                        const idx = parseInt(inp.getAttribute('data-faq-idx'));
                        const field = inp.getAttribute('data-field');
                        if (currentKnowledgeData.faq[idx]) {{
                            currentKnowledgeData.faq[idx][field] = inp.value.trim();
                        }}
                    }});

                    try {{
                        const res = await fetch('/api/knowledge', {{
                            method: 'POST',
                            headers: {{ 'Content-Type': 'application/json' }},
                            body: JSON.stringify(currentKnowledgeData)
                        }});
                        const resJson = await res.json();
                        if (resJson.status === 'success') {{
                            const badge = document.getElementById('save-status-badge');
                            if (badge) {{
                                badge.style.display = 'inline-block';
                                setTimeout(() => {{ badge.style.display = 'none'; }}, 3000);
                            }}
                            log('💾 บันทึกฐานข้อมูลคลังความรู้บอท (data/knowledge.json) สำเร็จ!', 'system');
                        }} else {{
                            alert('เกิดข้อผิดพลาดในการบันทึก: ' + resJson.message);
                        }}
                    }} catch (err) {{
                        alert('เกิดข้อผิดพลาดในการเชื่อมต่อบันทึกฐานข้อมูล: ' + err);
                    }}
                }});
            }}

            loadKnowledgeAdmin();

            // Connect to WebSocket
            const avatarBtn = document.getElementById('avatar-btn');
            const avatarIcon = document.getElementById('avatar-icon');
            const statusText = document.getElementById('status-text');
            const statusSubtitle = document.getElementById('status-subtitle');
            const modal = document.getElementById('modal-overlay');

            player.onPlaybackStateChange = (isPlaying) => {{
                if (isConnected) {{
                    if (isPlaying) {{
                        avatarBtn.className = 'avatar-button connected speaking';
                        avatarIcon.textContent = '🔊';
                        statusText.textContent = 'AI กำลังอธิบาย...';
                    }} else {{
                        avatarBtn.className = 'avatar-button connected';
                        avatarIcon.textContent = '🎤';
                        statusText.textContent = 'ระบบพร้อมใช้งาน';
                    }}
                }}
            }};

            let callTimerInterval = null;
            let callSeconds = 0;
            let isMuted = false;

            function startCallTimer() {{
                callSeconds = 0;
                const timerEl = document.getElementById('phone-call-timer');
                if (timerEl) timerEl.textContent = '00:00';
                clearInterval(callTimerInterval);
                callTimerInterval = setInterval(() => {{
                    callSeconds++;
                    const mins = String(Math.floor(callSeconds / 60)).padStart(2, '0');
                    const secs = String(callSeconds % 60).padStart(2, '0');
                    if (timerEl) timerEl.textContent = `${{mins}}:${{secs}}`;
                }}, 1000);
            }}

            function stopCallTimer() {{
                clearInterval(callTimerInterval);
            }}

            function openPhoneModal(name) {{
                const callerNameEl = document.getElementById('phone-caller-name');
                if (callerNameEl) callerNameEl.textContent = name || 'Vera Sun';
                const modal = document.getElementById('phone-modal-overlay');
                if (modal) modal.classList.add('active');
                if (!callTimerInterval) startCallTimer();
            }}

            function closePhoneModal() {{
                const modal = document.getElementById('phone-modal-overlay');
                if (modal) modal.classList.remove('active');
            }}

            // Minimize Phone Modal Button Event
            const phoneMinimizeBtn = document.getElementById('phone-minimize-btn');
            if (phoneMinimizeBtn) {{
                phoneMinimizeBtn.addEventListener('click', () => {{
                    closePhoneModal();
                }});
            }}

            // Click outside phone shell (on backdrop) to minimize/close
            const phoneOverlay = document.getElementById('phone-modal-overlay');
            if (phoneOverlay) {{
                phoneOverlay.addEventListener('click', (e) => {{
                    if (e.target === phoneOverlay) {{
                        closePhoneModal();
                    }}
                }});
            }}

            // Dialer Call Button Event
            const dialerStartBtn = document.getElementById('dialer-start-btn');
            if (dialerStartBtn) {{
                dialerStartBtn.addEventListener('click', () => {{
                    const nameInput = document.getElementById('dialer-name');
                    const name = nameInput ? nameInput.value.trim() : 'Vera Sun';
                    openPhoneModal(name);
                    if (!isConnected) {{
                        connect();
                    }}
                }});
            }}

            // Phone Screen Hangup Button Event
            const phoneHangupBtn = document.getElementById('phone-hangup-btn');
            if (phoneHangupBtn) {{
                phoneHangupBtn.addEventListener('click', () => {{
                    closePhoneModal();
                    stopCallTimer();
                    callTimerInterval = null;
                    if (isConnected) {{
                        disconnect();
                    }}
                }});
            }}

            // Phone Screen Mute Button Toggle
            const btnPhoneMute = document.getElementById('btn-phone-mute');
            if (btnPhoneMute) {{
                btnPhoneMute.addEventListener('click', () => {{
                    isMuted = !isMuted;
                    const labelMute = document.getElementById('label-phone-mute');
                    if (isMuted) {{
                        btnPhoneMute.classList.add('active');
                        btnPhoneMute.textContent = '🔇';
                        if (labelMute) labelMute.textContent = 'เปิดเสียง';
                        log('Microphone muted.', 'system');
                    }} else {{
                        btnPhoneMute.classList.remove('active');
                        btnPhoneMute.textContent = '🎙️';
                        if (labelMute) labelMute.textContent = 'ปิดเสียง';
                        log('Microphone unmuted.', 'system');
                    }}
                }});
            }}

            avatarBtn.addEventListener('click', toggleConnection);

            function toggleConnection() {{
                if (isConnected) {{
                    closePhoneModal();
                    disconnect();
                }} else {{
                    const nameInput = document.getElementById('dialer-name');
                    const name = nameInput ? nameInput.value.trim() : 'Vera Sun';
                    openPhoneModal(name);
                    connect();
                }}
            }}

            function connect() {{
                avatarBtn.className = 'avatar-button connecting';
                avatarIcon.textContent = '⏳';
                statusText.textContent = 'กำลังสร้างการเชื่อมต่อ...';
                log('Connecting to WebSocket server...', 'system');

                // Request microphone permission
                navigator.mediaDevices.getUserMedia({{ 
                    audio: {{ 
                        channelCount: 1, 
                        echoCancellation: true, 
                        noiseSuppression: true 
                    }} 
                }})
                .then(stream => {{
                    micStream = stream;
                    
                    // Build WebSocket URL
                    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                    const wsUrl = `${{protocol}}//${{window.location.host}}/local-stream`;
                    ws = new WebSocket(wsUrl);
                    
                    ws.onopen = () => {{
                        isConnected = true;
                        avatarBtn.className = 'avatar-button connected';
                        avatarIcon.textContent = '🎤';
                        statusText.textContent = 'กำลังโหลดคำสั่งบอท...';
                        log('Connected to server. Initializing audio...', 'system');
                        
                        const nameInp = document.getElementById('dialer-name');
                        const phoneInp = document.getElementById('dialer-phone');
                        const cName = nameInp ? nameInp.value.trim() : 'Vera Sun';
                        const cPhone = phoneInp ? phoneInp.value.trim() : '081-234-5678';
                        ws.send(JSON.stringify({{ event: 'setup', name: cName, phone: cPhone }}));

                        // Initialize Audio Context for recording and playback with low latency
                        audioContext = new (window.AudioContext || window.webkitAudioContext)({{ latencyHint: 'interactive' }});
                        
                        // Setup Input Analyst for Mic visualizer
                        inputAnalyst = audioContext.createAnalyser();
                        inputAnalyst.fftSize = 256;
                        const source = audioContext.createMediaStreamSource(stream);
                        source.connect(inputAnalyst);
                        
                        // Setup Output Analyst (for speaker visualization)
                        outputAnalyst = audioContext.createAnalyser();
                        outputAnalyst.fftSize = 256;
                        outputAnalyst.connect(audioContext.destination);
                        
                        // Modify Player: feed audio output through Output Analyst
                        player.init(audioContext);
                        player.playChunk = (pcm16Base64) => {{
                            player.init(audioContext);
                            if (player.audioCtx.state === 'suspended') {{
                                player.audioCtx.resume();
                            }}

                            if (!latencyTracker.hasPlaybackForTurn) {{
                                latencyTracker.hasPlaybackForTurn = true;
                                latencyTracker.playback = performance.now();
                                logMilestone("🔊 PLAYBACK", "Audio playback initiated on browser speakers (AudioContext)");
                                renderLatencySummary();
                            }}

                            const binaryString = window.atob(pcm16Base64);
                            const len = binaryString.length;
                            const bytes = new Uint8Array(len);
                            for (let i = 0; i < len; i++) {{
                                bytes[i] = binaryString.charCodeAt(i);
                            }}

                            const pcm16 = new Int16Array(bytes.buffer);
                            const float32 = new Float32Array(pcm16.length);
                            for (let i = 0; i < pcm16.length; i++) {{
                                float32[i] = pcm16[i] / 32768.0;
                            }}

                            const audioBuffer = player.audioCtx.createBuffer(1, float32.length, player.sampleRate);
                            audioBuffer.copyToChannel(float32, 0);

                            const bufferSource = player.audioCtx.createBufferSource();
                            bufferSource.buffer = audioBuffer;
                            
                            bufferSource.connect(outputAnalyst);

                            const currentTime = player.audioCtx.currentTime;
                            if (player.nextStartTime < currentTime) {{
                                player.nextStartTime = currentTime;
                            }}
                            
                            bufferSource.start(player.nextStartTime);
                            player.nextStartTime += audioBuffer.duration;
                            player.activeSources.push(bufferSource);
                            
                            if (player.onPlaybackStateChange) {{
                                player.onPlaybackStateChange(true);
                            }}

                            bufferSource.onended = () => {{
                                const idx = player.activeSources.indexOf(bufferSource);
                                if (idx > -1) player.activeSources.splice(idx, 1);
                                if (player.activeSources.length === 0 && player.onPlaybackStateChange) {{
                                    player.onPlaybackStateChange(false);
                                }}
                            }};
                        }};

                        let lastSpeechTimestamp = 0;
                        let consecutiveSpeechFrames = 0;
                        let postSpeechSendUntil = 0; // Timestamp: keep sending audio until this time after speech ends
                        let turnPending = false; // Prevent overlapping turns

                        // Recorder Process Node (ScriptProcessorNode) - 1024 buffer size for 20ms ultra-low latency
                        scriptNode = audioContext.createScriptProcessor(1024, 1, 1);
                        source.connect(scriptNode);
                        scriptNode.connect(audioContext.destination);
                        
                        scriptNode.onaudioprocess = (e) => {{
                            if (isMuted) return;
                            if (ws && ws.readyState === WebSocket.OPEN) {{
                                const inputData = e.inputBuffer.getChannelData(0);
                                
                                // Calculate RMS Noise Gate
                                let sum = 0;
                                for (let i = 0; i < inputData.length; i++) {{
                                    sum += inputData[i] * inputData[i];
                                }}
                                const rms = Math.sqrt(sum / inputData.length);
                                const now = performance.now();

                                const isBotPlaying = (player && player.activeSources && player.activeSources.length > 0);
                                const SPEECH_THRESHOLD = isBotPlaying ? 0.08 : 0.02;
                                if (rms > SPEECH_THRESHOLD) {{
                                    consecutiveSpeechFrames++;
                                    lastSpeechTimestamp = now;
                                    // Reset trailing timer when user resumes speaking
                                    postSpeechSendUntil = 0;
                                    // Require sustained speech (> 60ms / 3 consecutive frames) to trigger turn start & barge-in
                                    if (!latencyTracker.isSpeaking && consecutiveSpeechFrames >= 3) {{
                                        latencyTracker.isSpeaking = true;
                                        // Instant Local Barge-in: Clear player speakers when sustained speech detected
                                        if (player && player.activeSources && player.activeSources.length > 0) {{
                                            player.clear();
                                            if (ws && ws.readyState === WebSocket.OPEN) {{
                                                ws.send(JSON.stringify({{ event: 'clear', reason: 'barge_in' }}));
                                            }}
                                            log('🎙️ Sustained Speech Interruption: Stopped AI playback on user speech start', 'system');
                                        }}
                                        // Only create new turn if no pending turn waiting for Gemini response
                                        if (!turnPending) {{
                                            resetTurnMetrics();
                                            latencyTracker.speechStart = now - 60;
                                            turnPending = true;
                                            if (ws && ws.readyState === WebSocket.OPEN) {{
                                                ws.send(JSON.stringify({{ event: 'turn_start' }}));
                                            }}
                                            logMilestone("🎙️ SPEECH START", `User started speaking (sustained speech > 60ms, RMS > ${{SPEECH_THRESHOLD}})`);
                                        }}
                                    }}
                                    if (latencyTracker.silenceTimer) {{
                                        clearTimeout(latencyTracker.silenceTimer);
                                        latencyTracker.silenceTimer = null;
                                    }}
                                }} else {{
                                    consecutiveSpeechFrames = 0;
                                    if (latencyTracker.isSpeaking && !latencyTracker.silenceTimer) {{
                                        // Silence detected: optimized VAD hangover window (300ms)
                                        latencyTracker.silenceTimer = setTimeout(() => {{
                                            const silenceNow = performance.now();
                                            latencyTracker.isSpeaking = false;
                                            latencyTracker.speechEnd = silenceNow - 300;
                                            latencyTracker.vadEnd = silenceNow;
                                            logMilestone("⏹️ SPEECH END", "Silence detected for 300ms hangover window");
                                            logMilestone("⏹️ CLIENT VAD END", "Browser detected 300ms silence");

                                            if (ws && ws.readyState === WebSocket.OPEN) {{
                                                ws.send(JSON.stringify({{
                                                    event: 'vad_end',
                                                    timestamp: silenceNow
                                                }}));
                                            }}
                                            // Start trailing silence window: send 2 more seconds of silence frames
                                            // so Gemini Native VAD can confirm end-of-speech
                                            postSpeechSendUntil = silenceNow + 2000;
                                            latencyTracker.silenceTimer = null;
                                        }}, 300);

                                    }}
                                }}
                                
                                // Smart Trailing Silence Gate:
                                // Send audio during: (1) active speech, (2) VAD hangover, (3) 2s post-speech trailing
                                // Stop sending after trailing window expires to prevent Context Bloat
                                const inTrailingWindow = postSpeechSendUntil > 0 && now < postSpeechSendUntil;
                                const shouldSendAudio = latencyTracker.isSpeaking || latencyTracker.silenceTimer || inTrailingWindow;
                                if (shouldSendAudio) {{
                                    const resampled = downsampleBuffer(inputData, audioContext.sampleRate, 16000);
                                    const pcm16 = floatTo16BitPCM(resampled);
                                    const base64 = arrayBufferToBase64(pcm16);
                                    ws.send(JSON.stringify({{ event: 'audio', data: base64 }}));
                                }}
                            }}
                        }};
                        
                        drawWave();
                    }};
                    
                    ws.onmessage = (event) => {{
                        const msg = JSON.parse(event.data);
                        const phonePreview = document.getElementById('phone-chat-preview');
                        
                        if (msg.event === 'status') {{
                            log(msg.text, 'system');
                            if (msg.text.includes('Ready to chat')) {{
                                statusText.textContent = 'คุยหรือพิมพ์กับ AI ได้เลยครับ';
                                statusSubtitle.textContent = 'พูดใส่ไมค์ หรือพิมพ์ข้อความด้านล่าง';
                                if (chatInput) chatInput.disabled = false;
                                if (sendBtn) sendBtn.disabled = false;
                                if (speakingBadge) speakingBadge.style.display = 'inline-block';
                                addChatMessage('พร้อมรับฟังและตอบคำถามแล้วครับ...', 'system');
                                if (phonePreview) phonePreview.textContent = '🤖 Gemini: พร้อมรับสายแล้วครับ...';
                            }}
                        }} else if (msg.event === 'text') {{
                            activeUserMessageBody = null; // Reset user active bubble when bot speaks
                            if (!latencyTracker.hasFirstResponseForTurn) {{
                                latencyTracker.hasFirstResponseForTurn = true;
                                latencyTracker.geminiFirstResponse = performance.now();
                                logMilestone("📥 GEMINI FIRST RESPONSE", "First text/content response received from Gemini Live API");
                            }}
                            if (!activeBotMessageBody) {{
                                const msgDiv = addChatMessage(msg.text, 'bot');
                                activeBotMessageBody = msgDiv ? msgDiv.querySelector('.bot-text-body') : null;
                            }} else {{
                                const currentText = activeBotMessageBody.textContent.trim();
                                if (msg.text.startsWith(currentText) && currentText !== "") {{
                                    activeBotMessageBody.textContent = msg.text;
                                }} else {{
                                    activeBotMessageBody.textContent += msg.text;
                                }}
                            }}
                            log('🤖 Gemini: ' + msg.text, 'gemini');
                            if (phonePreview && activeBotMessageBody) phonePreview.textContent = '🤖 Gemini: ' + activeBotMessageBody.textContent;
                        }} else if (msg.event === 'rag_info') {{
                            logRagMatch(msg.query, msg.section, msg.content, msg.file, msg.method, msg.duration_ms);
                        }} else if (msg.event === 'tool_info') {{
                            logToolExecution(msg.tool, msg.target, msg.description);
                            if (typeof loadCustomerHistory === 'function') loadCustomerHistory();
                        }} else if (msg.event === 'audio') {{
                            if (!latencyTracker.hasFirstResponseForTurn) {{
                                latencyTracker.hasFirstResponseForTurn = true;
                                latencyTracker.geminiFirstResponse = performance.now();
                                logMilestone("📥 GEMINI FIRST RESPONSE", "First message frame received from Gemini Live API");
                            }}
                            if (!latencyTracker.hasFirstAudioForTurn) {{
                                latencyTracker.hasFirstAudioForTurn = true;
                                latencyTracker.firstAudio = performance.now();
                                logMilestone("🎵 FIRST AUDIO", "First 24kHz PCM audio packet received");
                            }}
                            player.playChunk(msg.data);
                            if (!isReceivingAudio) {{
                                isReceivingAudio = true;
                                const latency = latencyTracker.speechEnd ? Math.round(performance.now() - latencyTracker.speechEnd) : 180;
                                log(`🔊 [AI AUDIO STREAM] Gemini สตรีมเสียงสด (Latency: ${{latency}}ms, 24kHz PCM)...`, 'gemini');
                                if (phonePreview) phonePreview.textContent = '🔊 Gemini: กำลังพูดตอบกลับ...';
                            }}
                            clearTimeout(audioResetTimer);
                            audioResetTimer = setTimeout(() => {{
                                isReceivingAudio = false;
                            }}, 2000);
                        }} else if (msg.event === 'turn_complete') {{
                            latencyTracker.geminiTurnComplete = performance.now();
                            turnPending = false;
                            activeBotMessageBody = null; // Next response starts a new bubble
                            activeUserMessageBody = null; // Reset user active bubble for the next turn
                            logMilestone("🏁 GEMINI TURN COMPLETE", "Gemini Live API marked turnComplete=true");
                        }} else if (msg.event === 'user_transcript') {{
                            activeBotMessageBody = null; // Reset bot active bubble when user speaks
                            if (!activeUserMessageBody) {{
                                const msgDiv = addChatMessage(msg.text, 'user');
                                activeUserMessageBody = msgDiv ? msgDiv.querySelector('.user-text-body') : null;
                            }} else {{
                                const currentText = activeUserMessageBody.textContent.trim();
                                if (msg.text.startsWith(currentText) && currentText !== "") {{
                                    activeUserMessageBody.textContent = msg.text;
                                }} else {{
                                    activeUserMessageBody.textContent += (msg.text.startsWith(' ') || currentText.endsWith(' ') ? '' : ' ') + msg.text;
                                }}
                            }}
                            if (phonePreview && activeUserMessageBody) phonePreview.textContent = '🎤 ลูกค้า: ' + activeUserMessageBody.textContent;
                        }} else if (msg.event === 'ai_transcript') {{
                            activeUserMessageBody = null; // Reset user active bubble when bot speaks
                            if (!latencyTracker.hasFirstResponseForTurn) {{
                                latencyTracker.hasFirstResponseForTurn = true;
                                latencyTracker.geminiFirstResponse = performance.now();
                                logMilestone("📥 GEMINI FIRST RESPONSE", "First AI transcript response received");
                            }}
                            if (!activeBotMessageBody) {{
                                const msgDiv = addChatMessage(msg.text, 'bot');
                                activeBotMessageBody = msgDiv ? msgDiv.querySelector('.bot-text-body') : null;
                            }} else {{
                                const currentText = activeBotMessageBody.textContent.trim();
                                if (msg.text.startsWith(currentText) && currentText !== "") {{
                                    activeBotMessageBody.textContent = msg.text;
                                }} else {{
                                    activeBotMessageBody.textContent += msg.text;
                                }}
                            }}
                            log('🤖 Gemini: ' + msg.text, 'gemini');
                            if (phonePreview && activeBotMessageBody) phonePreview.textContent = '🤖 Gemini: ' + activeBotMessageBody.textContent;
                        }} else if (msg.event === 'clear') {{
                            activeBotMessageBody = null;
                            activeUserMessageBody = null;
                            if (msg.reason === 'tool_call') {{
                                log('🛠️ Gemini Live: กำลังเรียกใช้ Tool / ค้นหาข้อมูล...', 'tool');
                            }} else {{
                                log('Detected user barge-in! Stopping bot playback.', 'system');
                                player.clear();
                            }}
                        }} else if (msg.event === 'end_call') {{
                            log('Gemini Live: end_call() invoked. วางสายอัตโนมัติเรียบร้อยแล้ว.', 'system');
                            closePhoneModal();
                            stopCallTimer();
                            callTimerInterval = null;
                            if (isConnected) disconnect();
                        }} else if (msg.event === 'transfer') {{
                            log('Gemini Live: transfer_call() invoked!', 'tool');
                            showTransferModal();
                        }}
                    }};
                    
                    ws.onclose = () => {{
                        log('WebSocket connection closed.', 'system');
                        disconnect();
                    }};
                    
                    ws.onerror = (err) => {{
                        log(`WebSocket error: ${{err.message || 'unknown'}}`, 'system');
                        disconnect();
                    }};
                }})
                .catch(err => {{
                    log(`Microphone permission denied: ${{err}}`, 'system');
                    disconnect();
                    alert('กรุณาอนุญาตการใช้งานไมโครโฟนเพื่อคุยกับ AI ครับ');
                }});
            }}

            function disconnect() {{
                isConnected = false;
                if (chatInput) chatInput.disabled = true;
                if (sendBtn) sendBtn.disabled = true;
                if (speakingBadge) speakingBadge.style.display = 'none';

                if (ws) {{
                    try {{ ws.close(); }} catch(e) {{}}
                    ws = null;
                }}
                
                if (scriptNode) {{
                    try {{ scriptNode.disconnect(); }} catch(e) {{}}
                    scriptNode = null;
                }}
                
                if (micStream) {{
                    try {{ micStream.getTracks().forEach(track => track.stop()); }} catch(e) {{}}
                    micStream = null;
                }}
                
                if (audioContext) {{
                    try {{ audioContext.close(); }} catch(e) {{}}
                    audioContext = null;
                }}
                
                player.clear();
                cancelAnimationFrame(animationId);
                
                avatarBtn.className = 'avatar-button';
                avatarIcon.textContent = '📞';
                statusText.textContent = 'เริ่มการทดสอบเสียง';
                statusSubtitle.textContent = 'คลิกวงกลมด้านบนเพื่อเริ่มเชื่อมต่อ';
                log('Disconnected.', 'system');
            }}

            function showTransferModal() {{
                modal.classList.add('active');
                disconnect();
            }}

            function closeTransferModal() {{
                modal.classList.remove('active');
            }}

            // Audio Resampling Utilities
            function downsampleBuffer(buffer, inputSampleRate, outputSampleRate) {{
                if (inputSampleRate === outputSampleRate) {{
                    return buffer;
                }}
                const sampleRateRatio = inputSampleRate / outputSampleRate;
                const newLength = Math.round(buffer.length / sampleRateRatio);
                const result = new Float32Array(newLength);
                let offsetResult = 0;
                let offsetBuffer = 0;
                while (offsetResult < result.length) {{
                    const nextOffsetBuffer = Math.round((offsetResult + 1) * sampleRateRatio);
                    let accum = 0, count = 0;
                    for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i++) {{
                        accum += buffer[i];
                        count++;
                    }}
                    result[offsetResult] = accum / count;
                    offsetResult++;
                    offsetBuffer = nextOffsetBuffer;
                }}
                return result;
            }}

            function floatTo16BitPCM(float32Array) {{
                const buffer = new ArrayBuffer(float32Array.length * 2);
                const view = new DataView(buffer);
                let offset = 0;
                for (let i = 0; i < float32Array.length; i++, offset += 2) {{
                    let s = Math.max(-1, Math.min(1, float32Array[i]));
                    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
                }}
                return buffer;
            }}

            function arrayBufferToBase64(buffer) {{
                let binary = '';
                const bytes = new Uint8Array(buffer);
                const len = bytes.byteLength;
                for (let i = 0; i < len; i++) {{
                    binary += String.fromCharCode(bytes[i]);
                }}
                return window.btoa(binary);
            }}

            // Tab 4 Customer Memory & Reservations Loader
            async function loadCustomerHistory() {{
                try {{
                    const logsRes = await fetch('/api/call-logs');
                    const logsJson = await logsRes.json();
                    const logsContainer = document.getElementById('customer-logs-list');
                    if (logsContainer && logsJson.status === 'success') {{
                        logsContainer.innerHTML = '';
                        const data = logsJson.data || {{}};
                        const keys = Object.keys(data);
                        if (keys.length === 0) {{
                            logsContainer.innerHTML = '<p style="font-size:12px; color:var(--text-muted);">ไม่มีประวัติการโทรย้อนหลัง</p>';
                        }} else {{
                            keys.forEach(phone => {{
                                const item = data[phone];
                                const card = document.createElement('div');
                                card.style.cssText = 'background:#ffffff; border:1px solid var(--border-color); border-radius:10px; padding:12px; font-size:12px;';
                                const audioPlayerHtml = item.recording_file ? `
                                    <div style="margin-top:8px; background:#fafafa; border:1px solid var(--border-color); border-radius:8px; padding:8px;">
                                        <div style="font-size:11px; font-weight:700; color:#09090b; margin-bottom:4px; display:flex; align-items:center; gap:6px;">
                                            <span>🎧</span>
                                            <span>ฟังเสียงบันทึกการโทร (Call Audio Recording):</span>
                                        </div>
                                        <audio controls style="width:100%; height:36px;" src="/api/recordings/${{escapeHtml(item.recording_file)}}"></audio>
                                    </div>
                                ` : '';
                                card.innerHTML = `
                                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                                        <span style="font-weight:700; color:#09090b;">👤 ${{escapeHtml(item.caller_name || 'ลูกค้า')}} (${{escapeHtml(phone)}})</span>
                                        <span style="font-size:10px; background:#f4f4f5; color:#71717a; padding:2px 8px; border-radius:8px; font-weight:600;">โทรแล้ว ${{item.total_calls || 1}} ครั้ง</span>
                                    </div>
                                    <div style="color:var(--text-muted); font-size:11px; margin-bottom:4px;">⏱️ ล่าสุด: ${{escapeHtml(item.last_call_time || '')}}</div>
                                    <div style="background:#fafafa; border:1px solid var(--border-color); border-radius:6px; padding:6px 8px; color:#09090b;">📝 ${{escapeHtml(item.last_summary || '')}}</div>
                                    ${{audioPlayerHtml}}
                                `;
                                logsContainer.appendChild(card);
                            }});
                        }}
                    }}

                    const resRes = await fetch('/api/reservations');
                    const resJson = await resRes.json();
                    const resContainer = document.getElementById('reservations-list');
                    if (resContainer && resJson.status === 'success') {{
                        resContainer.innerHTML = '';
                        const list = resJson.data || [];
                        if (list.length === 0) {{
                            resContainer.innerHTML = '<p style="font-size:12px; color:var(--text-muted);">ไม่มีรายการจองในขณะนี้</p>';
                        }} else {{
                            list.forEach(res => {{
                                const row = document.createElement('div');
                                row.style.cssText = 'background:#ffffff; border:1px solid var(--border-color); border-radius:10px; padding:12px; font-size:12px; display:flex; justify-content:space-between; align-items:center;';
                                row.innerHTML = `
                                    <div>
                                        <div style="font-weight:700; color:#09090b;">🔖 ${{escapeHtml(res.id)}} - ${{escapeHtml(res.name)}} (${{escapeHtml(res.phone)}})</div>
                                        <div style="color:var(--text-muted); font-size:11px;">📅 ${{escapeHtml(res.date_time)}} (${{res.guests}} ท่าน - ${{escapeHtml(res.type)}})</div>
                                    </div>
                                    <span style="font-size:11px; background:#e0e7ff; color:#4338ca; font-weight:700; padding:4px 10px; border-radius:8px;">✓ จองสำเร็จ</span>
                                `;
                                resContainer.appendChild(row);
                            }});
                        }}
                    }}
                }} catch (err) {{
                    console.error('Failed to load history:', err);
                }}
            }}

            const refreshHistoryBtn = document.getElementById('refresh-history-btn');
            if (refreshHistoryBtn) {{
                refreshHistoryBtn.addEventListener('click', loadCustomerHistory);
            }}

            loadCustomerHistory();
        </script>
    </body>
    </html>
    """
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


