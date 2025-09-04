import os
import google.generativeai as genai
import pandas as pd
import streamlit as st
from prompt import PROMPT_WORKAW
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from document_reader import get_kmutnb_summary
import tempfile

# ✅ ตามที่ขอ: ไม่แตะบรรทัดนี้
genai.configure(api_key="AIzaSyD9ycgboJDlkj-JoyRJy8QKaAagEq3TAEQ")

# ----------------- CONFIG -----------------
generation_config = {
    "temperature": 0.1,
    "top_p": 0.95,
    "top_k": 64,
    # "max_output_tokens": 8192,
    "max_output_tokens": 512,  # ลดเพื่อกัน rate limit และตอบไวขึ้น
    "response_mime_type": "text/plain",
    "candidate_count": 1,      # ให้รุ่นตอบมาช้อยส์เดียว เร็วขึ้น
}

SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE
}

# สร้าง model แค่ครั้งเดียว
@st.cache_resource(show_spinner=False)
def get_model():
    return genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        safety_settings=SAFETY_SETTINGS,
        generation_config=generation_config,
        system_instruction=PROMPT_WORKAW
    )

model = get_model()

# ----------------- IO & CACHE -----------------
# อ่าน/สรุป PDF แล้ว cache ผลลัพธ์ กัน I/O หนัก ๆ ตอน rerun
@st.cache_data(show_spinner=True)
def load_kmutnb_summary_from_bytes(file_bytes: bytes, filename: str) -> str:
    """สร้าง temporary file จาก uploaded bytes แล้วประมวลผล"""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(file_bytes)
            tmp_path = tmp_file.name
        
        # ใช้ temporary file path
        result = get_kmutnb_summary(tmp_path)
        
        # ลบ temporary file
        os.unlink(tmp_path)
        
        return result
    except Exception as e:
        return f"Error processing file: {str(e)}"

# Alternative: อ่านจากไฟล์ที่อยู่ใน repository (สำหรับกรณีที่ต้องการ default file)
@st.cache_data(show_spinner=True)
def load_default_kmutnb_summary() -> str:
    """อ่านไฟล์ default ที่อยู่ใน project directory"""
    # หาไฟล์ในโฟลเดอร์เดียวกับ script หรือ subfolder
    possible_paths = [
        "DataSetLibraly.pdf",  # ใน root folder
        "data/DataSetLibraly.pdf",  # ใน data folder
        "workaw/DataSetLibraly.pdf",  # ใน workaw folder
        os.path.join(os.path.dirname(__file__), "DataSetLibraly.pdf"),  # same dir as script
        os.path.join(os.path.dirname(__file__), "data", "DataSetLibraly.pdf"),
        os.path.join(os.path.dirname(__file__), "workaw", "DataSetLibraly.pdf"),
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return get_kmutnb_summary(path)
    
    return "Error: ไม่พบไฟล์ DataSetLibraly.pdf ในระบบ กรุณาอัปโหลดไฟล์"

# ----------------- UI -----------------
def clear_history():
    st.session_state["messages"] = [
        {"role": "model", "content": "KMUTNB Library Chatbot สวัสดีครับ สอบถามข้อมูลเกี่ยวกับ KMUTNB Library เรื่องใดครับ"}
    ]
    # เคลียร์แชทเซสชันด้วย เพื่อรีอินเจ็กต์ context ใหม่
    st.session_state.pop("chat_session", None)
    st.rerun()

# ----------------- SIDEBAR -----------------
with st.sidebar:
    st.header("📁 File Management")
    
    # File uploader
    uploaded_file = st.file_uploader(
        "อัปโหลดไฟล์ PDF (ข้อมูล KMUTNB Library)",
        type=['pdf'],
        help="อัปโหลดไฟล์ PDF ที่มีข้อมูล KMUTNB Library"
    )
    
    use_default = st.checkbox(
        "ใช้ไฟล์ default ในระบบ", 
        value=True if not uploaded_file else False,
        help="ใช้ไฟล์ DataSetLibraly.pdf ที่มีอยู่ในระบบ"
    )
    
    st.divider()
    
    if st.button("Clear History", use_container_width=True):
        clear_history()
    
    # แสดงสถานะไฟล์
    st.subheader("📊 File Status")
    if uploaded_file:
        st.success(f"✅ อัปโหลด: {uploaded_file.name}")
        st.info(f"📊 ขนาด: {uploaded_file.size:,} bytes")
    elif use_default:
        st.info("🔄 ใช้ไฟล์ default ในระบบ")
    else:
        st.warning("⚠️ ยังไม่มีไฟล์")

# ----------------- MAIN UI -----------------
st.title("💬 KMUTNB Library Chatbot")

if "messages" not in st.session_state:
    st.session_state["messages"] = [
        {
            "role": "model",
            "content": "KMUTNB Library Chatbot สวัสดีครับ สอบถามข้อมูลเกี่ยวกับ KMUTNB Library เรื่องใดครับ",
        }
    ]

# ----------------- LOAD DATASET -----------------
file_content = None

try:
    if uploaded_file:
        # ใช้ไฟล์ที่อัปโหลด
        st.info("🔄 กำลังประมวลผลไฟล์ที่อัปโหลด...")
        file_bytes = uploaded_file.read()
        file_content = load_kmutnb_summary_from_bytes(file_bytes, uploaded_file.name)
    elif use_default:
        # ใช้ไฟล์ default
        st.info("🔄 กำลังโหลดไฟล์ default...")
        file_content = load_default_kmutnb_summary()
    
    if file_content and file_content.startswith("Error:"):
        st.error(file_content)
        st.warning("กรุณาอัปโหลดไฟล์ PDF ที่ถูกต้อง หรือตรวจสอบไฟล์ default ในระบบ")
        file_content = None
    elif file_content:
        st.success("✅ โหลดข้อมูลเรียบร้อยแล้ว")
        
except Exception as e:
    st.error(f"เกิดข้อผิดพลาดในการอ่านไฟล์: {e}")
    file_content = None

# ถ้าไม่มีไฟล์ให้หยุดการทำงาน
if not file_content:
    st.stop()

# ----------------- CREATE / REUSE CHAT SESSION -----------------
def ensure_chat_session():
    if "chat_session" not in st.session_state or not file_content:
        # ประกอบ history เริ่มต้น: system เปิดบท + user ใส่สรุปจาก PDF เป็น context
        base_history = [
            {
                "role": "model",
                "parts": [{"text": "KMUTNB Library Chatbot พร้อมให้บริการข้อมูลจากเอกสารที่แนบไว้"}],
            },
            {
                "role": "user",
                "parts": [{
                    "text": (
                        "นี่คือสรุปข้อมูล KMUTN Library ที่ต้องใช้ตอบคำถามต่อไปนี้ "
                        "(ให้ใช้เป็นบริบท ไม่ต้องท่องจำทั้งหมด):\n\n"
                        + file_content
                    )
                }],
            },
        ]
        st.session_state["chat_session"] = model.start_chat(history=base_history)

ensure_chat_session()

# ----------------- RENDER HISTORY (โชว์เฉพาะท้าย ๆ ให้ไว) -----------------
def render_messages(limit_last: int = 20):
    for msg in st.session_state["messages"][-limit_last:]:
        st.chat_message(msg["role"]).write(msg["content"])

render_messages()

# ----------------- HANDLE INPUT -----------------
prompt = st.chat_input(
    placeholder="พิมพ์คำถามเกี่ยวกับ KMUTNB Library ได้เลยครับ ✨",
    disabled=not file_content
)

def trim_history(max_pairs: int = 8):
    """
    จำกัดความยาว history ใน UI (และที่เราจะส่งต่อเป็นข้อความสรุป)
    เก็บแค่คู่สนทนาท้าย ๆ ลด token → เร็วขึ้น
    """
    msgs = st.session_state["messages"]
    # เก็บเฉพาะท้าย ๆ
    if len(msgs) > (2 * max_pairs + 1):  # model msg แรก + n*2 (user/model)
        st.session_state["messages"] = msgs[-(2 * max_pairs + 1):]

def generate_response(user_text: str):
    # อัปเดต UI history
    st.session_state["messages"].append({"role": "user", "content": user_text})
    st.chat_message("user").write(user_text)

    # โหมดสั้น ๆ ขอบคุณ
    if user_text.lower().startswith("add") or user_text.lower().endswith("add"):
        reply = "ขอบคุณสำหรับคำแนะนำครับ"
        st.session_state["messages"].append({"role": "model", "content": reply})
        st.chat_message("model").write(reply)
        trim_history()
        return

    # ส่งข้อความพร้อมสตรีมผลตอบกลับ (latency ต่ำกว่าแบบ non-stream)
    placeholder = st.chat_message("model")
    stream_box = placeholder.empty()
    collected = []

    try:
        for chunk in st.session_state["chat_session"].send_message(user_text, stream=True):
            piece = getattr(chunk, "text", None)
            if piece:
                collected.append(piece)
                stream_box.write("".join(collected))
        final_text = "".join(collected).strip() or "ขออภัย ระบบไม่พบคำตอบที่เหมาะสมในตอนนี้"
    except Exception as e:
        final_text = f"เกิดข้อผิดพลาดในการตอบ: {e}"

    st.session_state["messages"].append({"role": "model", "content": final_text})
    trim_history()

if prompt and file_content:
    generate_response(prompt)