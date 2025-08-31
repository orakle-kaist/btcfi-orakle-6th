# Note: Global FD redirect disabled - it blocks uvicorn logs
# Instead, we'll use targeted suppression in specific functions
import os
import sys

from bitcoinutils.setup import setup
from bitcoinutils.keys import PublicKey

# 안전 몽키패치 (idempotent)
if not getattr(PublicKey, "_safe_patch_applied", False):
    _orig_to_hex = PublicKey.to_hex
    def _to_hex_safe(self, compressed=True, *args, **kwargs):
        # bitcoinutils는 compressed 인자를 넘기므로 반드시 받는다
        v = _orig_to_hex(self, compressed, *args, **kwargs)
        # 일부 버전은 이미 str, 일부는 bytes일 수 있으니 통일
        return v if isinstance(v, str) else v.hex()

    # x-only 추출 헬퍼: 압축 키(33바이트, 0x02/0x03 프리픽스)에서 x만 떼기
    def _to_x_only_hex_safe(self):
        h = _to_hex_safe(self, True)
        # 33바이트(hex 66)면 프리픽스(02/03) 제거 → 32바이트
        if len(h) == 66 and (h.startswith("02") or h.startswith("03")):
            return h[2:]
        # 이미 32바이트 형태라면 그대로 사용
        return h[-64:]

    PublicKey.to_hex = _to_hex_safe
    # bitcoinutils 버전에 따라 to_x_only_hex 없을 수 있으니 그냥 덮어씀
    PublicKey.to_x_only_hex = _to_x_only_hex_safe

    PublicKey._safe_patch_applied = True
    print("[GLOBAL PATCH] PublicKey.to_hex/to_x_only_hex safely patched (sig-compatible)")

from fastapi import FastAPI

from bitvmx_protocol_library.config import common_protocol_properties
from bitvmx_protocol_library.enums import BitcoinNetwork
from prover_app.api.router import router as prover_router

if common_protocol_properties.network == BitcoinNetwork.MUTINYNET:
    setup("testnet")
else:
    setup(common_protocol_properties.network.value)

app = FastAPI(
    title="Prover service",
    description="Microservice to perform all the operations related to the prover",
)


@app.get("/healthcheck")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(prover_router, prefix="/api")  # , tags=["Prover API"])
