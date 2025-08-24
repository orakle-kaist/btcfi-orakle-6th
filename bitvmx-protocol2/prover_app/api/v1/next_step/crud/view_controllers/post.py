from prover_app.api.v1.next_step.crud.view_models.post import NextStepPostV1Input, NextStepPostV1Output

class NextStepPostViewControllerV1:
    async def __call__(self, next_step_post_view_input: NextStepPostV1Input) -> NextStepPostV1Output:
        return NextStepPostV1Output(message="Next step ready", next_step="execute")