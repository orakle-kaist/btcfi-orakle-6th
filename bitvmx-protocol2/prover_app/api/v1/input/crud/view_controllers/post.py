from prover_app.api.v1.input.crud.view_models.post import InputPostV1Input, InputPostV1Output

class InputPostViewControllerV1:
    async def __call__(self, input_post_view_input: InputPostV1Input) -> InputPostV1Output:
        return InputPostV1Output(execution_trace_id="test-trace-id", message="Input processed")