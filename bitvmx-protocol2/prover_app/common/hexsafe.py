# prover_app/common/hexsafe.py
import re

_HEX_RE = re.compile(r'[0-9a-fA-F]+')

def hex_from_any(v) -> str:
    """어떤 입력이 와도 ASCII hex string으로 반환(소문자, 공백/0x 제거). 실패시 빈 문자열."""
    if v is None:
        return ''
    if isinstance(v, (bytes, bytearray, memoryview)):
        return bytes(v).hex()
    if isinstance(v, str):
        s = v.strip()
        if s.startswith('0x') or s.startswith('0X'):
            s = s[2:]
        s = ''.join(_HEX_RE.findall(s)).lower()
        return s
    if hasattr(v, 'to_hex'):
        return hex_from_any(v.to_hex())
    if hasattr(v, 'hex'):
        return hex_from_any(v.hex())
    try:
        return hex_from_any(bytes(v))
    except Exception:
        return ''.join(_HEX_RE.findall(str(v))).lower()

def bfromhex_safe(v) -> bytes:
    """bytes.fromhex 래퍼: bytes면 그대로, str/obj면 hex 추출 후 변환. 실패시 b''."""
    if v is None:
        return b''
    if isinstance(v, (bytes, bytearray, memoryview)):
        return bytes(v)
    s = hex_from_any(v)
    try:
        return bytes.fromhex(s) if s else b''
    except Exception:
        return b''

def ensure_hex_str(v) -> str:
    """브로드캐스트 경계용: 무조건 str(hex)로."""
    s = hex_from_any(v)
    return s or ''