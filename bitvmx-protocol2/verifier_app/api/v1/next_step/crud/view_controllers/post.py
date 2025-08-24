from verifier_app.api.v1.next_step.crud.view_models.post import (
    NextStepPostV1Input,
    NextStepPostV1Output,
)


class NextStepPostViewControllerV1:
    def __init__(self, next_step_controller):
        self.next_step_controller = next_step_controller
        
    async def __call__(self, next_step_post_input: NextStepPostV1Input) -> NextStepPostV1Output:
        return await self.next_step_controller(setup_uuid=next_step_post_input.setup_id)