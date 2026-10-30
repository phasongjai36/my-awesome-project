"""
PromptPay QR payload builder (EMVCo Merchant Presented Mode, per the BOT PromptPay standard).

Pure standard library on purpose — no qrcode/reportlab/PIL imports — so this module
can be unit-tested anywhere and reused by other backends (the TypeScript app in
NICHEBLOOMS_Smart_Bill_Hub implements the same algorithm in server/lib/promptpay.ts).

Targets accepted by Thai banking apps:
  - mobile   10 digits, leading 0
  - citizen  13 digits (national ID)
  - wallet   15 digits (e-wallet)
"""

from __future__ import annotations

# PromptPay Merchant Account Information AID — required so bank apps recognise the QR.
AID_PROMPTPAY = "A000000677010111"

# EMVCo country code for Thailand.
COUNTRY_TH = "TH"

# Currency code 764 = Thai Baht.
CURRENCY_THB = "764"


def tlv(tag: str, value: str) -> str:
    """Encode a tag-length-value field (length is bytes, not characters)."""
    return f"{tag}{len(value):02d}{value}"


def crc16_ccitt(data: bytes) -> int:
    """CRC-16/CCITT-FALSE (XMODEM): init 0xFFFF, poly 0x1021, no reflection."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def classify_promptpay_id(pp_id: str) -> str | None:
    """Return 'mobile' | 'citizen' | 'wallet' | None for a PromptPay ID."""
    digits = "".join(c for c in str(pp_id) if c.isdigit())
    if len(digits) == 10 and digits.startswith("0"):
        return "mobile"
    if len(digits) == 13:
        return "citizen"
    if len(digits) == 15:
        return "wallet"
    return None


def format_promptpay_display(pp_id: str) -> str:
    """Human-readable form: 081-234-5678 for mobile, other lengths unchanged."""
    digits = "".join(c for c in str(pp_id) if c.isdigit())
    if len(digits) == 10 and digits.startswith("0"):
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    return str(pp_id)


def format_target(pp_id: str, id_type: str = "citizen") -> str:
    """Normalise the PromptPay target as required by the BOT spec."""
    digits = "".join(c for c in str(pp_id) if c.isdigit())
    if id_type == "phone":
        if digits.startswith("0"):
            return "0066" + digits[1:]
        if digits.startswith("66"):
            return "00" + digits
        return digits
    return digits


def build_promptpay(
    amount: float,
    pp_id: str,
    id_type: str = "citizen",
    merchant_name: str = "PAYMENT",
    merchant_city: str = "BANGKOK",
    ref: str = "",
) -> str:
    """
    Build a complete EMVCo QR payload with a PromptPay target and an embedded amount.

    The amount is embedded so the payer never has to key it in — the amount in the QR
    always matches the receipt.
    """
    target = format_target(pp_id, id_type)
    if id_type == "phone":
        # Sub-tag 01 = mobile number (no leading zero, prefixed per BOT spec).
        sub = tlv("01", target)
    else:
        # Sub-tag 02 = citizen ID / tax ID (13 digits).
        sub = tlv("02", target)

    f29 = tlv("29", tlv("00", AID_PROMPTPAY) + sub)
    f54 = tlv("54", f"{amount:.2f}")
    f62 = tlv("62", tlv("01", ref[:25])) if ref else ""

    payload = (
        tlv("00", "01")
        + tlv("01", "12")
        + f29
        + tlv("52", "0000")
        + tlv("53", CURRENCY_THB)
        + f54
        + tlv("58", COUNTRY_TH)
        + tlv("59", merchant_name[:25])
        + tlv("60", merchant_city[:15])
        + f62
    )

    body = payload + "6304"
    return body + f"{crc16_ccitt(body.encode('ascii')):04X}"


def verify_promptpay(payload: str) -> bool:
    """Check the EMVCo CRC trailer of a payload. Useful in tests and for sanity checks."""
    if len(payload) < 8 or payload[-8:-4] != "6304":
        return False
    body, crc_hex = payload[:-4], payload[-4:]
    try:
        expected = int(crc_hex, 16)
    except ValueError:
        return False
    return crc16_ccitt(body.encode("ascii")) == expected
