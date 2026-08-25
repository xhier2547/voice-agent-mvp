import json
import logging
import datetime
from app import config

logger = logging.getLogger("VoiceAgent")

def get_caller_memory(phone: str = None, name: str = None, logs_path: str = "data/call_logs.json") -> str:
    """
    Fetches past customer conversation history and memory log for personalized AI responses.
    """
    try:
        with open(logs_path, "r", encoding="utf-8") as f:
            logs = json.load(f)
        
        target_log = None
        if phone and phone in logs:
            target_log = logs[phone]
        elif name:
            for p, item in logs.items():
                if item.get("caller_name", "").lower() == name.lower():
                    target_log = item
                    break

        if target_log:
            memory_str = f"""
ประวัติลูกค้าคนนี้เคยโทรเข้ามาแล้ว (Customer Memory):
- ชื่อลูกค้า: {target_log.get('caller_name', name or 'ลูกค้า')}
- เบอร์โทรศัพท์: {target_log.get('phone', phone or 'ไม่ระบุ')}
- จำนวนครั้งที่เคยโทร: {target_log.get('total_calls', 1)} ครั้ง
- ล่าสุดเมื่อ: {target_log.get('last_call_time', 'เมื่อเร็วๆ นี้')}
- สรุปการคุยครั้งก่อน: {target_log.get('last_summary', 'ลูกค้าสอบถามข้อมูลร้านค้า')}
- คำแนะนำ: ทักทายด้วยชื่อลูกค้าอย่างเป็นกันเองและเป็นธรรมชาติ เช่น 'สวัสดีค่ะคุณ {target_log.get('caller_name', '')} ยินดีต้อนรับกลับมาค่ะ!'
"""
            return memory_str
    except Exception as e:
        logger.warning(f"Could not load caller memory: {e}")
    
    return ""

def get_system_instruction(knowledge_path: str = "data/knowledge.json", caller_name: str = None, caller_phone: str = None) -> str:
    """
    Reads the knowledge base JSON file and builds a customized System Prompt
    injecting RAG context and Customer Memory.
    """
    try:
        with open(knowledge_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.warning(f"Could not load knowledge base from {knowledge_path}: {e}")
        data = {
            "company_name": "DripAI Coffee & Space",
            "operating_hours": "เปิดให้บริการทุกวัน เวลา 07:00 น. ถึง 20:00 น.",
            "location": "ชั้น 1 อาคารทรู ดิจิทัล พาร์ค สุขุมวิท 101 กรุงเทพฯ",
            "contact_number": "02-123-4567",
            "wifi_password": "DripAICoffeeGuest (ความเร็ว 500/500 Mbps)",
            "promotions": [],
            "faq": []
        }

    # Construct the instruction text
    prompt = f"""
คุณคือผู้ช่วย AI บริการลูกค้าทางโทรศัพท์ของร้าน "{data['company_name']}"
หน้าที่ของคุณคือตอบคำถามของลูกค้าอย่างสุภาพ เป็นมิตร และตอบกลับอย่างรวดเร็วทันใจ (<200ms)

ข้อมูลร้านค้าและบริการเพื่อใช้ตอบคำถาม (RAG):
- เวลาเปิดทำการ: {data['operating_hours']}
- สถานที่ตั้งและที่จอดรถ: {data['location']}
- เบอร์ติดต่อ: {data['contact_number']}
- รหัส Wi-Fi: {data['wifi_password']}

โปรโมชั่นปัจจุบัน:
"""
    for promo in data.get('promotions', []):
        prompt += f"- {promo['name']}: {promo['detail']}\n"

    prompt += "\nคำถามที่พบบ่อย (FAQ):\n"
    for item in data.get('faq', []):
        prompt += f"ถาม: {item['question']}\nตอบ: {item['answer']}\n\n"

    # Inject Customer Memory
    caller_mem = get_caller_memory(caller_phone, caller_name)
    if caller_mem:
        prompt += caller_mem

    prompt += """
คำแนะนำสำหรับการสนทนาทางโทรศัพท์จริง (Real-Time Ultra Low Latency):
1. คุณคือพนักงานรับสายสด (Real-Time Live Voice Agent) ให้ตอบกลับทันทีแบบเรียลไทม์ (<200ms)
2. ตอบกลับภาษาไทยด้วยประโยคสั้นกระชับ 1 ประโยคสั้นๆ (5-8 คำ) ห้ามเกริ่นอัมบท ห้ามทวนคำถาม ห้ามเว้นจังหวะ เพื่อให้สตรีมมิ่งเสียงตอบกลับได้เร็วที่สุดทันที
3. ตอบเข้าประเด็นทันที เช่น 'ร้านเปิดเจ็ดโมงถึงสองทุ่มค่ะ', 'รหัสไวไฟคือ DripAICoffeeGuest ค่ะ'
4. เมื่อตอบคำถามของลูกค้าเรียบร้อย ให้ถามลูกค้าอย่างสุภาพว่า 'มีอะไรให้ช่วยเหลือเพิ่มเติมไหมคะ?'
5. หากลูกค้าตอบว่า 'ไม่มีแล้ว', 'ไม่มีครับ/ค่ะ', 'ขอบคุณครับ/ค่ะ', 'ขอบคุณมาก', 'เท่านี้ครับ' หรือปฏิเสธไม่ถามต่อ:
   - ให้พูดขอบคุณอย่างเป็นธรรมชาติ เช่น 'ยินดีให้บริการค่ะ ขอบคุณที่ใช้บริการ DripAI Coffee สวัสดีค่ะ'
   - และเรียกใช้ฟังก์ชัน `end_call` ทันทีเพื่อวางสายและจบการสนทนา!
6. ห้ามพิมพ์ข้อความความคิดในใจ ภาษาอังกฤษ หรือหัวข้ออธิบาย เด็ดขาด
7. สามารถใช้ Tools เมื่อลูกค้าต้องการ:
   - วางสาย/จบการสนทนา: เรียกใช้ `end_call`
   - จองโต๊ะ / จองห้องประชุม: เรียกใช้ `book_table`
   - เช็กแต้มสะสมสมาชิก: เรียกใช้ `check_member_points`
   - ส่ง SMS สรุปข้อมูลเข้ามือถือลูกค้า: เรียกใช้ `send_sms_info`
   - โอนสายหาพนักงานมนุษย์: เรียกใช้ `transfer_call`
"""
    return prompt

def build_setup_message(system_instruction: str) -> dict:
    """
    Builds the initialization JSON setup message for Gemini Live API with Function Declarations.
    """
    return {
        "setup": {
            "model": config.get_gemini_model(),
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {
                            "voiceName": config.GEMINI_VOICE
                        }
                    }
                }
            },
            "systemInstruction": {
                "parts": [
                    {
                        "text": system_instruction
                    }
                ]
            },
            "tools": [
                {
                    "functionDeclarations": [
                        {
                            "name": "end_call",
                            "description": "วางสายและจบการสนทนาทางโทรศัพท์ทันที เมื่อลูกค้ากล่าวขอบคุณ ตอบว่าไม่มีอะไรสอบถามเพิ่มเติมแล้ว หรือปฏิเสธไม่ต้องการถามต่อ",
                            "parameters": {
                                "type": "OBJECT",
                                "properties": {
                                    "reason": {"type": "STRING", "description": "เหตุผลในการวางสาย"}
                                },
                                "required": []
                            }
                        },
                        {
                            "name": "book_table",
                            "description": "จองโต๊ะหรือจองห้องประชุมส่วนตัวให้ลูกค้า",
                            "parameters": {
                                "type": "OBJECT",
                                "properties": {
                                    "name": {"type": "STRING", "description": "ชื่อผู้จอง"},
                                    "phone": {"type": "STRING", "description": "เบอร์โทรศัพท์"},
                                    "date_time": {"type": "STRING", "description": "วันที่และเวลาที่ต้องการจอง"},
                                    "guests": {"type": "INTEGER", "description": "จำนวนท่าน"}
                                },
                                "required": ["name", "date_time", "guests"]
                            }
                        },
                        {
                            "name": "check_member_points",
                            "description": "เช็กแต้มสะสมสมาชิกและสิทธิ์ส่วนลดของลูกค้า",
                            "parameters": {
                                "type": "OBJECT",
                                "properties": {
                                    "phone": {"type": "STRING", "description": "เบอร์โทรศัพท์สมาชิก"}
                                },
                                "required": []
                            }
                        },
                        {
                            "name": "send_sms_info",
                            "description": "ส่ง SMS สรุปข้อมูลร้านค้า รหัส Wi-Fi หรือแผนที่เข้ามือถือลูกค้า",
                            "parameters": {
                                "type": "OBJECT",
                                "properties": {
                                    "phone": {"type": "STRING", "description": "เบอร์โทรศัพท์รับ SMS"},
                                    "info_type": {"type": "STRING", "description": "ประเภทข้อมูล เช่น wifi, map, promo"}
                                },
                                "required": ["info_type"]
                            }
                        },
                        {
                            "name": "transfer_call",
                            "description": "โอนสายลูกค้าไปยังเจ้าหน้าที่พนักงานที่เป็นมนุษย์ ทันทีเมื่อลูกค้าแจ้งความประสงค์ต้องการพูดคุยกับเจ้าหน้าที่หรือบุคคลจริง",
                            "parameters": {
                                "type": "OBJECT",
                                "properties": {},
                                "required": []
                            }
                        }
                    ]
                }
            ]
        }
    }

def execute_end_call(reason: str = None) -> dict:
    """
    Executes end call action.
    """
    return {
        "status": "success",
        "message": f"ขอบคุณที่ใช้บริการ DripAI Coffee วางสายเรียบร้อยแล้ว ({reason or 'จบการสนทนา'})"
    }

def execute_book_table(name: str, phone: str, date_time: str, guests: int, res_path: str = "data/reservations.json") -> dict:
    """
    Executes table reservation action and saves record to reservations.json.
    """
    try:
        try:
            with open(res_path, "r", encoding="utf-8") as f:
                res_list = json.load(f)
        except Exception:
            res_list = []

        new_res = {
            "id": f"RES-{1001 + len(res_list)}",
            "name": name or "ลูกค้า",
            "phone": phone or "081-234-5678",
            "date_time": date_time,
            "guests": guests or 2,
            "type": "ห้องประชุมส่วนตัว" if guests > 6 else "โต๊ะอาหารทั่วไป",
            "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        res_list.append(new_res)
        with open(res_path, "w", encoding="utf-8") as f:
            json.dump(res_list, f, ensure_ascii=False, indent=2)
        logger.info(f"Booked table successfully for {name}")
        return {"status": "success", "reservation": new_res, "message": f"จองโต๊ะให้คุณ {name} สำหรับ {guests} ท่าน วันที่ {date_time} เรียบร้อยแล้วค่ะ"}
    except Exception as e:
        logger.error(f"Failed to book table: {e}")
        return {"status": "error", "message": str(e)}

def execute_check_member_points(phone: str) -> dict:
    """
    Executes member points inquiry.
    """
    return {
        "status": "success",
        "points": 8,
        "required_for_free": 10,
        "message": "สะสมครบ 8 แก้วแล้วค่ะ สะสมอีกเพียง 2 แก้วรับเครื่องดื่มฟรี 1 แก้วทันทีค่ะ!"
    }

def execute_send_sms_info(phone: str, info_type: str) -> dict:
    """
    Simulates sending SMS info to user.
    """
    return {
        "status": "success",
        "info_type": info_type,
        "message": f"จัดส่งข้อความ SMS ข้อมูล {info_type} ไปยังเบอร์ {phone or 'ของคุณ'} เรียบร้อยแล้วค่ะ!"
    }

def match_knowledge(query: str, knowledge_path: str = "data/knowledge.json") -> dict:
    """
    Matches user query string against knowledge base items to identify RAG retrieval source.
    """
    try:
        with open(knowledge_path, "r", encoding="utf-8") as f:
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
    
    q_lower = (query or "").lower()
    if any(k in q_lower for k in ["เปิด", "ปิด", "เวลา", "กี่โมง", "เปิดกี่โมง"]):
        return {"section": "เวลาเปิดทำการ (Operating Hours)", "content": data.get("operating_hours", ""), "file": knowledge_path}
    elif any(k in q_lower for k in ["wifi", "wi-fi", "รหัส", "เน็ต", "อินเทอร์เน็ต", "พาสเวิร์ด"]):
        return {"section": "รหัส Wi-Fi (Wi-Fi Credentials)", "content": data.get("wifi_password", ""), "file": knowledge_path}
    elif any(k in q_lower for k in ["ที่อยู่", "ตั้ง", "สถานที่", "จอดรถ", "เดินทาง", "ที่ไหน", "พิกัด"]):
        return {"section": "สถานที่ตั้งและที่จอดรถ (Location)", "content": data.get("location", ""), "file": knowledge_path}
    elif any(k in q_lower for k in ["ติดต่อ", "เบอร์", "โทร", "พนักงาน"]):
        return {"section": "เบอร์ติดต่อพนักงาน (Contact Number)", "content": data.get("contact_number", ""), "file": knowledge_path}
    elif any(k in q_lower for k in ["โปร", "ส่วนลด", "แถม", "ฟรี", "ลด"]):
        promos = [f"{p.get('name')}: {p.get('detail')}" for p in data.get("promotions", [])]
        return {"section": "โปรโมชั่นปัจจุบัน (Promotions)", "content": " | ".join(promos) if promos else "ไม่มีโปรโมชั่น", "file": knowledge_path}
    else:
        for item in data.get("faq", []):
            q_faq = item.get("question", "")
            if any(w in q_lower for w in q_faq.lower().split() if len(w) > 2):
                return {"section": f"FAQ: {q_faq}", "content": item.get("answer"), "file": knowledge_path}
        return {"section": f"คลังข้อมูลร้านค้า ({data.get('company_name')})", "content": f"ข้อมูลบริบทระบบ RAG ใน {knowledge_path}", "file": knowledge_path}
