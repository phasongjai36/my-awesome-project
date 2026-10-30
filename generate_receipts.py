#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
สร้างใบเสร็จ PDF + QR PromptPay (ฝังยอดชำระ) จาก billing_data.json

วิธีใช้:
  1. คัดลอก billing_data.example.json เป็น billing_data.json แล้วแก้ข้อมูลจริง
  2. ตั้งค่า PROMPTPAY_ID ในไฟล์ .env (ดู .env.example)
  3. รัน: python3 generate_receipts.py

หมายเหตุ: billing_data.json, .env และโฟลเดอร์ output/ ถูก .gitignore ไว้
เพราะเป็นข้อมูลลูกค้าและเลขพร้อมเพย์จริง — อย่าฝากขึ้น repo สาธารณะ
"""
import json
from pathlib import Path

import qrcode
from reportlab.lib.pagesizes import A4, A5
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from config import BASE, resolve_promptpay
from promptpay import build_promptpay, classify_promptpay_id, format_promptpay_display

DATA_FILE = BASE / "billing_data.json"
OUT = BASE / "output"
QR_DIR = OUT / "qr"

# ---------- ฟอนต์ไทย (ค้นหาอัตโนมัติ, ถ้าไม่เจอจะ fallback ไป Helvetica) ----------
FONT_CANDIDATES_REG = [
    "/usr/share/fonts/truetype/tlwg/Garuda.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansThai-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansThai-Regular.ttf",
    "/usr/share/fonts/truetype/tlwg/Loma.ttf",
]
FONT_CANDIDATES_BOLD = [
    "/usr/share/fonts/truetype/tlwg/Garuda-Bold.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansThai-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansThai-Bold.ttf",
    "/usr/share/fonts/truetype/tlwg/Loma-Bold.ttf",
]

F = "Helvetica"
FB = "Helvetica-Bold"


def _find_font(candidates: list[str]) -> str | None:
    for path in candidates:
        if Path(path).exists():
            return path
    return None


def _register_fonts() -> None:
    """ลงทะเบียนฟอนต์ไทย ถ้ามีในเครื่อง — ไม่มีก็ใช้ Helvetica ไปก่อน (ไม่ crash)"""
    global F, FB
    regular = _find_font(FONT_CANDIDATES_REG)
    if not regular:
        return
    bold = _find_font(FONT_CANDIDATES_BOLD) or regular
    try:
        pdfmetrics.registerFont(TTFont("NotoThai", regular))
        pdfmetrics.registerFont(TTFont("NotoThai-Bold", bold))
    except Exception:
        return
    F, FB = "NotoThai", "NotoThai-Bold"


_register_fonts()


def make_qr_png(payload: str, path: Path) -> Path:
    qr = qrcode.QRCode(box_size=10, border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(str(path))
    return path


def fmt(baht: float) -> str:
    return f"{baht:,.2f}"


# ---------- วาดใบเสร็จ A5 ----------
def draw_receipt(customer: dict, meta: dict, pp_id: str, pp_type: str) -> tuple[Path, float]:
    cid = customer["id"]
    name = customer["name"]
    contracts = customer["contracts"]
    total = sum(c["amount_due"] for c in contracts)
    ref = f"INV-{cid}"
    safe_name = customer["name"].replace(" ", "").replace("คุณ", "")
    out_pdf = OUT / f"receipt_{cid}_{safe_name}.pdf"

    width, height = A5  # 148 x 210 mm
    margin = 10 * mm
    pdf = canvas.Canvas(str(out_pdf), pagesize=A5)

    y = height - margin
    pdf.setFont(FB, 15)
    pdf.drawCentredString(width / 2, y, meta["shop_name"])
    y -= 6 * mm
    pdf.setFont(F, 9)
    pdf.drawCentredString(width / 2, y, meta["shop_subtitle"])
    y -= 5 * mm
    pdf.setFont(F, 8.5)
    pdf.drawCentredString(width / 2, y, f"วันที่ออก: {meta['report_date']}   |   เลขที่: {ref}")
    y -= 4 * mm
    pdf.setDash(2, 2)
    pdf.line(margin, y, width - margin, y)
    pdf.setDash()
    y -= 6 * mm

    pdf.setFont(FB, 11)
    pdf.drawString(margin, y, f"ผู้รับบิล: {name}")
    y -= 6 * mm

    col_item = margin
    col_amt = width - margin
    pdf.setFont(FB, 9)
    pdf.drawString(col_item, y, "รายการ / หมายเหตุ")
    pdf.drawRightString(col_amt, y, "ยอด (บาท)")
    y -= 3 * mm
    pdf.line(margin, y, width - margin, y)
    y -= 5 * mm

    pdf.setFont(F, 9)
    for contract in contracts:
        paid = contract["paid_installments"]
        total_installments = contract["total_installments"]
        pdf.drawString(
            col_item, y, f"• {contract['item']}  (จ่ายแล้ว {paid}/{total_installments} งวด)"
        )
        pdf.drawRightString(col_amt, y, fmt(contract["amount_due"]))
        y -= 4.5 * mm
        if contract.get("due_note"):
            pdf.setFont(F, 7.5)
            pdf.drawString(col_item + 3 * mm, y, contract["due_note"])
            pdf.setFont(F, 9)
            y -= 4 * mm
        y -= 1 * mm

    y -= 2 * mm
    pdf.setDash(2, 2)
    pdf.line(margin, y, width - margin, y)
    pdf.setDash()
    y -= 6 * mm
    pdf.setFont(FB, 13)
    pdf.drawString(margin, y, "ยอดรวมที่ต้องชำระ")
    pdf.setFont(FB, 15)
    pdf.drawRightString(width - margin, y, f"{fmt(total)} บาท")
    y -= 8 * mm

    qr_payload = build_promptpay(
        total,
        pp_id,
        pp_type,
        meta.get("merchant_name", "PAYMENT"),
        meta.get("merchant_city", "BANGKOK"),
        ref,
    )
    qr_path = make_qr_png(qr_payload, QR_DIR / f"qr_{cid}.png")

    box_top = y
    box_h = 62 * mm
    pdf.setStrokeColorRGB(0.2, 0.2, 0.2)
    pdf.roundRect(margin, box_top - box_h, width - 2 * margin, box_h, 3 * mm, stroke=1, fill=0)
    pdf.setFont(FB, 10)
    pdf.drawCentredString(width / 2, box_top - 6 * mm, "สแกน QR PromptPay เพื่อชำระเงิน")
    pdf.setFont(F, 8)
    pdf.drawCentredString(
        width / 2,
        box_top - 10.5 * mm,
        "ยอดเงินถูกฝังใน QR อัตโนมัติ — สแกนแล้วยอดตรงกับบิล",
    )

    qr_size = 38 * mm
    pdf.drawImage(
        str(qr_path),
        width / 2 - qr_size / 2,
        box_top - 12 * mm - qr_size,
        width=qr_size,
        height=qr_size,
    )
    pdf.setFont(FB, 11)
    pdf.drawCentredString(width / 2, box_top - box_h + 6 * mm, f"ยอดชำระ: {fmt(total)} บาท")

    y = box_top - box_h - 6 * mm
    pdf.setFont(F, 7.5)
    footer = meta.get("receipt_footer", "")
    line = ""
    for char in footer:
        if pdfmetrics.stringWidth(line + char, F, 7.5) > (width - 2 * margin):
            pdf.drawCentredString(width / 2, y, line)
            y -= 3.5 * mm
            line = char
        else:
            line += char
    if line:
        pdf.drawCentredString(width / 2, y, line)

    pdf.showPage()
    pdf.save()
    return out_pdf, total


# ---------- สรุป A4 ----------
def draw_summary(rows: list[tuple[str, int, float]], grand_total: float, meta: dict) -> Path:
    out_pdf = OUT / "00_summary_all_customers.pdf"
    width, height = A4
    margin = 15 * mm
    pdf = canvas.Canvas(str(out_pdf), pagesize=A4)

    y = height - margin
    pdf.setFont(FB, 16)
    pdf.drawString(margin, y, "สรุปยอดเรียกเก็บเงิน — ทุกลูกค้า")
    y -= 7 * mm
    pdf.setFont(F, 9)
    pdf.drawString(
        margin, y, f"วันที่ออก: {meta['report_date']}   |   ยอดรวมทั้งหมด: {fmt(grand_total)} บาท"
    )
    y -= 4 * mm
    pdf.setFont(F, 8)
    pdf.drawString(
        margin,
        y,
        "หมายเหตุ: ยอดในไฟล์นี้เป็นค่าเริ่มต้น (1 งวด/สัญญา) — กรุณาแก้ไข amount_due ใน billing_data.json แล้วรันสคริปต์ใหม่",
    )
    y -= 6 * mm
    pdf.setFont(FB, 9.5)
    pdf.drawString(margin, y, "ลูกค้า")
    pdf.drawString(margin + 55 * mm, y, "จำนวนสัญญา")
    pdf.drawRightString(width - margin, y, "ยอดชำระ (บาท)")
    y -= 3 * mm
    pdf.line(margin, y, width - margin, y)
    y -= 6 * mm
    pdf.setFont(F, 9.5)
    for name, count, total in rows:
        pdf.drawString(margin, y, name)
        pdf.drawString(margin + 55 * mm, y, str(count))
        pdf.drawRightString(width - margin, y, fmt(total))
        y -= 6 * mm
        if y < margin + 20 * mm:
            pdf.showPage()
            y = height - margin
            pdf.setFont(F, 9.5)
    y -= 3 * mm
    pdf.line(margin, y, width - margin, y)
    y -= 7 * mm
    pdf.setFont(FB, 12)
    pdf.drawString(margin, y, "รวมทั้งหมด")
    pdf.drawRightString(width - margin, y, f"{fmt(grand_total)} บาท")
    pdf.showPage()
    pdf.save()
    return out_pdf


def main() -> None:
    OUT.mkdir(exist_ok=True)
    QR_DIR.mkdir(parents=True, exist_ok=True)

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
    detected = classify_promptpay_id(pp_id)
    if detected is None:
        raise SystemExit(
            f"เลขพร้อมเพย์ '{format_promptpay_display(pp_id)}' ใช้ไม่ได้ "
            "(ต้องเป็นเบอร์มือถือ 10 / บัตรประชาชน 13 / e-Wallet 15 หลัก)"
        )

    rows: list[tuple[str, int, float]] = []
    grand = 0.0
    for customer in data["customers"]:
        pdf_path, total = draw_receipt(customer, meta, pp_id, pp_type)
        rows.append((customer["name"], len(customer["contracts"]), total))
        grand += total
        print(f"[OK] {customer['id']} {customer['name']}: {total:,.2f} บาท -> {pdf_path.name}")
    summary_path = draw_summary(rows, grand, meta)
    print(f"[OK] summary -> {summary_path.name}")
    print(f"รวมยอดทั้งหมด: {grand:,.2f} บาท")


if __name__ == "__main__":
    main()
