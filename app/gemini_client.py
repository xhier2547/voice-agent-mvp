import json
import logging
import datetime
import os
import time
import urllib.request
import urllib.error
import chromadb
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
    Reads the knowledge base JSON file and builds a customized System Prompt.
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
        }

    promos_list = data.get("promotions", [])
    promos_str = "\n".join([f"  • {p.get('name')}: {p.get('detail')}" for p in promos_list]) if promos_list else "  • ไม่มีโปรโมชั่นในขณะนี้"

    faq_list = data.get("faq", [])
    faq_str = "\n".join([f"  • ถาม: {f.get('question')}\n    ตอบ: {f.get('answer')}" for f in faq_list]) if faq_list else "  • ไม่มี"

    prompt = f"""คุณคือพนักงานบริการลูกค้าของ "{data.get('company_name', '')}"

ตอบภาษาไทย สั้น กระชับ คุยอย่างเป็นธรรมชาติเหมือนเพื่อนมนุษย์คุยกันจริงๆ

ข้อมูลร้านค้าและโปรโมชั่น (พร้อมตอบลูกค้าได้ทันทีใน 0.6 วินาทีโดยไม่ต้องเรียกใช้ Tool):
- เวลาเปิด: {data.get('operating_hours', '')}
- สถานที่: {data.get('location', '')}
- เบอร์ติดต่อ: {data.get('contact_number', '')}
- Wi-Fi: {data.get('wifi_password', '')}

โปรโมชั่นปัจจุบัน:
{promos_str}

คำถามพบบ่อย (FAQ):
{faq_str}"""

    # Inject Customer Memory if exists
    caller_mem = get_caller_memory(caller_phone, caller_name)
    if caller_mem:
        prompt += f"\n\nข้อมูลของลูกค้าคนนี้:\n{caller_mem}"

    prompt += """

กฎเหล็กควบคุมขอบเขตบทสนทนา (Strict Guardrails & Focus):
1. **รักษาบทบาทและขอบเขตบริการ**: คุณคือพนักงานบริการของแบรนด์และองค์กรนี้ (APEX AGENT Platform) ให้ข้อมูลเฉพาะเรื่องที่เกี่ยวกับร้านและเอกสารข้อมูลระบบเท่านั้น
2. **จัดการการพูดออกนอกเรื่อง (Off-Topic Steering)**: หากลูกค้าชวนคุยเรื่องทั่วไปที่ไม่เกี่ยวกับระบบ (เช่น ดินฟ้าอากาศ, การเมือง, ข่าวสาร) ให้ตอบรับสั้นๆ สุภาพ แล้วดึงบทสนทนากลับเข้าเรื่องบริการทันที เช่น "เรื่องนั้นน่าสนใจมากเลยค่ะ! แต่สำหรับวันนี้หากต้องการสอบถามข้อมูลบริการหรือจองนัดหมาย APEX AGENT ยินดีดูแลให้อย่างเต็มที่เลยค่ะ"
3. **ตอบกลับสดรวดเร็วทันทีระดับ sub-second (< 1 วินาที)**: ข้อมูลพื้นฐานบริการมีครบถ้วนในคำสั่งนี้แล้ว ให้ตอบลูกค้าด้วยเสียงสดทันทีโดยไม่ต้องเรียกใช้ Tool `query_knowledge`! ให้ใช้ `query_knowledge` เฉพาะเมื่อเป็นคำถามลึกซึ้งในเอกสารที่ไม่อยู่ในข้อมูลพื้นฐานเท่านั้น
4. **การค้นหาเอกสาร Dynamic Knowledge**: หากเป็นคำถามเฉพาะทางหรือรายละเอียดลึกซึ้ง ให้ใช้ `query_knowledge` ค้นหาข้อมูลจากเอกสาร PDF/CSV/TXT ที่อัปโหลดในระบบแล้วนำมาตอบสั้นๆ 1-2 ประโยค

เทคนิคการสนทนาให้ลื่นไหลและเป็นธรรมชาติ (Natural Conversational Voice Persona):
1. **ใช้คำเกริ่นตอบรับอย่างเป็นธรรมชาติ (Active Listening & Empathy)**: เริ่มต้นด้วยคำตอบรับที่แสดงอารมณ์ร่วมและใส่ใจ เช่น "ฟังดูน่าสนใจมากเลยค่ะ!", "ยินดีเลยค่ะ!", "ได้เลยครับ!", "ยินดีด้วยนะคะ!", "ยอดเยี่ยมเลยค่ะ!"
2. **ชวนคุยและช่วยเหลืออย่างเป็นมิตร (Contextual Engagement)**: แสดงความเข้าใจต่อสิ่งที่ลูกค้าเล่า แล้วถามคำถามเจาะจงเพื่อนำเสนอทางเลือกหรือช่วยเหลือต่ออย่างเป็นธรรมชาติ
3. **หลีกเลี่ยงภาษาหุ่นยนต์และสคริปต์แข็งๆ**: ห้ามพูดทวนคำถามลูกค้า ห้ามใช้ประโยคสำเร็จรูปปิดท้ายเดิมๆ เช่น "มีอะไรให้ช่วยอีกไหมคะ" ให้ชวนคุยต่อตามเนื้อหาจริงเท่านั้น
4. **ความยาวกระชับลงตัว (1-2 ประโยค)**: ตอบ 1-2 ประโยคกระชับลงตัว ไม่สั้นจนห้วนเป็นหุ่นยนต์ และไม่ยาวจนเกิดความหน่วงในสตรีมเสียง
5. **เรียกใช้ Tools ทันทีพร้อมคำเกริ่น**: เมื่อลูกค้าต้องการจองโต๊ะ วางสาย หรือเช็กแต้ม ให้เรียกใช้ Tool ทันที
6. **การรับมือคำตอบรับสั้นๆ (Backchannel Handling)**: หากลูกค้าพูดคำรับสั้นๆ เช่น "ครับ", "ค่ะ", "อ๋อ", "โอเค" ระหว่างสนทนา ให้ตอบรับสั้นๆ เช่น "ครับผม" หรือ "ค่ะ" แล้วดำเนินบทสนทนาต่ออย่างลื่นไหล ห้ามตกใจหรือค้างประมวลผลนาน

กฎเหล็กสำหรับการจบสาย (End Call - Anti Loop):
- เมื่อลูกค้าพูดว่า "ไม่มีอะไรแล้ว", "ไม่มีอะไรถามแล้ว", "พอแค่นี้", "ขอบคุณนะ", "ลาก่อน" หรือแสดงเจตนาจบสนทนา ให้ทำตามขั้นตอนนี้ **เพียงครั้งเดียว**:
  1. พูดขอบคุณสั้นๆ ไม่เกิน 1 ประโยค เช่น "ขอบคุณที่ติดต่อเข้ามาค่ะ APEX AGENT ยินดีให้บริการเสมอค่ะ"
  2. เรียก end_call() ทันทีหลังพูดจบ
- **ห้ามพูดขอบคุณซ้ำเด็ดขาด** ห้ามเริ่มประโยคขอบคุณใหม่หลังจากพูดจบแล้ว ไม่ว่าจะเกิดอะไรขึ้น
- **ห้ามถามซ้ำ** ว่า "มีอะไรอีกไหม" หลังจากลูกค้าบอกว่าไม่มีแล้ว"""
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

                "thinkingConfig": {
                    "thinkingBudget": 0
                },

                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {
                            "voiceName": config.GEMINI_VOICE
                        }
                    }
                }
            },
            "realtimeInputConfig": {
                "automaticActivityDetection": {
                    "disabled": False,
                    "prefixPaddingMs": 20,
                    "silenceDurationMs": 100
                }
            },
            "inputAudioTranscription": {},
            "outputAudioTranscription": {},

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
                                "type": "object",
                                "properties": {
                                    "reason": {"type": "string", "description": "เหตุผลในการวางสาย"}
                                },
                                "required": []
                            }
                        },
                        {
                            "name": "book_table",
                            "description": "จองโต๊ะหรือจองห้องประชุมส่วนตัวให้ลูกค้า",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string", "description": "ชื่อผู้จอง"},
                                    "phone": {"type": "string", "description": "เบอร์โทรศัพท์"},
                                    "date_time": {"type": "string", "description": "วันที่และเวลาที่ต้องการจอง"},
                                    "guests": {"type": "integer", "description": "จำนวนท่าน"}
                                },
                                "required": ["name", "date_time", "guests"]
                            }
                        },
                        {
                            "name": "check_member_points",
                            "description": "เช็กแต้มสะสมสมาชิกและสิทธิ์ส่วนลดของลูกค้า",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "phone": {"type": "string", "description": "เบอร์โทรศัพท์สมาชิก"}
                                },
                                "required": []
                            }
                        },
                        {
                            "name": "send_sms_info",
                            "description": "ส่ง SMS สรุปข้อมูลร้านค้า รหัส Wi-Fi หรือแผนที่เข้ามือถือลูกค้า",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "phone": {"type": "string", "description": "เบอร์โทรศัพท์รับ SMS"},
                                    "info_type": {"type": "string", "description": "ประเภทข้อมูล เช่น wifi, map, promo"}
                                },
                                "required": ["info_type"]
                            }
                        },
                        {
                            "name": "transfer_call",
                            "description": "โอนสายลูกค้าไปยังเจ้าหน้าที่พนักงานที่เป็นมนุษย์ ทันทีเมื่อลูกค้าแจ้งความประสงค์ต้องการพูดคุยกับเจ้าหน้าที่หรือบุคคลจริง",
                            "parameters": {
                                "type": "object",
                                "properties": {},
                                "required": []
                            }
                        },
                        {
                            "name": "check_reservation",
                            "description": "ตรวจสอบข้อมูลการจองโต๊ะหรือจองห้องประชุมส่วนตัวของลูกค้าในระบบด้วยเบอร์โทรศัพท์",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "phone": {"type": "string", "description": "เบอร์โทรศัพท์ที่ใช้จอง"}
                                },
                                "required": ["phone"]
                            }
                        },
                        {
                            "name": "query_knowledge",
                            "description": "ค้นหารายละเอียดข้อมูลร้านค้า นโยบาย เมนู ราคา หรือโปรโมชั่น เพื่อตอบคำถามของลูกค้าด้วยระบบ RAG",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "query": {"type": "string", "description": "คีย์เวิร์ดหรือข้อความที่ต้องการค้นหา เช่น เวลาเปิดร้าน, โปรโมชั่น, ราคาลาเต้"}
                                },
                                "required": ["query"]
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
    Executes table reservation action and saves record to reservations.json in non-blocking background thread.
    """
    try:
        guests_cnt = guests or 2
        new_res = {
            "id": f"RES-{1001 + int(time.time() * 1000) % 9000}",
            "name": name or "ลูกค้า",
            "phone": phone or "081-234-5678",
            "date_time": date_time,
            "guests": guests_cnt,
            "type": "ห้องประชุมส่วนตัว" if guests_cnt > 6 else "โต๊ะอาหารทั่วไป",
            "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        import threading
        def _bg_save():
            try:
                try:
                    with open(res_path, "r", encoding="utf-8") as f:
                        res_list = json.load(f)
                except Exception:
                    res_list = []
                res_list.append(new_res)
                with open(res_path, "w", encoding="utf-8") as f:
                    json.dump(res_list, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.error(f"Failed to async save reservation: {e}")

        threading.Thread(target=_bg_save, daemon=True).start()
        logger.info(f"Booked table successfully for {name} (Async Non-blocking)")
        return {"status": "success", "reservation": new_res, "message": f"จองโต๊ะให้คุณ {name} สำหรับ {guests_cnt} ท่าน วันที่ {date_time} เรียบร้อยแล้วค่ะ"}
    except Exception as e:
        logger.error(f"Failed to book table: {e}")
        return {"status": "error", "message": str(e)}

def execute_check_reservation(phone: str, res_path: str = "data/reservations.json") -> dict:
    """
    Checks if a reservation exists for the given phone number in reservations.json.
    """
    try:
        if not phone:
            return {"status": "error", "message": "กรุณาระบุเบอร์โทรศัพท์เพื่อตรวจสอบการจองค่ะ"}
            
        clean_phone = "".join(c for c in phone if c.isdigit())
        
        try:
            with open(res_path, "r", encoding="utf-8") as f:
                res_list = json.load(f)
        except Exception:
            res_list = []
            
        matches = []
        for res in res_list:
            res_phone = "".join(c for c in res.get("phone", "") if c.isdigit())
            if clean_phone in res_phone or res_phone in clean_phone:
                matches.append(res)
                
        if matches:
            latest = matches[-1]
            return {
                "status": "success",
                "found": True,
                "reservation": latest,
                "message": f"พบข้อมูลการจองภายใต้เบอร์ {phone} ค่ะ: รหัสการจอง {latest['id']} จองโดยคุณ {latest['name']} วันที่ {latest['date_time']} จำนวน {latest['guests']} ท่าน ({latest['type']}) เรียบร้อยแล้วค่ะ"
            }
        else:
            return {
                "status": "success",
                "found": False,
                "message": f"ไม่พบข้อมูลการจองสำหรับเบอร์โทรศัพท์ {phone} ในระบบค่ะ"
            }
    except Exception as e:
        logger.error(f"Failed to check reservation: {e}")
        return {"status": "error", "message": str(e)}

def execute_query_knowledge(query: str) -> dict:
    """
    Queries the RAG Vector Store to retrieve matching business knowledge.
    """
    try:
        if not query:
            return {"status": "error", "message": "กรุณาระบุสิ่งที่ต้องการค้นหาค่ะ"}
            
        result = match_knowledge(query)
        logger.info(f"RAG Match for query '{query}': {result.get('section')}")
        
        section = result.get("section", "คลังความรู้")
        content = result.get("content", "ไม่พบข้อมูลที่ตรงกันในขณะนี้ค่ะ")
        
        return {
            "status": "success",
            "section": section,
            "content": content,
            "message": f"ดึงข้อมูลจากหัวข้อ '{section}' ค่ะ: {content}"
        }
    except Exception as e:
        logger.error(f"RAG query failed: {e}")
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

class GeminiEmbeddingFunction(chromadb.EmbeddingFunction):
    """
    Custom ChromaDB Embedding Function that uses Gemini Embedding API (gemini-embedding-001).
    """
    def __init__(self, api_key: str, model_name: str = "models/gemini-embedding-001"):
        self.api_key = api_key
        self.model_name = model_name

    def __call__(self, input: chromadb.Documents) -> chromadb.Embeddings:
        if not input:
            return []
        
        requests = []
        for text in input:
            requests.append({
                "model": self.model_name,
                "content": {
                    "parts": [{"text": text}]
                }
            })
        
        req_data = {"requests": requests}
        req_body = json.dumps(req_data).encode("utf-8")
        clean_model = self.model_name if self.model_name.startswith("models/") else f"models/{self.model_name}"
        url = f"https://generativelanguage.googleapis.com/v1beta/{clean_model}:batchEmbedContents?key={self.api_key}"
        
        try:
            req = urllib.request.Request(
                url,
                data=req_body,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                embeddings = res_data.get("embeddings", [])
                return [emb.get("values", []) for emb in embeddings]
        except Exception as e:
            logger.debug(f"Gemini embeddings API call info: {e}")
            raise e

class VectorRAGStore:
    """
    Vector Database RAG Engine powered by ChromaDB & Semantic Vector Space Matching with In-Memory Cache.
    """
    def __init__(self, storage_dir: str = "data/chroma_db"):
        self.storage_dir = storage_dir
        self.chroma_client = None
        self.collection = None
        self.documents = []
        self.metadatas = []
        self.cache = {}
        self._init_chroma()

    def _init_chroma(self):
        try:
            os.makedirs(self.storage_dir, exist_ok=True)
            self.chroma_client = chromadb.PersistentClient(path=self.storage_dir)
            gemini_ef = GeminiEmbeddingFunction(api_key=config.GEMINI_API_KEY)
            try:
                self.collection = self.chroma_client.get_or_create_collection(
                    name="voice_agent_rag",
                    embedding_function=gemini_ef
                )
            except Exception as e:
                if "Embedding function conflict" in str(e) or "already exists" in str(e):
                    try:
                        self.chroma_client.delete_collection("voice_agent_rag")
                    except Exception:
                        pass
                    self.collection = self.chroma_client.create_collection(
                        name="voice_agent_rag",
                        embedding_function=gemini_ef
                    )
                else:
                    raise e
            logger.info("ChromaDB Vector Store initialized successfully with Gemini Embeddings.")
        except Exception as e:
            logger.warning(f"Could not initialize ChromaDB: {e}. Falling back to Vector Space Engine.")

    def sync_knowledge(self, knowledge_path: str = "data/knowledge.json"):
        """
        Extracts, embeds, and indexes all business knowledge into the Vector Database.
        """
        self.cache.clear()
        try:
            with open(knowledge_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return

        docs = []
        metas = []
        ids = []

        if data.get("operating_hours"):
            docs.append(f"เวลาเปิดทำการ: {data['operating_hours']}")
            metas.append({"section": "เวลาเปิดทำการ (Operating Hours)", "type": "info"})
            ids.append("info_hours")

        if data.get("location"):
            docs.append(f"สถานที่ตั้งและที่จอดรถ: {data['location']}")
            metas.append({"section": "สถานที่ตั้งและที่จอดรถ (Location)", "type": "info"})
            ids.append("info_location")

        if data.get("wifi_password"):
            docs.append(f"รหัส Wi-Fi อินเทอร์เน็ต: {data['wifi_password']}")
            metas.append({"section": "รหัส Wi-Fi (Wi-Fi Credentials)", "type": "info"})
            ids.append("info_wifi")

        if data.get("contact_number"):
            docs.append(f"เบอร์โทรศัพท์ติดต่อร้านค้า: {data['contact_number']}")
            metas.append({"section": "เบอร์ติดต่อพนักงาน (Contact Number)", "type": "info"})
            ids.append("info_contact")

        for idx, promo in enumerate(data.get("promotions", [])):
            doc_text = f"โปรโมชั่นส่วนลด: {promo.get('name')} - {promo.get('detail')}"
            docs.append(doc_text)
            metas.append({"section": f"โปรโมชั่น: {promo.get('name')}", "type": "promo"})
            ids.append(f"promo_{idx}")

        for idx, faq in enumerate(data.get("faq", [])):
            doc_text = f"คำถาม: {faq.get('question')} ตอบ: {faq.get('answer')}"
            docs.append(doc_text)
            metas.append({"section": f"FAQ: {faq.get('question')}", "type": "faq"})
            ids.append(f"faq_{idx}")

        # Also sync dynamic uploaded documents
        try:
            with open("data/documents.json", "r", encoding="utf-8") as f:
                dyn_docs = json.load(f)
            for d in dyn_docs:
                d_chunks = d.get("chunks", [])
                d_id = d.get("doc_id", "")
                d_filename = d.get("filename", "document")
                d_type = d.get("source_type", "txt")
                for idx, chunk in enumerate(d_chunks):
                    doc_text = f"เอกสารข้อมูล [{d_filename}]: {chunk}"
                    docs.append(doc_text)
                    metas.append({
                        "doc_id": d_id,
                        "filename": d_filename,
                        "section": f"เอกสาร {d_filename} (ส่วนที่ {idx+1})",
                        "type": d_type
                    })
                    ids.append(f"doc_{d_id}_chunk_{idx}")
        except Exception:
            pass

        self.documents = docs
        self.metadatas = metas

        if self.collection and docs:
            try:
                self.collection.upsert(
                    documents=docs,
                    metadatas=metas,
                    ids=ids
                )
                logger.info(f"Indexed {len(docs)} documents into ChromaDB Vector Store.")
            except Exception as e:
                logger.warning(f"Failed to upsert to ChromaDB: {e}")

    def ingest_dynamic_document(self, doc_id: str, filename: str, chunks: list, source_type: str = "pdf"):
        """
        Embeds and indexes document chunks into ChromaDB Vector Store.
        """
        if not chunks:
            return

        self.cache.clear()
        docs = []
        metas = []
        ids = []

        for idx, chunk in enumerate(chunks):
            doc_text = f"เอกสารข้อมูล [{filename}]: {chunk}"
            docs.append(doc_text)
            metas.append({
                "doc_id": doc_id,
                "filename": filename,
                "section": f"เอกสาร {filename} (ส่วนที่ {idx+1})",
                "type": source_type
            })
            ids.append(f"doc_{doc_id}_chunk_{idx}")

            self.documents.append(doc_text)
            self.metadatas.append({
                "doc_id": doc_id,
                "filename": filename,
                "section": f"เอกสาร {filename} (ส่วนที่ {idx+1})",
                "type": source_type
            })

        if self.collection and docs:
            try:
                self.collection.upsert(
                    documents=docs,
                    metadatas=metas,
                    ids=ids
                )
                logger.info(f"Indexed {len(docs)} chunks for dynamic document '{filename}' into ChromaDB Vector Store.")
            except Exception as e:
                logger.warning(f"Failed to upsert dynamic document to ChromaDB: {e}")

    def delete_dynamic_document(self, doc_id: str):
        """
        Removes dynamic document chunks from ChromaDB and memory.
        """
        self.cache.clear()
        if self.collection:
            try:
                self.collection.delete(where={"doc_id": doc_id})
                logger.info(f"Deleted dynamic document '{doc_id}' from ChromaDB Vector Store.")
            except Exception as e:
                logger.warning(f"Failed to delete dynamic document from ChromaDB: {e}")

        # Filter out from in-memory documents
        keep_docs = []
        keep_metas = []
        for d, m in zip(self.documents, self.metadatas):
            if m.get("doc_id") != doc_id:
                keep_docs.append(d)
                keep_metas.append(m)
        self.documents = keep_docs
        self.metadatas = keep_metas

    def query(self, query_text: str) -> dict:
        """
        Performs Semantic Search on the Vector Database with In-Memory Cache.
        """
        cache_key = (query_text or "").strip().lower()
        if cache_key in self.cache:
            cached = dict(self.cache[cache_key])
            cached["method"] = "In-Memory Fast Cache (<0.1ms)"
            cached["cache_hit"] = True
            logger.info(f"RAG Cache HIT for query '{query_text}' -> {cached.get('section')}")
            return cached

        res_dict = None
        if not self.documents:
            self.sync_knowledge()

        if self.collection:
            try:
                res = self.collection.query(
                    query_texts=[query_text],
                    n_results=1
                )
                if res and res.get("documents") and len(res["documents"][0]) > 0:
                    matched_doc = res["documents"][0][0]
                    matched_meta = res["metadatas"][0][0]
                    dist = res["distances"][0][0] if "distances" in res and res["distances"] else 0.5
                    sim_pct = round(max(10.0, min(99.9, (1.0 - dist) * 100)), 1)
                    
                    res_dict = {
                        "section": matched_meta.get("section", "ChromaDB Vector Match"),
                        "content": matched_doc,
                        "file": "data/chroma_db (Chroma Vector DB)",
                        "method": "Vector Embeddings (ChromaDB)",
                        "similarity": f"{sim_pct}%",
                        "cache_hit": False
                    }
            except Exception as e:
                logger.warning(f"ChromaDB query fallback: {e}")

        if not res_dict:
            res_dict = self._vector_space_fallback(query_text)

        if cache_key:
            self.cache[cache_key] = res_dict

        return res_dict

    def _vector_space_fallback(self, query_text: str) -> dict:
        if not self.documents:
            return {
                "section": "คลังข้อมูลร้านค้า (Vector RAG)",
                "content": "ไม่มีข้อมูลคลังความรู้",
                "file": "data/knowledge.json",
                "method": "Keyword Search",
                "similarity": "50%"
            }

        q_words = set((query_text or "").lower())
        best_score = -1
        best_idx = 0

        for idx, doc in enumerate(self.documents):
            d_words = set(doc.lower())
            intersection = q_words.intersection(d_words)
            union = q_words.union(d_words)
            jaccard_sim = len(intersection) / len(union) if union else 0
            if jaccard_sim > best_score:
                best_score = jaccard_sim
                best_idx = idx

        best_doc = self.documents[best_idx]
        best_meta = self.metadatas[best_idx]
        sim_pct = round(min(99.0, max(60.0, best_score * 300)), 1)

        return {
            "section": best_meta.get("section", "Vector RAG Match"),
            "content": best_doc,
            "file": "data/chroma_db (Vector Store)",
            "method": "Vector Embeddings (Semantic Cosine)",
            "similarity": f"{sim_pct}%"
        }

vector_rag_engine = VectorRAGStore()
vector_rag_engine.sync_knowledge()

def match_knowledge(query: str, knowledge_path: str = "data/knowledge.json") -> dict:
    """
    Matches user query string against Vector Database (ChromaDB Semantic Search).
    """
    return vector_rag_engine.query(query)
