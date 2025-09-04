import os
import google.generativeai as genai
import pandas as pd
import streamlit as st
from prompt import PROMPT_WORKAW
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from document_reader import get_kmutnb_summary

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
def load_kmutnb_summary(path: str) -> str:
    return get_kmutnb_summary(path)

# ----------------- UI -----------------
def clear_history():
    st.session_state["messages"] = [
        {"role": "model", "content": "KMUTNB Library Chatbot สวัสดีครับ สอบถามข้อมูลเกี่ยวกับ KMUTNB Library เรื่องใดครับ"}
    ]
    # เคลียร์แชทเซสชันด้วย เพื่อรีอินเจ็กต์ context ใหม่
    st.session_state.pop("chat_session", None)
    st.rerun()

with st.sidebar:
    if st.button("Clear History"):
        clear_history()

st.title("💬 KMUTNB Library Chatbot สวัสดีครับ")

if "messages" not in st.session_state:
    st.session_state["messages"] = [
        {
            "role": "model",
            "content": "KMUTNB Library Chatbot สวัสดีครับ สอบถามข้อมูลเกี่ยวกับ KMUTNB Library เรื่องใดครับ",
        }
    ]

# ----------------- LOAD DATASET ONCE -----------------
file_path = os.path.join(os.path.dirname(__file__), "DataSetLibraly.pdf")

try:
    file_content = load_kmutnb_summary(file_path)
    if isinstance(file_content, str) and file_content.startswith("Error:"):
        st.error(file_content)
        st.stop()
except Exception as e:
    st.error(f"Error reading file: {e}")
    st.stop()
# ----------------- CREATE / REUSE CHAT SESSION -----------------
# ยัด context จาก PDF เข้า history แค่ครั้งแรก แล้วใช้ session เดิมต่อ ย่นเวลา!
def ensure_chat_session():
    if "chat_session" not in st.session_state:
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
def render_messages(limit_last:int = 20):
    for msg in st.session_state["messages"][-limit_last:]:
        st.chat_message(msg["role"]).write(msg["content"])

render_messages()

# ----------------- HANDLE INPUT -----------------
prompt = st.chat_input(placeholder="พิมพ์คำถามเกี่ยวกับ KMUTNB Library ได้เลยครับ ✨")

def trim_history(max_pairs:int = 8):
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

if prompt:
    generate_response(prompt)
