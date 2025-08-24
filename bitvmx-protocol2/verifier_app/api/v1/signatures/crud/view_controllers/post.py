from verifier_app.api.v1.signatures.crud.view_models.post import (
    SignaturesPostV1Input,
    SignaturesPostV1Output,
)
from bitvmx_protocol_library.transaction_generation.entities.dtos.bitvmx_prover_signatures_dto import (
    BitVMXProverSignaturesDTO,
)


class SignaturesPostViewControllerV1:
    def __init__(self, generate_signatures_controller):
        self.generate_signatures_controller = generate_signatures_controller
        
    async def __call__(self, signatures_post_input: SignaturesPostV1Input) -> SignaturesPostV1Output:
        # Convert dict to DTO with pydantic v1/v2 compatibility
        data = signatures_post_input.prover_signatures_dto
        try:
            # Try pydantic v2 first
            prover_signatures_dto = BitVMXProverSignaturesDTO.model_validate(data)
        except AttributeError:
            # Fallback to pydantic v1
            prover_signatures_dto = BitVMXProverSignaturesDTO.parse_obj(data)
        
        verifier_signatures_dto = self.generate_signatures_controller(
            setup_uuid=signatures_post_input.setup_uuid,
            bitvmx_prover_signatures_dto=prover_signatures_dto
        )
        
        return SignaturesPostV1Output(
            verifier_signatures_dto=verifier_signatures_dto
        )