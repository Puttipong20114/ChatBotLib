# document_reader.py
from typing import List
import os

# สำหรับ DOCX
try:
    import docx  # python-docx
except Exception:
    docx = None

# สำหรับ PDF (ตัวเลือกที่ 1: pdfplumber)
try:
    import pdfplumber
except Exception:
    pdfplumber = None

# สำหรับ PDF (ตัวเลือกที่ 2: pypdf เป็น fallback)
try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

MAX_CHARS = 120_000  # ป้องกันข้อความยาวเกิน ส่งเข้าโมเดลลำบาก

def _clean_text(text: str) -> str:
    # เก็บเฉพาะข้อความ อ่านง่าย ตัดช่องว่างซ้ำ/ป้องกัน \x00
    if not text:
        return ""
    t = text.replace("\x00", "").replace("\r", "")
    # ลดช่องว่างซ้ำ
    return "\n".join(line.strip() for line in t.split("\n") if line.strip())

def _read_docx(path: str) -> str:
    if docx is None:
        return "Error: python-docx is not installed. Please install it with: pip install python-docx"
    try:
        d = docx.Document(path)
        parts: List[str] = []
        for p in d.paragraphs:
            parts.append(p.text)
        # ตาราง (ถ้ามี)
        for table in d.tables:
            for row in table.rows:
                parts.append(" | ".join(cell.text for cell in row.cells))
        text = "\n".join(parts)
        return _clean_text(text)[:MAX_CHARS]
    except Exception as e:
        return f"Error: cannot read DOCX -> {e}"

def _read_pdf_plumber(path: str) -> str:
    if pdfplumber is None:
        return None
    try:
        parts: List[str] = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                txt = page.extract_text() or ""
                parts.append(txt)
        text = "\n".join(parts)
        text = _clean_text(text)
        return text[:MAX_CHARS]
    except Exception:
        return None  # ค่อยไปลองวิธีอื่น

def _read_pdf_pypdf(path: str) -> str:
    if PdfReader is None:
        return None
    try:
        reader = PdfReader(path)
        parts: List[str] = []
        for page in reader.pages:
            txt = page.extract_text() or ""
            parts.append(txt)
        text = "\n".join(parts)
        text = _clean_text(text)
        return text[:MAX_CHARS]
    except Exception:
        return None

def _read_pdf(path: str) -> str:
    # ลองด้วย pdfplumber ก่อน (แม่นกว่าในหลาย ๆ เคส) แล้วค่อย fallback เป็น pypdf
    text = _read_pdf_plumber(path)
    if text is None or len(text.strip()) == 0:
        text = _read_pdf_pypdf(path)
    if text is None or len(text.strip()) == 0:
        return "Error: cannot extract text from PDF (try another file or ensure it's not scanned image)."
    return text

def get_kmutnb_summary(file_path: str) -> str:
    """
    อ่านไฟล์ dataset (.pdf หรือ .docx) แล้วคืนค่าเป็นข้อความแบบสรุป (plain text)
    ถ้าเกิดปัญหาคืนค่า string ที่ขึ้นต้นด้วย 'Error:' เหมือนเดิม เพื่อให้โค้ดหลักจัดการได้
    """
    if not os.path.exists(file_path):
        return f"Error: file not found -> {file_path}"

    ext = os.path.splitext(file_path)[1].lower()

    try:
        if ext == ".pdf":
            return _read_pdf(file_path)
        elif ext == ".docx":
            return _read_docx(file_path)
        else:
            return "Error: unsupported file type. Please use .pdf or .docx"
    except Exception as e:
        return f"Error: {e}"
