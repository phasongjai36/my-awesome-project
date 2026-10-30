"""ทดสอบตัวสร้าง QR payload ของ PromptPay (EMVCo) — ไม่ต้องใช้ dependency นอกจาก stdlib

หมายเหตุ: เลขพร้อมเพย์ที่ใช้ทดสอบเป็นตัวเลขสมมติ (9999999999999) ไม่ใช่เลขจริงของร้าน
"""

import pytest

from config import load_env_file, resolve_promptpay
from promptpay import (
    build_promptpay,
    classify_promptpay_id,
    crc16_ccitt,
    format_promptpay_display,
    format_target,
    tlv,
    verify_promptpay,
)

FAKE_CITIZEN_ID = "9999999999999"
FAKE_MOBILE = "0899999999"


def test_tlv_encodes_tag_length_value():
    assert tlv("01", "12") == "010212"
    assert tlv("59", "NICHE BLOOMS") == "5912NICHE BLOOMS"


def test_crc16_ccitt_known_vector():
    # CRC-16/CCITT-FALSE (init 0xFFFF, poly 0x1021) ของ "123456789" = 0x29B1
    # EMVCo QR กำหนดให้ใช้ CRC-16/CCITT-FALSE (ไม่ใช่ XMODEM ที่ init 0x0000)
    assert crc16_ccitt(b"123456789") == 0x29B1


@pytest.mark.parametrize(
    "pp_id,expected",
    [
        (FAKE_MOBILE, "mobile"),
        (FAKE_CITIZEN_ID, "citizen"),
        ("999999999999999", "wallet"),
        ("12345", None),
        ("", None),
    ],
)
def test_classify_promptpay_id(pp_id, expected):
    assert classify_promptpay_id(pp_id) == expected


def test_format_target_phone_strips_leading_zero():
    assert format_target(FAKE_MOBILE, "phone") == "0066899999999"


def test_format_target_phone_handles_country_code():
    assert format_target("66899999999", "phone") == "0066899999999"


def test_format_target_citizen_keeps_digits():
    assert format_target(FAKE_CITIZEN_ID, "citizen") == FAKE_CITIZEN_ID


def test_format_promptpay_display():
    assert format_promptpay_display(FAKE_MOBILE) == "089-999-9999"
    assert format_promptpay_display(FAKE_CITIZEN_ID) == FAKE_CITIZEN_ID


def test_build_promptpay_structure():
    payload = build_promptpay(
        1234.50, FAKE_CITIZEN_ID, "citizen", "NICHE BLOOMS", "BANGKOK"
    )
    assert payload.startswith("000201")
    assert payload[-8:-4] == "6304"
    assert "5802TH" in payload
    assert "5303764" in payload
    assert "5912NICHE BLOOMS" in payload
    assert verify_promptpay(payload)


def test_build_promptpay_embeds_amount():
    payload = build_promptpay(9484.0, FAKE_CITIZEN_ID, "citizen")
    assert "54079484.00" in payload


def test_build_promptpay_uses_sub_tag_01_for_phone():
    payload = build_promptpay(100.0, FAKE_MOBILE, "phone")
    # sub-tag 01 = เบอร์มือถือ, ความยาว 13 หลัก (0066 + เลข 9 หลัก)
    assert "01130066899999999" in payload
    assert verify_promptpay(payload)


def test_build_promptpay_uses_sub_tag_02_for_citizen():
    payload = build_promptpay(100.0, FAKE_CITIZEN_ID, "citizen")
    # sub-tag 02 = บัตรประชาชน 13 หลัก
    assert "0213" + FAKE_CITIZEN_ID in payload
    assert verify_promptpay(payload)


def test_build_promptpay_includes_reference():
    payload = build_promptpay(100.0, FAKE_CITIZEN_ID, "citizen", ref="INV-cus-1")
    assert "6213" in payload
    assert "INV-cus-1" in payload


def test_verify_promptpay_rejects_tampered_payload():
    payload = build_promptpay(100.0, FAKE_CITIZEN_ID, "citizen")
    tampered = payload[:-1] + ("0" if payload[-1] != "0" else "1")
    assert not verify_promptpay(tampered)


def test_verify_promptpay_rejects_garbage():
    assert not verify_promptpay("not-a-payload")
    assert not verify_promptpay("")


# ---------- การอ่านค่าตั้งจาก .env / environment ----------


def test_load_env_file_parses_quotes_and_comments(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        '# comment line\nPROMPTPAY_ID="0899999999"\n\nPROMPTPAY_ID_TYPE=phone\nBROKEN\n',
        encoding="utf-8",
    )
    values = load_env_file(env_file)
    assert values["PROMPTPAY_ID"] == "0899999999"
    assert values["PROMPTPAY_ID_TYPE"] == "phone"
    assert "BROKEN" not in values


def test_missing_env_file_returns_empty(tmp_path):
    assert load_env_file(tmp_path / "nope.env") == {}


def test_environment_variable_wins_over_env_file(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "PROMPTPAY_ID=0899999999\nPROMPTPAY_ID_TYPE=phone\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PROMPTPAY_ID", FAKE_CITIZEN_ID)
    monkeypatch.setenv("PROMPTPAY_ID_TYPE", "citizen")

    pp_id, pp_type = resolve_promptpay({}, env_path=env_file)
    assert pp_id == FAKE_CITIZEN_ID
    assert pp_type == "citizen"


def test_env_file_used_when_environment_is_empty(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "PROMPTPAY_ID=0899999999\nPROMPTPAY_ID_TYPE=phone\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("PROMPTPAY_ID", raising=False)
    monkeypatch.delenv("PROMPTPAY_ID_TYPE", raising=False)

    pp_id, pp_type = resolve_promptpay({}, env_path=env_file)
    assert pp_id == "0899999999"
    assert pp_type == "phone"


def test_metadata_is_the_last_resort(monkeypatch, tmp_path):
    monkeypatch.delenv("PROMPTPAY_ID", raising=False)
    monkeypatch.delenv("PROMPTPAY_ID_TYPE", raising=False)

    meta = {"promptpay_id": FAKE_CITIZEN_ID, "promptpay_id_type": "citizen"}
    pp_id, pp_type = resolve_promptpay(meta, env_path=tmp_path / "nope.env")
    assert pp_id == FAKE_CITIZEN_ID
    assert pp_type == "citizen"
