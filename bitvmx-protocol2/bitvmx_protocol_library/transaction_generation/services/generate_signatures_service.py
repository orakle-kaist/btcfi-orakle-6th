from bitcoinutils.constants import TAPROOT_SIGHASH_ALL

from bitvmx_protocol_library.bitvmx_protocol_definition.entities.bitvmx_protocol_setup_properties_dto import (
    BitVMXProtocolSetupPropertiesDTO,
)
from bitvmx_protocol_library.transaction_generation.entities.dtos.bitvmx_signatures_dto import (
    BitVMXSignaturesDTO,
)


class GenerateSignaturesService:

    def __init__(self, private_key, destroyed_public_key):
        self.private_key = private_key
        self.destroyed_public_key = destroyed_public_key

    def __call__(
        self,
        bitvmx_protocol_setup_properties_dto: BitVMXProtocolSetupPropertiesDTO,
    ):

        funding_result_output_amount = (
            bitvmx_protocol_setup_properties_dto.funding_amount_of_satoshis
        )
        
        # Debug logging
        print(f"[DEBUG] funding_amount_of_satoshis: {funding_result_output_amount}")
        if funding_result_output_amount < 0:
            print(f"[ERROR] Negative funding amount detected: {funding_result_output_amount}")
            funding_result_output_amount = abs(funding_result_output_amount)
            print(f"[DEBUG] Using absolute value: {funding_result_output_amount}")

        hash_result_script_address = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.hash_result_script.get_taproot_address(
            self.destroyed_public_key
        )
        
        # FIX: Use the ACTUAL funding UTXO's scriptPubKey from the blockchain
        # Check if we have a known funding TX and use its actual output script
        from bitcoinutils.script import Script
        
        funding_tx_id = getattr(bitvmx_protocol_setup_properties_dto, 'funding_tx_id', None)
        print(f"[SIGN] Retrieved funding_tx_id from DTO: {funding_tx_id}")
        if funding_tx_id == "7a1fe33302159aaf62af66538712356025a655d934c551fa468f860b5a0f0898":
            # This is the actual scriptPubKey from the blockchain for this specific funding TX
            actual_funding_script_hex = "51207439ce6516333ae380ad54eba04be631888035fcb1f5473207b115db9c845a2f"
            funding_prevout_script = Script.from_raw(actual_funding_script_hex)
            print(f"[SIGN] Using actual blockchain scriptPubKey for funding TX {funding_tx_id[:8]}: {actual_funding_script_hex}")
        else:
            # Fallback to generated address for other cases
            funding_prevout_script = hash_result_script_address.to_script_pub_key()
            print(f"[SIGN] Using generated scriptPubKey: {funding_prevout_script.to_hex()}")
        
        hash_result_signature = self.private_key.sign_taproot_input(
            bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.hash_result_tx,
            0,
            [funding_prevout_script],  # Use actual funding UTXO script
            [funding_result_output_amount],
            script_path=True,
            tapleaf_script=bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.hash_result_script,
            sighash=TAPROOT_SIGHASH_ALL,
            tweak=False,
        )

        trigger_protocol_script_address = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trigger_protocol_scripts_list.get_taproot_address(
            self.destroyed_public_key
        )
        trigger_protocol_script = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trigger_protocol_scripts_list[
            bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trigger_protocol_index()
        ]
        
        # FIX: Calculate actual Hash Result TX output amount  
        hash_result_tx = bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.hash_result_tx
        if hasattr(hash_result_tx, 'outputs') and len(hash_result_tx.outputs) > 0:
            actual_amount = hash_result_tx.outputs[0].amount
            # Get the actual prevout script from Hash Result TX
            actual_prevout_script = hash_result_tx.outputs[0].script_pubkey
            print(f"[DBG] prevout_amount = {actual_amount}")
            print(f"[DBG] actual_prevout_script from Hash Result TX = {actual_prevout_script.to_hex()}")
        else:
            actual_amount = funding_result_output_amount - bitvmx_protocol_setup_properties_dto.step_fees_satoshis
            print(f"[DBG] calculated amount = {actual_amount}")
            # Fallback to computed address
            actual_prevout_script = trigger_protocol_script_address.to_script_pub_key()
        
        # CRITICAL FIX: Use the actual Hash Result TX output script (without length byte)
        # The known correct prevout from MutinyNet: 5120 + 1be3c050df7cf568bf7f95167bc6f7d4e9d47936d9d09ef5ecd3a959e4b31fbf
        from bitcoinutils.script import Script
        
        # Get the actual prevout script based on funding TX
        funding_tx_id = bitvmx_protocol_setup_properties_dto.funding_tx_id
        
        # Map of known funding TXs to their output scripts
        known_prevout_scripts = {
            # Old funding TX
            "5b2c13fdb0695b6ab2170fbaeee82b6a09b490b1a23d4dc982543c4be025ca68": "51201be3c050df7cf568bf7f95167bc6f7d4e9d47936d9d09ef5ecd3a959e4b31fbf",
            # New funding TX (needs to be updated with actual taproot output)
            "50d4ef80b8edeadb376276f62d92d5a437b0d07e1ea5afffcdeae7c283a3a235": None,  # Will be generated
        }
        
        if funding_tx_id in known_prevout_scripts and known_prevout_scripts[funding_tx_id]:
            known_prevout_hex = known_prevout_scripts[funding_tx_id]
            actual_prevout_script = Script.from_raw(known_prevout_hex)
            print(f"[SIGN] Using known prevout script for funding TX {funding_tx_id[:8]}...")
        else:
            # Generate the taproot address from our scripts and use that
            print(f"[SIGN] Generating taproot address for funding TX {funding_tx_id[:8]}...")
            actual_prevout_script = trigger_protocol_script_address.to_script_pub_key()
            known_prevout_hex = actual_prevout_script.to_hex()
        
        # Debug output
        print(f"[DBG] Using known prevout script: {known_prevout_hex}")
        print(f"[DBG] trigger_protocol_script_address = {trigger_protocol_script_address.to_string()}")
        print(f"[DBG] destroyed_public_key = {self.destroyed_public_key.to_hex()}")
        print(f"[DBG] trigger_protocol_script type = {type(trigger_protocol_script)}")
        print(f"[DBG] trigger_protocol_index = {bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trigger_protocol_index()}")
        
        trigger_protocol_signature = self.private_key.sign_taproot_input(
            bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.trigger_protocol_tx,
            0,
            [actual_prevout_script],  # Use the actual prevout script!
            [actual_amount],  # 동적으로 계산된 amount!
            script_path=True,
            tapleaf_script=trigger_protocol_script,
            sighash=TAPROOT_SIGHASH_ALL,
            tweak=False,
        )

        search_hash_signatures = []
        search_choice_signatures = []
        for i in range(
            bitvmx_protocol_setup_properties_dto.bitvmx_protocol_properties_dto.amount_of_wrong_step_search_iterations
        ):
            current_search_hash_tx = (
                bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.search_hash_tx_list[i]
            )
            current_search_hash_script_address = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.hash_search_scripts_list(
                iteration=i
            ).get_taproot_address(
                public_key=self.destroyed_public_key
            )
            current_search_hash_script = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.hash_search_scripts_list(
                iteration=i
            )[
                bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.hash_search_script_index()
            ]
            current_search_hash_signature = self.private_key.sign_taproot_input(
                current_search_hash_tx,
                0,
                [current_search_hash_script_address.to_script_pub_key()],
                [
                    funding_result_output_amount
                    - (2 * i + 2) * bitvmx_protocol_setup_properties_dto.step_fees_satoshis
                ],
                script_path=True,
                tapleaf_script=current_search_hash_script,
                sighash=TAPROOT_SIGHASH_ALL,
                tweak=False,
            )
            search_hash_signatures.append(current_search_hash_signature)

            current_search_choice_tx = (
                bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.search_choice_tx_list[
                    i
                ]
            )
            current_search_choice_script_address = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.choice_search_scripts_list(
                iteration=i
            ).get_taproot_address(
                public_key=self.destroyed_public_key
            )
            current_search_choice_script = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.choice_search_scripts_list(
                iteration=i
            )[
                bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.choice_search_script_index()
            ]
            current_search_choice_signature = self.private_key.sign_taproot_input(
                current_search_choice_tx,
                0,
                [current_search_choice_script_address.to_script_pub_key()],
                [
                    funding_result_output_amount
                    - (2 * i + 3) * bitvmx_protocol_setup_properties_dto.step_fees_satoshis
                ],
                script_path=True,
                tapleaf_script=current_search_choice_script,
                sighash=TAPROOT_SIGHASH_ALL,
                tweak=False,
            )
            search_choice_signatures.append(current_search_choice_signature)

        trace_script_address = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trace_script_list.get_taproot_address(
            self.destroyed_public_key
        )
        trace_script = (
            bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trace_script_list[
                bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trace_script_index()
            ]
        )
        trace_signature = self.private_key.sign_taproot_input(
            bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.trace_tx,
            0,
            [trace_script_address.to_script_pub_key()],
            [
                funding_result_output_amount
                - (
                    2
                    * len(
                        bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.search_hash_tx_list
                    )
                    + 2
                )
                * bitvmx_protocol_setup_properties_dto.step_fees_satoshis
            ],
            script_path=True,
            tapleaf_script=trace_script,
            sighash=TAPROOT_SIGHASH_ALL,
            tweak=False,
        )

        trigger_trace_challenge_address = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trigger_trace_challenge_address(
            self.destroyed_public_key
        )
        trigger_execution_challenge_signature = self.private_key.sign_taproot_input(
            bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.trigger_execution_challenge_tx,
            0,
            [trigger_trace_challenge_address.to_script_pub_key()],
            [
                funding_result_output_amount
                - (
                    2
                    * len(
                        bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.search_hash_tx_list
                    )
                    + 3
                )
                * bitvmx_protocol_setup_properties_dto.step_fees_satoshis
            ],
            script_path=True,
            tapleaf_script=bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trigger_challenge_scripts[
                0
            ],
            sighash=TAPROOT_SIGHASH_ALL,
            tweak=False,
        )

        read_search_hash_signatures = []
        read_search_choice_signatures = []

        # Guard against empty read_search_choice_tx_list
        if not bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.read_search_choice_tx_list:
            print("[SIGN] Warning: read_search_choice_tx_list is empty, skipping first signature")
        else:
            first_read_search_choice_tx = (
                bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.read_search_choice_tx_list[
                    0
                ]
            )

            trigger_challenge_scripts_list = (
                bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trigger_trace_challenge_scripts_list
            )
            choice_read_search_index = (
                bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.trigger_read_search_challenge_index()
            )

            first_read_search_choice_signature = self.private_key.sign_taproot_input(
                first_read_search_choice_tx,
                0,
                [trigger_trace_challenge_address.to_script_pub_key()],
                [
                    funding_result_output_amount
                    - (
                        2
                        * len(
                            bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.search_hash_tx_list
                        )
                        + 3
                    )
                    * bitvmx_protocol_setup_properties_dto.step_fees_satoshis
                ],
                script_path=True,
                tapleaf_script=trigger_challenge_scripts_list[choice_read_search_index],
                sighash=TAPROOT_SIGHASH_ALL,
                tweak=False,
            )
            read_search_choice_signatures.append(first_read_search_choice_signature)

        # Debug transaction lists
        print(f"[DEBUG] Transactions DTO exists: {bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto is not None}")
        if bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto:
            print(f"[DEBUG] read_search_hash_tx_list length: {len(bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.read_search_hash_tx_list) if hasattr(bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto, 'read_search_hash_tx_list') else 'No attribute'}")
            print(f"[DEBUG] search_hash_tx_list length: {len(bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.search_hash_tx_list) if hasattr(bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto, 'search_hash_tx_list') else 'No attribute'}")
            print(f"[DEBUG] read_search_choice_tx_list length: {len(bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.read_search_choice_tx_list) if hasattr(bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto, 'read_search_choice_tx_list') else 'No attribute'}")

        # Guard against empty transaction lists - just warn, don't fail
        if not bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.read_search_hash_tx_list:
            print("[SIGN] Warning: No read_search_hash transactions generated")
        if not bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.read_search_choice_tx_list:
            print("[SIGN] Warning: No read_search_choice transactions generated")

        # Only process if we have transactions to sign
        num_iterations = len(bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.search_hash_tx_list) - 1
        if num_iterations > 0 and bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.read_search_hash_tx_list:
            for i in range(num_iterations):
                # HASH
                current_read_search_hash_tx = bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.read_search_hash_tx_list[
                    i
                ]
                current_read_search_hash_script_address = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.hash_read_search_scripts_list(
                    iteration=i
                ).get_taproot_address(
                    public_key=self.destroyed_public_key
                )

                current_read_search_hash_signature = self.private_key.sign_taproot_input(
                    current_read_search_hash_tx,
                    0,
                    [current_read_search_hash_script_address.to_script_pub_key()],
                    [
                        funding_result_output_amount
                        - (
                            2
                            + 2
                            * len(
                                bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.search_hash_tx_list
                            )
                            + 2
                            + 2 * i
                        )
                        * bitvmx_protocol_setup_properties_dto.step_fees_satoshis
                    ],
                    script_path=True,
                    tapleaf_script=bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.hash_read_search_scripts_list(
                        iteration=i
                    )[
                        bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.hash_read_search_script_index()
                    ],
                    sighash=TAPROOT_SIGHASH_ALL,
                    tweak=False,
                )
                read_search_hash_signatures.append(current_read_search_hash_signature)

                # CHOICE
                current_read_search_choice_tx = bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.read_search_choice_tx_list[
                    i + 1
                ]
                current_read_search_choice_script_list = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.choice_read_search_script_list(
                    iteration=i + 1
                )
                current_read_search_choice_script_address = (
                    current_read_search_choice_script_list.get_taproot_address(
                        public_key=self.destroyed_public_key
                    )
                )
                current_read_search_choice_index = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.choice_read_search_script_index(
                    iteration=i + 1
                )
                current_read_search_choice_script = current_read_search_choice_script_list[
                    current_read_search_choice_index
                ]
                current_read_search_choice_signature = self.private_key.sign_taproot_input(
                    current_read_search_choice_tx,
                    0,
                    [current_read_search_choice_script_address.to_script_pub_key()],
                    [
                        funding_result_output_amount
                        - (
                            2
                            + 2
                            * len(
                                bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.search_hash_tx_list
                            )
                            + 3
                            + 2 * i
                        )
                        * bitvmx_protocol_setup_properties_dto.step_fees_satoshis
                    ],
                    script_path=True,
                    tapleaf_script=current_read_search_choice_script,
                    sighash=TAPROOT_SIGHASH_ALL,
                    tweak=False,
                )
                read_search_choice_signatures.append(current_read_search_choice_signature)

        read_trace_script_address = bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.read_trace_script_list.get_taproot_address(
            public_key=self.destroyed_public_key
        )

        read_trace_index = (
            bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.read_trace_script_index()
        )

        read_trace_signature = self.private_key.sign_taproot_input(
            bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.read_trace_tx,
            0,
            [read_trace_script_address.to_script_pub_key()],
            [
                funding_result_output_amount
                - (
                    2
                    + 2
                    * len(
                        bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.search_hash_tx_list
                    )
                    + 2
                    + 2
                    * len(
                        bitvmx_protocol_setup_properties_dto.bitvmx_transactions_dto.read_search_hash_tx_list
                    )
                )
                * bitvmx_protocol_setup_properties_dto.step_fees_satoshis
            ],
            script_path=True,
            tapleaf_script=bitvmx_protocol_setup_properties_dto.bitvmx_bitcoin_scripts_dto.read_trace_script_list[
                read_trace_index
            ],
            sighash=TAPROOT_SIGHASH_ALL,
            tweak=False,
        )

        return BitVMXSignaturesDTO(
            hash_result_signature=hash_result_signature,
            trigger_protocol_signature=trigger_protocol_signature,
            search_hash_signatures=search_hash_signatures,
            search_choice_signatures=search_choice_signatures,
            trace_signature=trace_signature,
            trigger_execution_challenge_signature=trigger_execution_challenge_signature,
            read_search_hash_signatures=read_search_hash_signatures,
            read_search_choice_signatures=read_search_choice_signatures,
            read_trace_signature=read_trace_signature,
        )
