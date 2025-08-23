"""
Improved Setup Controller with Auto-funding
Separates concerns and uses services properly
"""
from typing import Optional, Dict
from prover_app.domain.services.mutinynet_utxo_service import MutinynetUTXOService

class CreateSetupWithAutoFundingController:
    """
    Controller that orchestrates setup creation with automatic funding
    """
    
    def __init__(
        self,
        utxo_service: MutinynetUTXOService,
        verifier_communication_service,
        setup_creation_service,
        persistence_service
    ):
        self.utxo_service = utxo_service
        self.verifier_communication_service = verifier_communication_service
        self.setup_creation_service = setup_creation_service
        self.persistence_service = persistence_service
    
    async def __call__(
        self,
        setup_params: Dict,
        auto_fund: bool = True
    ) -> str:
        """
        Create setup with automatic funding from Mutinynet
        
        Args:
            setup_params: Setup configuration
            auto_fund: Whether to automatically find funding UTXO
            
        Returns:
            Setup UUID
        """
        # Step 1: Auto-fetch funding if requested
        if auto_fund and setup_params.get('funding_tx_id') == '0' * 64:
            funding_info = self.utxo_service.get_funding_tx_info(
                setup_params['prover_destination_address']
            )
            
            if funding_info:
                setup_params['funding_tx_id'] = funding_info['funding_tx_id']
                setup_params['funding_index'] = funding_info['funding_index']
                print(f"✅ Auto-funding: Using UTXO {funding_info['funding_tx_id'][:8]}... with {funding_info['funding_value']} sats")
            else:
                print("⚠️ No suitable UTXO found, proceeding with dummy funding")
        
        # Step 2: Get verifier public keys (delegated to service)
        verifier_keys = await self.verifier_communication_service.get_public_keys(
            setup_params
        )
        
        # Step 3: Create setup (delegated to service)
        setup_uuid = await self.setup_creation_service.create(
            setup_params,
            verifier_keys
        )
        
        # Step 4: Persist setup (delegated to service)
        await self.persistence_service.save_setup(setup_uuid, setup_params)
        
        return setup_uuid