from prover_app.api.v1.fund.crud.view_models.post import FundPostV1Input, FundPostV1Output

class FundPostViewControllerV1:
    async def __call__(self, fund_post_view_input: FundPostV1Input) -> FundPostV1Output:
        return FundPostV1Output(success=True, message="Funding setup created")