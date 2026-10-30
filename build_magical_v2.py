"""
สร้างจดหมายมหัศจรรย์ (ไม่ตัดโลโก้ใหม่) — ใช้โลโก้ที่ตัดไว้แล้วใน assets/logo_transparent.png

รัน:  python3 build_magical_v2.py

ถ้ายังไม่มีโลโก้ ให้รัน `python3 build_magical.py` ก่อน (หรือ copy ไฟล์โลโก้มาไว้ใน assets/)
"""

from build_magical import build_letter

if __name__ == "__main__":
    build_letter()
