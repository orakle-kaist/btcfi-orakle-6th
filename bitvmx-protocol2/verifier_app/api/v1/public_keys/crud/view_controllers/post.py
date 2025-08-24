from verifier_app.api.v1.public_keys.crud.view_models.post import (
    PublicKeysPostV1Input,
    PublicKeysPostV1Output,
)
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
import json


def _to_jsonable(obj):
    """Convert any object to JSON-serializable format"""
    if hasattr(obj, '__dict__'):
        return {k: _to_jsonable(v) for k, v in obj.__dict__.items()}
    elif hasattr(obj, 'model_dump'):
        return obj.model_dump()
    elif hasattr(obj, 'dict'):
        return obj.dict()
    elif isinstance(obj, (list, tuple)):
        return [_to_jsonable(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    elif isinstance(obj, bytes):
        return obj.hex()
    else:
        return obj


class PublicKeysPostViewControllerV1:
    def __init__(self, generate_public_keys_controller):
        self.generate_public_keys_controller = generate_public_keys_controller
        
    async def __call__(
        self, public_keys_post_input: PublicKeysPostV1Input
    ):
        # Get controller response - expecting tuple of (dto, public_key)
        bitvmx_verifier_winternitz_public_keys_dto, verifier_public_key = await self.generate_public_keys_controller(
            bitvmx_protocol_setup_properties_dto=public_keys_post_input.bitvmx_protocol_setup_properties_dto
        )
        
        # Build response payload - KEYS ONLY, NO TRANSACTIONS
        payload = {
            "setup_uuid": str(public_keys_post_input.bitvmx_protocol_setup_properties_dto.setup_uuid),
            "verifier_public_key": verifier_public_key,
            "bitvmx_verifier_winternitz_public_keys_dto": bitvmx_verifier_winternitz_public_keys_dto,
            # Optional fields can be None
            "verifier_payout_public_key": None,
            "verifier_destroyed_public_key": None,
            "verifier_destination_address": None,
        }
        
        # Use bulletproof JSON encoder
        return JSONResponse(
            content=jsonable_encoder(_to_jsonable(payload), exclude_none=True),
            status_code=200
        )