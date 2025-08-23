import secrets
import requests

from bitcoinutils.keys import PrivateKey

from prover_app.api.v1.setup.crud.v1.view_models.post import SetupPostV1Input, SetupPostV1Output


class SetupPostViewControllerV1:
    def __init__(
        self,
        create_setup_controller,
        protocol_properties,
        common_protocol_properties,
    ):
        self.create_setup_controller = create_setup_controller
        self.protocol_properties = protocol_properties
        self.common_protocol_properties = common_protocol_properties

    async def __call__(self, setup_post_view_input: SetupPostV1Input) -> SetupPostV1Output:
        if setup_post_view_input.verifier_list is None:
            verifier_list = self.protocol_properties.verifier_list
        else:
            verifier_list = setup_post_view_input.verifier_list
        if self.protocol_properties.prover_private_key is None:
            controlled_prover_private_key = PrivateKey(b=secrets.token_bytes(32))
        else:
            controlled_prover_private_key = PrivateKey(
                b=bytes.fromhex(self.protocol_properties.prover_private_key)
            )

        origin_of_funds_private_key = PrivateKey(
            b=bytes.fromhex(setup_post_view_input.secret_origin_of_funds)
        )
        
        
        # 자동으로 최신 UTXO 가져오기
        funding_tx_id = setup_post_view_input.funding_tx_id
        funding_index = setup_post_view_input.funding_index
        
        # 사용할 금액 설정 (기본값: 100,000 sats = 0.001 BTC)
        # 전체 잔액을 사용하지 않고 일부만 사용
        funding_amount = getattr(setup_post_view_input, 'funding_amount', 100000)
        
        if funding_tx_id == "auto" or funding_tx_id == "latest":
            # MutinyNet에서 최신 UTXO 자동으로 가져오기
            address = setup_post_view_input.prover_destination_address
            try:
                response = requests.get(f"https://mutinynet.com/api/address/{address}/utxo")
                if response.status_code == 200:
                    utxos = response.json()
                    if utxos and len(utxos) > 0:
                        # 가장 큰 UTXO 선택
                        largest_utxo = max(utxos, key=lambda x: x['value'])
                        funding_tx_id = largest_utxo['txid']
                        funding_index = largest_utxo['vout']
                        available_amount = largest_utxo['value']
                        
                        # 사용 가능한 금액 확인
                        if available_amount < funding_amount + 10000:  # 수수료 여유분 10,000 sats
                            print(f"경고: UTXO 잔액 부족 ({available_amount} sats), 더 적은 금액 사용")
                            funding_amount = min(funding_amount, available_amount - 10000)
                        
                        print(f"자동 UTXO 선택: {funding_tx_id}:{funding_index}")
                        print(f"  사용 가능: {available_amount} sats")
                        print(f"  사용 예정: {funding_amount} sats")
                        print(f"  잔액 유지: {available_amount - funding_amount} sats")
                    else:
                        raise Exception(f"No UTXOs found for address {address}")
            except Exception as e:
                print(f"UTXO 자동 가져오기 실패: {e}")
                # 기본값 사용
                pass

        setup_uuid = await self.create_setup_controller(
            max_amount_of_steps=setup_post_view_input.max_amount_of_steps,
            amount_of_input_words=setup_post_view_input.amount_of_input_words,
            amount_of_bits_wrong_step_search=setup_post_view_input.amount_of_bits_wrong_step_search,
            amount_of_bits_per_digit_checksum=setup_post_view_input.amount_of_bits_per_digit_checksum,
            verifier_list=verifier_list,
            controlled_prover_private_key=controlled_prover_private_key,
            funding_tx_id=funding_tx_id,
            funding_index=funding_index,
            step_fees_satoshis=self.common_protocol_properties.step_fees_satoshis,
            origin_of_funds_private_key=origin_of_funds_private_key,
            prover_destination_address=setup_post_view_input.prover_destination_address,
            prover_signature_private_key=setup_post_view_input.prover_signature_private_key,
            prover_signature_public_key=setup_post_view_input.prover_signature_public_key,
        )
        return SetupPostV1Output(setup_uuid=setup_uuid)
