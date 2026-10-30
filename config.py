"""
การตั้งค่าของระบบ — โมดูลนี้ใช้แค่ standard library เท่านั้น
เพื่อให้ทดสอบได้โดยไม่ต้องติดตั้ง qrcode/reportlab/Pillow

ลำดับการหาค่าเลขพร้อมเพย์:
  1. environment variable  (PROMPTPAY_ID / PROMPTPAY_ID_TYPE / PROMPTPAY_ACCOUNT_NAME)
  2. ไฟล์ .env
  3. billing_data.json -> metadata.promptpay_id
"""

import os
from pathlib import Path

BASE = Path(__file__).parent


def load_env_file(path: Path | None = None) -> dict[str, str]:
    """อ่านไฟล์ .env แบบเบาๆ ไม่ต้องพึ่ง package เพิ่ม (ไม่ต้องมี python-dotenv)"""
    env_path = Path(path) if path else (BASE / ".env")
    if not env_path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def resolve_promptpay(meta: dict, env_path: Path | None = None) -> tuple[str, str]:
    """คืนค่า (เลขพร้อมเพย์, ประเภท) — เช่น ("0812345678", "phone")"""
    env_file = load_env_file(env_path)
    pp_id = (
        os.environ.get("PROMPTPAY_ID")
        or env_file.get("PROMPTPAY_ID")
        or str(meta.get("promptpay_id") or "")
    )
    pp_type = (
        os.environ.get("PROMPTPAY_ID_TYPE")
        or env_file.get("PROMPTPAY_ID_TYPE")
        or str(meta.get("promptpay_id_type") or "citizen")
    )
    return pp_id, pp_type


def resolve_account_name(meta: dict, env_path: Path | None = None) -> str:
    """ชื่อผู้ถือบัญชีที่แสดงใต้ QR (ถ้าไม่ตั้งจะใช้ชื่อร้าน)"""
    env_file = load_env_file(env_path)
    return (
        os.environ.get("PROMPTPAY_ACCOUNT_NAME")
        or env_file.get("PROMPTPAY_ACCOUNT_NAME")
        or str(
            meta.get("promptpay_account_name") or meta.get("merchant_name") or "PAYMENT"
        )
    )
