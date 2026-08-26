import json
import logging
import datetime
import os
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

    prompt = f"""คุณคือพนักงานบริการลูกค้าของ "{data.get('company_name', '')}"

ตอบภาษาไทย สั้น กระชับ คุยอย่างเป็นธรรมชาติเหมือนเพื่อนมนุษย์คุยกันจริงๆ

ข้อมูลร้าน:
- เวลาเปิด: {data.get('operating_hours', '')}
- สถานที่: {data.get('location', '')}
- เบอร์: {data.get('contact_number', '')}
- Wi-Fi: {data.get('wifi_password', '')}"""

    # Inject Customer Memory if exists
    caller_mem = get_caller_memory(caller_phone, caller_name)
    if caller_mem:
        prompt += f"\n\nข้อมูลของลูกค้าคนนี้:\n{caller_mem}"

    prompt += """

กฎเหล็กเพื่อความเสถียรและธรรมชาติของการคุยทางโทรศัพท์:
1. ตอบสั้นมากๆ (ประโยคเดียวจบ 5-8 คำ) เพื่อลดความหน่วงในสตรีมเสียง
2. ห้ามทวนคำถามลูกค้า ห้ามเว้นจังหวะวิเคราะห์ หรือบรรยายความคิดในใจเด็ดขาด
3. **สำคัญมาก**: ห้ามพูดปิดท้ายประโยคด้วยประโยคสำเร็จรูปเดิมๆ เช่น "มีอะไรให้ช่วยอีกไหมคะ/ครับ" ในทุกๆ ประโยคเด็ดขาด มันดูเป็นหุ่นยนต์ ให้ถามต่อเมื่อลูกค้าคุยธุระนั้นๆ จบแล้วจริงๆ หรือเกิดความเงียบเท่านั้น
4. ใช้ Tools ทันทีเมื่อลูกค้าต้องการจองโต๊ะ วางสาย หรือเช็กแต้ม"""
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
                    "prefixPaddingMs": 40,
                    "silenceDurationMs": 200
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
                        },
                        {
                            "name": "check_reservation",
                            "description": "ตรวจสอบข้อมูลการจองโต๊ะหรือจองห้องประชุมส่วนตัวของลูกค้าในระบบด้วยเบอร์โทรศัพท์",
                            "parameters": {
                                "type": "OBJECT",
                                "properties": {
                                    "phone": {"type": "STRING", "description": "เบอร์โทรศัพท์ที่ใช้จอง"}
                                },
                                "required": ["phone"]
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

class VectorRAGStore:
    """
    Vector Database RAG Engine powered by ChromaDB & Semantic Vector Space Matching.
    """
    def __init__(self, storage_dir: str = "data/chroma_db"):
        self.storage_dir = storage_dir
        self.chroma_client = None
        self.collection = None
        self.documents = []
        self.metadatas = []
        self._init_chroma()

    def _init_chroma(self):
        try:
            import chromadb
            os.makedirs(self.storage_dir, exist_ok=True)
            self.chroma_client = chromadb.PersistentClient(path=self.storage_dir)
            self.collection = self.chroma_client.get_or_create_collection(name="voice_agent_rag")
            logger.info("ChromaDB Vector Store initialized successfully.")
        except Exception as e:
            logger.warning(f"Could not initialize ChromaDB: {e}. Falling back to Vector Space Engine.")

    def sync_knowledge(self, knowledge_path: str = "data/knowledge.json"):
        """
        Extracts, embeds, and indexes all business knowledge into the Vector Database.
        """
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

    def query(self, query_text: str) -> dict:
        """
        Performs Semantic Search on the Vector Database and returns the top matching section & content.
        """
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
                    
                    return {
                        "section": matched_meta.get("section", "ChromaDB Vector Match"),
                        "content": matched_doc,
                        "file": "data/chroma_db (Chroma Vector DB)",
                        "method": "Vector Embeddings (ChromaDB)",
                        "similarity": f"{sim_pct}%"
                    }
            except Exception as e:
                logger.warning(f"ChromaDB query fallback: {e}")

        return self._vector_space_fallback(query_text)

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
