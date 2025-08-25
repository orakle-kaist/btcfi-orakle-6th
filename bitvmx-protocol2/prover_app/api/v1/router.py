from typing import Annotated

from fastapi import APIRouter, Body

from prover_app.api.v1.fund.crud.v1.view_models.post import FundPostV1Input, FundPostV1Output
from prover_app.api.v1.input.crud.v1.view_models.post import InputPostV1Input, InputPostV1Output
from prover_app.api.v1.next_step.crud.view_models.post import NextStepPostV1Input, NextStepPostV1Output
from prover_app.api.v1.setup.crud.v1.swagger_examples.post import (
    setup_post_v1_input_swagger_examples,
)
from prover_app.api.v1.setup.crud.v1.view_models.post import SetupPostV1Input
from prover_app.api.v1.setup.fund.v1.swagger_examples.post import (
    setup_fund_post_v1_input_swagger_examples,
)
from prover_app.api.v1.setup.fund.v1.view_models.post import SetupFundPostV1Input
from prover_app.dependency_injection.api.v1.fund import FundPostViewControllers
from prover_app.dependency_injection.api.v1.input import InputPostViewControllers
from prover_app.dependency_injection.api.v1.next_step import NextStepPostViewControllers
from prover_app.dependency_injection.api.v1.setup import SetupPostViewControllers
from prover_app.dependency_injection.api.v1.setup_fund import SetupFundPostViewControllers

router = APIRouter()

# If this becomes too big, we should create a router inside each folder, overengineering as of now


@router.post("/setup")
async def setup_post(
    setup_post_input: Annotated[
        SetupPostV1Input, Body(openapi_examples=setup_post_v1_input_swagger_examples)
    ]
):
    view_controller = SetupPostViewControllers.v1()
    return await view_controller(setup_post_view_input=setup_post_input)


@router.post("/setup/fund")
async def setup_fund_post(
    setup_fund_post_input: Annotated[
        SetupFundPostV1Input, Body(openapi_examples=setup_fund_post_v1_input_swagger_examples)
    ]
):
    view_controller = SetupFundPostViewControllers.v1()
    return await view_controller(setup_post_view_input=setup_fund_post_input)


@router.post("/next_step")
async def next_step_post(next_step_post_input: NextStepPostV1Input = Body()):
    # Import broadcast service
    from prover_app.domain.services.broadcast_protocol_service import broadcast_protocol_transactions
    
    # Get the same persistence and broadcast service used by setup controller
    # Import from the same dependency injection used by setup
    from prover_app.dependency_injection.domain.create_setup import CreateSetupControllers
    
    # Get controller instance to access services
    setup_controller = CreateSetupControllers.bitvmx_protocol()
    
    try:
        # Broadcast protocol transactions
        result = broadcast_protocol_transactions(
            setup_uuid=next_step_post_input.setup_uuid,
            persistence=setup_controller.bitvmx_protocol_setup_properties_dto_persistence,
            broadcast_service=setup_controller.broadcast_transaction_service,
        )
        
        # Return success with broadcast results
        return NextStepPostV1Output(
            message=f"Broadcasted {result['broadcasted_count']} tx(s), skipped {result['skipped_count']}, failed {result['failed_count']} for {result['setup_uuid']}",
            next_step="await_confirmations" if result['broadcasted_count'] > 0 else "check_failed_transactions"
        )
        
    except ValueError as e:
        # Setup not found or no transactions
        return NextStepPostV1Output(
            message=str(e),
            next_step="error"
        )
    except Exception as e:
        # Other errors
        return NextStepPostV1Output(
            message=f"Error broadcasting transactions: {str(e)}",
            next_step="error"
        )


@router.post("/fund")
async def fund_post(fund_post_input: FundPostV1Input = Body()) -> FundPostV1Output:
    view_controller = FundPostViewControllers.v1()
    return await view_controller(fund_post_view_input=fund_post_input)


@router.post("/input")
async def input_post(input_input: InputPostV1Input = Body()) -> InputPostV1Output:
    view_controller = InputPostViewControllers.v1()
    return await view_controller(input_post_view_input=input_input)
