from prover_app.api.v1.next_step.crud.view_models.post import NextStepPostV1Input, NextStepPostV1Output

class NextStepPostViewControllerV1:
    def __init__(self, publish_next_step_controller):
        self.publish_next_step_controller = publish_next_step_controller
    
    async def __call__(self, next_step_post_view_input: NextStepPostV1Input) -> NextStepPostV1Output:
        # Call the actual BitVMX next step controller with force_resign parameter
        result = await self.publish_next_step_controller(
            setup_uuid=next_step_post_view_input.setup_uuid,
            force_resign=next_step_post_view_input.force_resign
        )
        
        return NextStepPostV1Output(
            message=f"Next step executed for setup {next_step_post_view_input.setup_uuid}",
            next_step=str(result) if result else "completed"
        )