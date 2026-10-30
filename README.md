# ระบบสร้างใบเสร็จ + QR PromptPay (ฝังยอดชำระ) — NICHE BLOOMS

ระบบสร้างใบเสร็จ PDF พร้อม **QR PromptPay ที่ฝังยอดชำระไว้ใน QR** ลูกค้าสแกนแล้ว
ยอดตรงกับบิลโดยไม่ต้องพิมพ์เอง พร้อม "จดหมายมหัศจรรย์" (HTML) สำหรับส่งให้ลูกค้าทาง Line

---

## เริ่มต้นใช้งาน

```bash
# 1. ติดตั้ง dependency
pip install -r requirements.txt

# 2. เตรียมไฟล์ข้อมูล (คัดลอกตัวอย่างมาแก้ข้อมูลจริง)
cp billing_data.example.json billing_data.json

# 3. ตั้งค่าเลขพร้อมเพย์
cp .env.example .env
#    แก้ PROMPTPAY_ID ใน .env ให้เป็นเลขจริงของร้าน

# 4. สร้างใบเสร็จ + QR
python3 generate_receipts.py

# 5. (ถ้าต้องการ) สร้างจดหมายมหัศจรรย์
python3 build_magical.py
```

ผลลัพธ์จะอยู่ในโฟลเดอร์ `output/` — ใบเสร็จ PDF แยกตามลูกค้า + ไฟล์สรุปรวม + รูป QR

---

## ไฟล์ในโฟลเดอร์นี้

| ไฟล์ | หน้าที่ |
| --- | --- |
| `billing_data.example.json` | **ตัวอย่าง** โครงสร้างข้อมูล (ชื่อลูกค้า รายการ ยอดที่ต้องชำระ) |
| `billing_data.json` | ไฟล์ข้อมูลจริงที่คุณแก้ไข — **ถูก gitignore ไว้** |
| `generate_receipts.py` | อ่าน JSON → สร้างใบเสร็จ PDF + QR PNG |
| `build_magical.py` | ตัดโลโก้ + สร้างจดหมายมหัศจรรย์ (HTML) |
| `build_magical_v2.py` | สร้างจดหมายเฉยๆ (ไม่ตัดโลโก้ใหม่) |
| `magical_template.html` | เทมเพลตจดหมาย (ถูกเติมข้อมูลจาก `billing_data.json`) |
| `promptpay.py` | ตัวสร้าง payload QR ตามมาตรฐาน EMVCo (ล้วน stdlib) |
| `config.py` | อ่านค่าตั้งจาก `.env` / environment (ล้วน stdlib) |
| `tests/` | เทสต์ของตัวสร้าง QR |

## วิธีแก้ข้อมูล

แก้ใน `billing_data.json` แล้วรัน `python3 generate_receipts.py` ใหม่ — QR จะฝังยอดใหม่อัตโนมัติ

- `metadata.shop_name` / `shop_subtitle` — ชื่อร้านและคำโปรยบนใบเสร็จ
- `metadata.report_date` — วันที่ออกบิล
- `metadata.receipt_footer` — ข้อความท้ายใบเสร็จ
- `customers[].name` — ชื่อลูกค้า
- `customers[].contracts[].amount_due` — ยอดที่ต้องชำระจริงในรอบนี้
- `customers[].contracts[].paid_installments` / `total_installments` — จำนวนงวดที่จ่ายแล้ว / ทั้งหมด
- เพิ่ม/ลบลูกค้าหรือสัญญาได้ตามโครงสร้างเดิม

## รูปแบบ QR

- เลขพร้อมเพย์มาจาก `PROMPTPAY_ID` ในไฟล์ `.env` (หรือ environment variable ชื่อเดียวกัน)
- รองรับ: **เบอร์มือถือ 10 หลัก** / **บัตรประชาชน 13 หลัก** / **e-Wallet 15 หลัก**
- ถ้าใช้เบอร์มือถือ ให้ตั้ง `PROMPTPAY_ID_TYPE=phone` (ค่าเริ่มต้นคือ `citizen`)
- ยอดเงินใน QR ตรงกับยอดรวมในใบเสร็จทุกครั้ง ลูกค้าสแกนแล้วไม่ต้องพิมพ์ยอดเอง

> ลำดับการหาค่า: `PROMPTPAY_ID` (environment) → `.env` → `metadata.promptpay_id` ใน `billing_data.json`

### โลโก้

ไฟล์โลโก้โปร่ง `assets/logo_transparent.png` เป็นไฟล์ภาพ (binary) จึง **ไม่ได้ฝังไว้ใน repo**
ถ้าต้องการจดหมายที่ใช้โลโก้ต้นฉบับ ให้วางไฟล์นี้ไว้ในโฟลเดอร์ `assets/` ของโปรเจกต์
ระบบจะใช้ไฟล์นั้นอัตโนมัติ — ถ้าไม่มี ระบบจะสร้างโลโก้ placeholder ขึ้นมาให้แทน (ไม่ error)

## ⚠️ เรื่องความปลอดภัย (สำคัญ)

repo นี้เป็น **public** จึงไม่มีข้อมูลลูกค้าจริงและเลขพร้อมเพย์จริงอยู่ในโค้ด

ไฟล์ต่อไปนี้ถูก `.gitignore` ไว้ — อย่า commit ขึ้นมา:

| ไฟล์ | ทำไมต้องปิด |
| --- | --- |
| `billing_data.json` | ชื่อลูกค้า + ยอดค้างชำระจริง |
| `NicheBlooms_Data.xlsx` | ตารางข้อมูลลูกค้าต้นทาง |
| `output/` | ใบเสร็จ PDF + QR PNG ที่ฝังเลขพร้อมเพย์จริง |
| `assets/receipt_sample.jpg`, `assets/logo1.jpg`, `assets/logo2.jpg` | ภาพใบเสร็จจริง (มีชื่อลูกค้า + เลขพร้อมเพย์) |
| `.env` | เลขพร้อมเพย์จริง |

ถ้าจำเป็นต้องเก็บข้อมูลจริงไว้ใน git ให้เปลี่ยน repo เป็น **private** ก่อน

## ต่อยอดเป็นระบบอัตโนมัติ (Line OA + AI)

ได้ — `output/*.pdf` และ `output/qr/*.png` คือสิ่งที่บอทจะส่งให้ลูกค้า
สามารถเชื่อมต่อกับ Line OA Messaging API + cron job ส่งบิล/เตือนชำระ + AI ตอบแชท + ตรวจสลิปอัตโนมัติได้

## พัฒนา / ทดสอบ

```bash
pip install ruff pytest
ruff check .
pytest tests/
```

CI จะรัน `ruff check .` และ `pytest tests/` ทุกครั้งที่ push
