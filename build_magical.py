#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
สร้าง "จดหมายมหัศจรรย์" (magical letter) สำหรับส่งให้ลูกค้าทาง Line

ขั้นตอน:
  1. ตัดโลโก้ NICHE BLOOMS เป็น PNG พื้นหลังโปร่ง (assets/logo_transparent.png)
  2. อ่าน billing_data.json -> สร้าง QR PromptPay ฝังยอดของแต่ละคน
  3. inject ข้อมูลลงใน magical_template.html -> niche_blooms_magical_letter.html

รัน:  python3 build_magical.py
"""
import base64
import json
from pathlib import Path

from PIL import Image

from config import resolve_account_name, resolve_promptpay
from generate_receipts import DATA_FILE, make_qr_png
from promptpay import build_promptpay, classify_promptpay_id, format_promptpay_display

BASE = Path(__file__).parent
TEMPLATE = BASE / "magical_template.html"
OUT = BASE / "niche_blooms_magical_letter.html"
ASSETS = BASE / "assets"
LOGO_PNG = ASSETS / "logo_transparent.png"
RECEIPT_IMG = ASSETS / "receipt_sample.jpg"
QR_TMP = BASE / "output" / "qr"


def crop_logo() -> Path:
    """
    ตัดโลโก้จากภาพใบเสร็จตัวอย่าง -> PNG พื้นหลังโปร่ง

    ถ้าไม่มี assets/receipt_sample.jpg (ไฟล์นี้ถูก gitignore เพราะเป็นข้อมูลลูกค้าจริง)
    จะข้ามการตัดแล้วใช้โลโก้ที่มีอยู่ หรือสร้าง placeholder ขึ้นมาใหม่
    """
    if LOGO_PNG.exists():
        print(f"[SKIP] มีโลโก้อยู่แล้ว: {LOGO_PNG.name}")
        return LOGO_PNG

    if not RECEIPT_IMG.exists():
        print("[WARN] ไม่พบ assets/receipt_sample.jpg — สร้างโลโก้ placeholder แทน")
        _make_placeholder_logo()
        return LOGO_PNG

    img = Image.open(RECEIPT_IMG).convert("RGBA")
    crop = img.crop((170, 30, 670, 235))
    pixels = crop.load()
    cw, ch = crop.size
    for y in range(ch):
        for x in range(cw):
            r, g, b, _alpha = pixels[x, y]
            if r > 195 and g > 185 and b > 155:
                pixels[x, y] = (r, g, b, 0)
    ASSETS.mkdir(parents=True, exist_ok=True)
    crop.save(LOGO_PNG)
    print("[OK] ตัดโลโก้แล้ว (พื้นหลังโปร่ง)")
    return LOGO_PNG


def _make_placeholder_logo() -> None:
    """
    สร้างโลโก้สำรองแบบง่าย ๆ ถ้าไม่มีไฟล์ต้นฉบับให้ตัด

    วิธีที่ดีที่สุดคือใส่ไฟล์โลโก้จริง (assets/logo_transparent.png) ไว้ในโฟลเดอร์ assets/
    ระบบจะเลือกใช้ไฟล์นั้นอัตโนมัติ
    """
    ASSETS.mkdir(parents=True, exist_ok=True)
    width, height = 500, 205
    cream = (250, 246, 238, 255)
    gold = (150, 120, 70, 255)
    img = Image.new("RGBA", (width, height), cream)
    try:
        from PIL import ImageDraw

        draw = ImageDraw.Draw(img)
        draw.rectangle((6, 6, width - 7, height - 7), outline=gold, width=2)
        draw.text((width / 2, 78), "ND NicheBlooms", fill=gold, anchor="mm")
        draw.text((width / 2, 132), "NICHE BLOOMS", fill=gold, anchor="mm")
    except Exception:
        pass
    img.save(LOGO_PNG)
    print(f"[OK] สร้าง placeholder logo: {LOGO_PNG.name}")


def _logo_b64() -> str:
    if not LOGO_PNG.exists():
        return ""
    return "data:image/png;base64," + base64.b64encode(LOGO_PNG.read_bytes()).decode()


def _promptpay_info(meta: dict, pp_id: str, pp_type: str) -> str:
    """ข้อความใต้ QR ในจดหมาย — มาจาก config ไม่ฝังไว้ในเทมเพลต"""
    account_name = resolve_account_name(meta)
    display = format_promptpay_display(pp_id)
    return (
        "<b>พร้อมเพย์</b><br>\n"
        f"        {account_name}<br>\n"
        f"        {display}<br>\n"
        "        สแกน QR — ยอดเงินตรงกับบิลอัตโนมัติ"
    )


def build_letter() -> Path:
    """สร้างจดหมายจาก billing_data.json"""
    if not DATA_FILE.exists():
        raise SystemExit(
            "ไม่พบ billing_data.json — คัดลอก billing_data.example.json มาแก้ข้อมูลจริงก่อน"
        )

    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    meta = data["metadata"]

    pp_id, pp_type = resolve_promptpay(meta)
    if not pp_id:
        raise SystemExit(
            "ไม่พบเลขพร้อมเพย์ — ตั้งค่า PROMPTPAY_ID ในไฟล์ .env (ดู .env.example)"
        )
    if classify_promptpay_id(pp_id) is None:
        raise SystemExit(
            f"เลขพร้อมเพย์ '{format_promptpay_display(pp_id)}' ใช้ไม่ได้ "
            "(ต้องเป็นเบอร์มือถือ 10 / บัตรประชาชน 13 / e-Wallet 15 หลัก)"
        )

    QR_TMP.mkdir(parents=True, exist_ok=True)

    customers = []
    for index, customer in enumerate(data["customers"], 1):
        total = sum(c["amount_due"] for c in customer["contracts"])
        items = [
            {"item": c["item"], "note": c["due_note"], "amount": c["amount_due"]}
            for c in customer["contracts"]
        ]
        ref = f"NB-{meta.get('report_date', '0000-00-00').replace('-', '')}-{index:04X}"
        payload = build_promptpay(
            total,
            pp_id,
            pp_type,
            meta.get("merchant_name", "NICHE BLOOMS"),
            meta.get("merchant_city", "BANGKOK"),
            ref,
        )
        qr_path = make_qr_png(payload, QR_TMP / f"real_{customer['id']}.png")
        qr_b64 = "data:image/png;base64," + base64.b64encode(qr_path.read_bytes()).decode()
        customers.append(
            {
                "id": customer["id"],
                "name": customer["name"],
                "receipt_no": ref,
                "date": meta.get("report_date", ""),
                "items": items,
                "total": total,
                "qr_b64": qr_b64,
            }
        )
        print(f"[OK] {customer['id']} {customer['name']}: {total:,} บาท")

    html = TEMPLATE.read_text(encoding="utf-8")
    html = html.replace("__LOGO_B64__", _logo_b64())
    html = html.replace("__PROMPTPAY_INFO__", _promptpay_info(meta, pp_id, pp_type))
    html = html.replace("__CUSTOMERS_JSON__", json.dumps(customers, ensure_ascii=False))
    OUT.write_text(html, encoding="utf-8")
    print(f"[DONE] {OUT.name}  {OUT.stat().st_size // 1024} KB  |  {len(customers)} ลูกค้า")
    return OUT


if __name__ == "__main__":
    crop_logo()
    build_letter()
