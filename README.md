# 🎙️ AI Voice Agent MVP — Real-Time Multimodal Gemini Live Phone Agent

> **Voice Agent MVP** คือระบบผู้ช่วย AI ตอบคำถามและบริการลูกค้าทางโทรศัพท์แบบ Real-Time เสียงพูดโต้ตอบสด (<250ms Latency) ขับเคลื่อนด้วย **Gemini Live Multimodal API (BidiGenerateContent)**, **FastAPI**, **WebSockets** และ **RAG Knowledge Base System** พร้อมสวมบทบาทเป็นพนักงานโทรศัพท์สำหรับธุรกิจ (ตัวอย่าง: DripAI Coffee & Space)

---

## 📌 สถานะการพัฒนาตามโครงสร้าง 10 ส่วนหลัก (Project Progress Checklist)

### ✅ สิ่งที่พัฒนาเสร็จเรียบร้อยแล้ว (Completed Features)

- [x] **1. Telephony / Call Simulator Gateway**
  - [x] ระบบจำลองการโทรเข้าผ่านหน้าเว็บด้วย **iOS Phone Call Simulator Overlay** สไตล์มินิมอล ( White & Soft Gray Theme)
  - [x] รองรับการระบุชื่อผู้โทร (`Caller Name`) และเบอร์โทรศัพท์ (`Phone Number`) ก่อนเริ่มสาย
  - [x] สวิตช์ย่อ/ขยายหน้าจอโทรศัพท์ (`Minimize / Close Button`) โดยไม่ตัดสาย เพื่อให้ดูคอนโซลและสลับแท็บไปพร้อมกันได้

- [x] **2. Audio Streaming (Real-Time Bidirectional)**
  - [x] สตรีมมิ่งเสียงไมโครโฟน 16kHz PCM ผ่าน WebSockets แบบสองทาง (Full-Duplex)
  - [x] เล่นเสียงตอบกลับความละเอียดสูง 24kHz PCM แบบ Streaming ไร้รอยต่อ

- [x] **3. VAD + Turn Taking + Interruption (Barge-in)**
  - [x] **Noise Gate Filter (RMS Filter)**: ตัดขยะเสียงเงียบ ป้องกันการส่ง Silence Frame เพื่อให้ Gemini ตรวจจับการเริ่ม/หยุดพูดได้แม่นยำ (<200ms)
  - [x] **Barge-In Support**: เมื่อผู้ใช้พูดแทรกขณะ AI กำลังพูด ระบบจะหยุดเล่นเสียงทันทีและกลับมาฟังผู้ใช้โดยอัตโนมัติ

- [x] **4. Speech Understanding & Agent Brain**
  - [x] ใช้ **Gemini 2.5 Flash Native Audio Model (`models/gemini-2.5-flash-native-audio-latest`)** ทำหน้าที่เป็นสมองหลักทั้งฟัง เข้าใจความหมาย และประมวลผลคำตอบ

- [x] **5. Knowledge Base & Vector Database RAG (ChromaDB)**
  - [x] **Vector Database Engine (ChromaDB)**: เปลี่ยนระบบค้นหา RAG จาก Keyword Search ไปเป็น **Vector Embeddings (ChromaDB)** ค้นหาความหมายเชิงลึก (Semantic Search) ได้แม่นยำแม้ใช้คำไม่ตรงกัน
  - [x] **Auto Vector Index Sync**: เมื่อแก้ไขหรือเพิ่มข้อมูลในคลังความรู้ Tab 3 ระบบจะทำการ Re-index เวกเตอร์เข้า ChromaDB ในโฟลเดอร์ `data/chroma_db/` โดยอัตโนมัติ
  - [x] **Interactive RAG Admin (Tab 3)**: หน้าเว็บสำหรับแก้ไข บันทึก เพิ่ม หรือลบข้อมูล FAQ และโปรโมชั่นแบบเรียลไทม์ พร้อม Hot-Reload เข้า Vector Engine

- [x] **6. Agent Tools / Function Calling ("มือ" ของ Agent)**
  - [x] 🔍 `query_knowledge`: ดึงข้อมูลโปรโมชั่น นโยบาย เมนู และราคาจากคลังความรู้ด้วย RAG Vector Engine
  - [x] 📅 `book_table`: รับจองโต๊ะ/ห้องประชุม และบันทึกลง `data/reservations.json`
  - [x] 🎁 `check_member_points`: เช็กแต้มสะสมสมาชิกและสิทธิ์ส่วนลด
  - [x] 📲 `send_sms_info`: จำลองการส่ง SMS สรุปข้อมูลร้านค้า/รหัส Wi-Fi เข้ามือถือลูกค้า
  - [x] 📞 `transfer_call`: โอนสายไปยังเจ้าหน้าที่พนักงานมนุษย์
  - [x] 🛑 `end_call`: กล่าวขอบคุณและวางสายอัตโนมัติโดยรอให้ AI พูดขอบคุณจบประโยคก่อนวางสาย (`Turn Complete` Aware Hangup Timing)

- [x] **7. Customer Memory & Call Audio Recording (ระบบความจำและบันทึกเสียงการโทร)**
  - [x] บันทึกประวัติการโทรย้อนหลังใน `data/call_logs.json`
  - [x] เมื่อลูกค้าคนเดิมโทรเข้ามา AI จะดึงความจำย้อนหลังขึ้นมาทักทายชื่อลูกค้าอย่างเป็นกันเอง
  - [x] **Full Call Audio Recording**: บันทึกเสียงโต้ตอบสองทาง (ทั้งเสียงผู้ใช้และเสียง AI) ลงไฟล์ `.wav` ในโฟลเดอร์ `recordings/` อัตโนมัติทุกสาย
  - [x] **HTML5 Call Audio Player (Tab 4)**: เครื่องเล่นเสียงบนเว็บฝั่งขวา ให้กดเปิดฟังเสียงการโทรย้อนหลังได้ทันที!
  - [x] **Tab 4 (📜 ประวัติการโทร & การจอง)**: แสดงรายการประวัติความจำลูกค้าและตารางจองโต๊ะสดบนหน้าเว็บ

- [x] **8. Observability & Latency Monitoring**
  - [x] **Live Console Breakdown**: แสดงเวลาตอบกลับของ Gemini สดๆ บนหน้าเว็บ เช่น `🔊 [AI AUDIO STREAM] Gemini สตรีมเสียงสด (Latency: 180ms, 24kHz PCM)...`
  - [x] แสดง RAG Matching Source และ Tool Execution Log อย่างละเอียดแบบเรียลไทม์ พร้อมแยกประเภท Event (Barge-in vs Tool Execution) อย่างชัดเจน

---

### 🔲 สิ่งที่ยังขาดและแผนพัฒนาต่อ (Future Roadmap / To-Do)

- [ ] **1. Telephony Real Trunking (เบอร์โทรศัพท์จริง)**
  - [ ] ทดสอบเชื่อมต่อรับสาย/โทรออกผ่านเบอร์โทรศัพท์จริงด้วย **Twilio Voice SIP / Media Streams** และ Public Ngrok URL
- [ ] **2. Database Integration**
  - [ ] อัปเกรดระบบจัดเก็บข้อมูลจากไฟล์ JSON (`knowledge.json`, `call_logs.json`, `reservations.json`) ไปเป็น **PostgreSQL / SQLite** ร่วมกับ **SQLAlchemy ORM**
- [ ] **3. Multi-Agent & Safety Guardrails**
  - [ ] ติดตั้ง Topic Enforcer / Guardrails ป้องกัน Jailbreak และควบคุมไม่ให้ AI ตอบเรื่องนอกเหนือจากขอบเขตธุรกิจ
- [ ] **4. Real SMS / LINE Messaging Integration**
  - [ ] เชื่อมต่อ API จริงกับ Twilio SMS หรือ LINE Messaging API เพื่อส่งข้อความยืนยันการจอง/รหัส Wi-Fi เข้ามือถือลูกค้าจริงหลังวางสาย

---

## 🛠️ โครงสร้างไฟล์ในโปรเจกต์ (Project Structure)

```text
AI_VOICE/
├── app/
│   ├── __init__.py
│   ├── main.py             # FastAPI App, WebSockets Relay & REST API Endpoints
│   ├── config.py           # Environment Configurations & API Keys
│   ├── audio.py            # Audio Buffer & PCM Converter Utilities
│   ├── gemini_client.py    # Gemini Live Bidi Setup, RAG Engine & Function Callings
│   ├── twilio_client.py    # Twilio REST API Transfer Call Integration
│   └── templates/
│       └── phone_modal.html # Standalone iOS Phone Call Simulator Component
├── data/
│   ├── knowledge.json      # RAG Knowledge Base Database
│   ├── call_logs.json      # Customer Memory & History Database
│   └── reservations.json   # Table & Meeting Room Bookings Database
├── run.py                  # Server Launcher Script
├── requirements.txt        # Python Project Dependencies
├── .env.example            # Environment Variables Template
└── README.md               # Project Documentation
```

---

## 🚀 ขั้นตอนการติดตั้งและเริ่มใช้งาน (Getting Started)

### 1. คลองโปรเจกต์และติดตั้ง Dependencies
```bash
git clone https://github.com/xhier2547/voice-agent-mvp.git
cd voice-agent-mvp

# สร้าง Virtual Environment
python -m venv venv
# สำหรับ Windows Command Prompt / PowerShell:
venv\Scripts\activate

# ติดตั้ง Dependencies
pip install -r requirements.txt
```

### 2. ตั้งค่า Environment Variables (`.env`)
คัดลอกไฟล์ `.env.example` เป็น `.env` แล้วระบุ **GEMINI_API_KEY** จาก [Google AI Studio](https://aistudio.google.com/):

```env
GEMINI_API_KEY=your_actual_gemini_api_key_here
GEMINI_MODEL=models/gemini-2.5-flash-native-audio-latest
GEMINI_VOICE=Aoede
PORT=8000
```

### 3. สตาร์ทระบบ Server
```bash
python run.py
```

เปิดเว็บเบราว์เซอร์ไปที่: **`http://localhost:8000/`**

---

## 📱 วิธีการทดสอบบน Web Sandbox

1. **จำลองการโทรเข้า (Call Simulator)**:
   - กรอก **ชื่อผู้โทร** (เช่น `Vera Sun`) และ **เบอร์โทรศัพท์** (เช่น `081-234-5678`) ฝั่งซ้าย
   - กดปุ่ม **"📞 กดเพื่อโทรออก (Call Now)"** เพื่อเริ่มสาย
2. **โต้ตอบเสียงสด (Speech Interaction)**:
   - ลองถามคำถาม เช่น *"ร้านเปิดกี่โมง?"*, *"ขอรหัสไวไฟหน่อย"*, หรือ *"ช่วยจองโต๊ะ 4 คน วันพรุ่งนี้บ่ายสอง"*
   - AI จะตอบกลับเป็นเสียงพูดสดใน **<250ms** พร้อมบันทึกการจองลงแท็บ **"📜 ประวัติการโทร & การจอง"**
3. **การวางสายอัตโนมัติ**:
   - เมื่อคุยเสร็จ ให้ตอบกลับว่า **"ไม่มีแล้ว ขอบคุณครับ"** AI จะกล่าวขอบคุณและวางสายให้อัตโนมัติ!

---

## 📄 License

MIT License — พัฒนาขึ้นเพื่อเป็นโครงร่างศึกษาและใช้งานสำหรับ AI Voice Agent MVP
