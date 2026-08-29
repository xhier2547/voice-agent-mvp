# 🎙️ APEX AGENT — Enterprise AI Voice Platform

> **APEX AGENT** คือแพลตฟอร์มผู้ช่วยเสียงอัจฉริยะ (AI Voice Agent) ระดับองค์กรที่รองรับการโต้ตอบด้วยเสียงสดแบบสองทางความหน่วงต่ำระดับมิลลิวินาที (Sub-second Latency) ขับเคลื่อนด้วย **Google Gemini Live Multimodal Audio API**, **FastAPI**, **WebSockets**, **ChromaDB Vector Store** และ **ระบบจัดการคลังความรู้ Dynamic Knowledge Management (PDF / CSV / TXT)**

---

## ✨ จุดเด่นและฟีเจอร์หลักของระบบ (Current Features)

### 1. ⚡ สตรีมมิ่งเสียงสองทางแบบเรียลไทม์ (Bidirectional Audio Streaming)
- **สตรีมมิ่งเสียงความเร็วสูง**: รองรับการส่งเสียงไมโครโฟน 16kHz PCM (Mono) จากเบราว์เซอร์ และรับเสียงตอบกลับคุณภาพสูง 24kHz PCM จาก Gemini Live API แบบ Full-Duplex
- **ประมวลผลเสียงแบบ Native Audio**: ขับเคลื่อนด้วยโมเดล `models/gemini-2.5-flash-native-audio-latest` เข้าใจภาษาไทยและภาษาอังกฤษอย่างลึกซึ้ง ไม่ต้องแปลงเป็นข้อความก่อน (No STT/TTS Pipeline Latency)
- **ระบบแทรกเสียง (Barge-in / Interruption)**: เมื่อผู้ใช้พูดแทรกขณะ AI กำลังพูด ระบบจะหยุดเล่นเสียงทันทีและกลับมารับฟังคำสั่งใหม่โดยอัตโนมัติ

---

### 2. 📁 ระบบจัดการคลังความรู้อัตโนมัติ (Dynamic Knowledge Management & Vector RAG)
- **อัปโหลดเอกสารผ่านหน้าเว็บ (Drag & Drop)**:
  - 📄 **PDF**: สกัดข้อความจากเอกสาร PDF เมนู นโยบายบริษัท ด้วย `pypdf`
  - 📊 **CSV**: แปลงข้อมูลรายการสินค้า แคตตาล็อก ราคา เป็นตารางความรู้
  - 📝 **TXT**: สกัดและจัดระเบียบเนื้อหาข้อความทั่วไป
- **ระบบตัด Chunk อัจฉริยะ (`semantic_chunk_text`)**: ตัดแบ่งเนื้อหาขนาดยาวพร้อม Overlap เพื่อคงความสมบูรณ์ของความหมาย
- **Vector Database (ChromaDB + Gemini Embeddings)**:
  - ใช้ `models/gemini-embedding-001` (3,072 Dimensions) สร้าง Vector Embeddings
  - ค้นหาคำตอบแบบ Semantic Search แม่นยำ แม้ใช้คำถามที่ไม่ตรงกับคีย์เวิร์ด
  - มีระบบ In-Memory Fast Cache (<0.1ms) และ Fallback Search เมื่อออฟไลน์
- **แก้ไขข้อมูลพื้นฐานผ่าน UI**: ปรับแต่งข้อมูลร้านค้า, เวลาทำการ, รหัส Wi-Fi, โปรโมชั่น และ FAQ บนแท็บ **Configure (Admin)** พร้อม Sync เข้า ChromaDB ทันที

---

### 3. 🛠️ เครื่องมือและการทำงานอัตโนมัติ (Function Calling & Tool Integrations)
- 🔍 **`query_knowledge`**: ค้นหาข้อมูลเชิงลึกจากคลังความรู้ Vector Database
- 📅 **`book_table`**: รับจองโต๊ะ/นัดหมาย และบันทึกลง `data/reservations.json` ทันที
- 🎁 **`check_member_points`**: ตรวจสอบคะแนนสะสมและสิทธิ์สมาชิกผ่านเบอร์โทรศัพท์
- 📲 **`send_sms_info`**: จำลองการส่ง SMS สรุปข้อมูลและลิงก์เข้ามือถือลูกค้า
- 📞 **`transfer_call`**: ส่งต่อสายไปยังเจ้าหน้าที่หรือเบอร์ปลายทางผ่าน Twilio Call Transfer
- 🛑 **`end_call`**: ตรวจจับความประสงค์จบการสนทนา กล่าวขอบคุณ และวางสายอัตโนมัติ พร้อมบันทึกเสียงและประวัติการโทร

---

### 4. 🧠 ระบบจดจำลูกค้า & บันทึกเสียงการโทร (Customer Memory & Audio Recording)
- **จดจำลูกค้าเดิม (Caller Memory)**: เมื่อเบอร์เดิมโทรเข้ามา ระบบจะดึงประวัติการโทรและบริบทก่อนหน้ามาทักทายอย่างเป็นกันเอง
- **บันทึกเสียงสนทนาสด (.WAV)**: รวมเสียงพูดของลูกค้าและเสียง AI ลงไฟล์ในโฟลเดอร์ `recordings/` แบบเรียลไทม์
- **วิเคราะห์อารมณ์และเจตนา (Call Intelligence)**: สรุปบทสนทนา (Summary), ตรวจจับอารมณ์ (Sentiment: Positive/Neutral/Negative) และระบุเจตนาหลัก (Primary Intent) บันทึกลง `data/call_logs.json`
- **เครื่องเล่นเสียงบนเว็บ (Audio Player)**: สามารถกดฟังเสียงย้อนหลังได้จากตารางประวัติการโทรทันที

---

### 5. 📱 หน้าจอจำลองการโทร & แดชบอร์ด (Simulator & Modern Dashboard)
- **iOS Phone Call Simulator**: หน้าต่างจำลอง iPhone สไตล์กระจกหรูหรา (Glassmorphism):
  - หน้าโทรสายหลักพร้อมจับเวลาและแสดงสถานะเสียงสด
  - แป้นกดตัวเลข DTMF (Keypad View)
  - โหมด FaceTime AI Hologram Orb View
  - หน้ารายชื่อติดต่อด่วน (Contacts View)
- **Floating Call Mini-Dock**: แถบควบคุมขนาดเล็กมุมจอลอยตัวเมื่อย่อหน้าจอโทรศัพท์
- **Live Latency & VAD Console**: แสดงเวลาตอบสนอง (VAD / Speech Start / Playback Start / Tool Invocations) แบบเรียลไทม์
- **สถิติและกราฟวิเคราะห์ (Dashboard)**: แสดงปริมาณการโทร อัตราความพึงพอใจ และช่วงเวลาที่มีการโทรเข้าสูงสุดผ่าน Chart.js

---

### 6. ☎️ การเชื่อมต่อสัญญาณโทรศัพท์จริง (Telephony / Twilio Integration)
- มี Endpoint WebSocket `/ws/media-stream` สำหรับรับสายเข้าจากเบอร์โทรศัพท์จริงผ่าน **Twilio Voice Media Streams**
- รองรับการแปลงสัญญาณเสียงสองทาง (Transcoding) ระหว่าง 8kHz G.711 $\mu$-law และ 16kHz/24kHz Linear PCM

---

## 📂 โครงสร้างโฟลเดอร์และไฟล์ (Project Architecture)

```text
AI_VOICE/
├── app/
│   ├── __init__.py
│   ├── main.py             # FastAPI Server, WebSocket Media Stream, Upload & REST APIs
│   ├── config.py           # ตัวแปรระบบ, Model Config และ Environment Variables
│   ├── audio.py            # การบันทึกไฟล์ WAV (CallAudioRecorder) และ Transcoding G.711 / PCM
│   ├── gemini_client.py    # Gemini Live API Client, ChromaDB Vector Store & Function Tools
│   ├── twilio_client.py    # Twilio REST API สำหรับการโอนสาย (Call Transfer)
│   └── templates/
│       ├── index.html      # หน้าจอหลัก Dashboard, Console Sandbox, Dynamic RAG & Logs
│       └── phone_modal.html # คอมโพเนนต์หน้าต่างจำลองโทรศัพท์ iOS Simulator
├── data/
│   ├── documents.json      # ฐานข้อมูลเมตาดาตาเอกสาร Dynamic Knowledge ที่อัปโหลด
│   ├── knowledge.json      # ข้อมูลความรู้พื้นฐานร้านค้า, FAQ, โปรโมชั่น
│   ├── call_logs.json      # ประวัติการโทร, ความจำลูกค้า, บทสนทนา และผลวิเคราะห์ Sentiment
│   ├── reservations.json   # รายการจองโต๊ะและการนัดหมาย
│   └── chroma_db/          # โฟลเดอร์เก็บ Vector Database ของ ChromaDB (Local Persistent)
├── recordings/             # โฟลเดอร์จัดเก็บไฟล์เสียงบันทึกการโทร (.wav)
├── run.py                  # สคริปต์รันเซิร์ฟเวอร์ Uvicorn
├── requirements.txt        # รายการแพ็กเกจ Python Dependencies
├── .env.example            # ตัวอย่างไฟล์ตั้งค่า API Key
└── README.md               # เอกสารประกอบโปรเจกต์
```

---

## 🚀 ขั้นตอนการติดตั้งและเริ่มใช้งาน (Getting Started)

### 1. โคลนโปรเจกต์และสร้าง Virtual Environment
```bash
git clone https://github.com/xhier2547/voice-agent-mvp.git
cd voice-agent-mvp

# สร้างและเปิดใช้งาน Virtual Environment
python -m venv venv
# สำหรับ Windows (PowerShell):
venv\Scripts\Activate.ps1
# หรือ Command Prompt:
venv\Scripts\activate.bat
```

### 2. ติดตั้ง Dependencies
```bash
pip install -r requirements.txt
```

### 3. กำหนดค่า Environment Variables (`.env`)
คัดลอกไฟล์ `.env.example` เป็น `.env` และใส่ **Gemini API Key** ที่ได้รับจาก [Google AI Studio](https://aistudio.google.com/):

```env
GEMINI_API_KEY=AIzaSy...your_gemini_api_key...
GEMINI_MODEL=models/gemini-2.5-flash-native-audio-latest
GEMINI_VOICE=Aoede
PORT=8000
```

*(ตัวเลือกเสริม: หากต้องการทดสอบเบอร์โทรจริง สามารถระบุ `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, และ `TRANSFER_NUMBER` เพิ่มเติมได้)*

### 4. รันเซิร์ฟเวอร์
```bash
py .\run.py
```

เปิดเว็บเบราว์เซอร์ไปที่:
👉 **`http://localhost:8000`**

---

## 🧪 คู่มือการทดสอบระบบ (User Walkthrough)

### 1. ทดสอบการคุยด้วยเสียงสด (Live Voice Testing)
1. ไปที่แท็บ **Console Sandbox** หรือกดไอคอนโทรศัพท์ด้านบนขวา
2. ระบุชื่อผู้โทร (เช่น `Vera Sun`) และเบอร์โทรศัพท์
3. กดปุ่ม **"จำลองโทรเข้า (Call)"** แล้วอนุญาตให้เบราว์เซอร์เข้าถึงไมโครโฟน
4. พูดคุยกับบอทด้วยภาษาไทยหรืออังกฤษอย่างเป็นธรรมชาติ เช่น:
   - *"สวัสดีครับ ที่ร้านเปิดปิดกี่โมง มีที่จอดรถไหม"*
   - *"ช่วยแนะนำโปรโมชั่นเด็ดๆ เดือนนี้หน่อย"*
   - *"อยากจองโต๊ะสำหรับ 3 คน วันพรุ่งนี้ตอน 18:30 น."*
5. เมื่อสนทนาเสร็จ สามารถพูดว่า *"ขอบคุณครับ แค่นี้ก่อนนะ"* บอทจะกล่าวขอบคุณและ**วางสายให้อัตโนมัติ**

### 2. ทดสอบอัปโหลดเอกสารความรู้ (Dynamic Knowledge RAG)
1. ไปที่แท็บ **Configure (Admin)**
2. ลากไฟล์เอกสาร `.pdf`, `.csv` หรือ `.txt` มาวางในกล่อง **Dropzone**
3. ระบบจะสกัดข้อความ ตัดเป็น Chunk และสร้าง Vector Embeddings เข้า ChromaDB ทันที
4. กลับไปที่โทรศัพท์และถามคำถามเกี่ยวกับเนื้อหาในเอกสารที่เพิ่งอัปโหลด AI จะค้นหาและตอบข้อมูลจากเอกสารได้อย่างแม่นยำ

### 3. ตรวจสอบประวัติการโทรและฟังเสียงย้อนหลัง
1. ไปที่แท็บ **Calls & Reservations**
2. ตรวจสอบรายการประวัติการโทร ข้อมูล Intent, Sentiment และบทสนทนาย้อนหลัง
3. กดปุ่ม **Play Audio** เพื่อเปิดฟังเสียงบันทึกการโทรที่ถูกบันทึกไว้ในโฟลเดอร์ `recordings/`

---

## 🔒 ข้อกำหนดและคำแนะนำด้านเทคนิค (Technical Notes)
- **เบราว์เซอร์**: แนะนำให้ใช้ Google Chrome, Microsoft Edge หรือ Safari เวอร์ชันล่าสุด เพื่อรองรับ Web Audio API และสิทธิ์ไมโครโฟนอย่างสมบูรณ์
- **โมเดลเวกเตอร์**: ระบบใช้ `models/gemini-embedding-001` ความยาว 3072 มิติ หากไม่มีการเชื่อมต่ออินเทอร์เน็ต ระบบมี In-Memory Cache และ Fallback Engine สำรองให้โดยอัตโนมัติ

---

## 📄 ใบอนุญาต (License)
MIT License — พัฒนาและเผยแพร่สำหรับการศึกษาและใช้งานเป็นโซลูชัน AI Voice Agent
