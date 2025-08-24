from prover_app.api.v1.setup.fund.view_models.post import SetupFundPostV1Input, SetupFundPostV1Output

class SetupFundPostViewControllerV1:
    async def __call__(self, setup_fund_post_view_input: SetupFundPostV1Input) -> SetupFundPostV1Output:
        return SetupFundPostV1Output(message="Setup funding completed")