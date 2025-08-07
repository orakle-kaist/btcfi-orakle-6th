use bitcoin::blockdata::opcodes::all::*;
use bitcoin::blockdata::script::{Builder, ScriptBuf};
use bitcoin::taproot::{TaprootBuilder, TaprootSpendInfo};
use bitcoin::secp256k1::{Secp256k1};
use bitcoin::XOnlyPublicKey;
use anyhow::Result;
use oracle_vm_common::types::OptionType;

/// Bitcoin L1 단방향 옵션 컨트랙트
/// BitVMX를 사용하여 오프체인 계산과 온체인 검증을 결합
pub struct BitcoinOption {
    /// 옵션 타입 (Call/Put)
    pub option_type: OptionType,
    /// 행사가 (satoshis)
    pub strike_price: u64,
    /// 만기 블록 높이
    pub expiry_block: u32,
    /// 구매자 공개키
    pub buyer_pubkey: bitcoin::secp256k1::PublicKey,
    /// 판매자 공개키  
    pub seller_pubkey: bitcoin::secp256k1::PublicKey,
    /// BitVMX 검증자 공개키
    pub verifier_pubkey: bitcoin::secp256k1::PublicKey,
    /// 프리미엄 (satoshis)
    pub premium: u64,
    /// 담보 금액 (satoshis)
    pub collateral: u64,
}


impl BitcoinOption {
    /// 옵션 컨트랙트의 Taproot 스크립트 생성
    pub fn create_taproot_script(&self) -> Result<(ScriptBuf, TaprootSpendInfo)> {
        let secp = Secp256k1::new();
        
        // 1. Key-path spending: 정상적인 협력 정산
        let internal_key = self.create_musig_internal_key()?;
        
        // 2. Script-path spending: BitVMX 증명 기반 정산
        let settlement_script = self.create_settlement_script();
        let refund_script = self.create_refund_script();
        
        // Taproot tree 구성
        let taproot_builder = TaprootBuilder::new()
            .add_leaf(1, settlement_script.clone())?
            .add_leaf(1, refund_script.clone())?;
            
        let internal_xonly = XOnlyPublicKey::from(internal_key);
        let taproot_spend_info = taproot_builder.finalize(&secp, internal_xonly)
            .map_err(|_| anyhow::anyhow!("Failed to finalize taproot"))?;
        
        // Taproot output script
        let taproot_output = Builder::new()
            .push_opcode(OP_PUSHNUM_1)
            .push_slice(&internal_xonly.serialize())
            .into_script();
        
        Ok((taproot_output, taproot_spend_info))
    }
    
    /// MuSig 내부 키 생성 (구매자 + 판매자 협력)
    fn create_musig_internal_key(&self) -> Result<bitcoin::secp256k1::PublicKey> {
        // 실제 구현에서는 MuSig2 프로토콜 사용
        // 여기서는 단순화를 위해 구매자 키 반환
        Ok(self.buyer_pubkey)
    }
    
    /// 정산 스크립트: BitVMX 증명 검증 후 자동 정산
    fn create_settlement_script(&self) -> ScriptBuf {
        Builder::new()
            // 만기 시간 체크
            .push_int(self.expiry_block as i64)
            .push_opcode(OP_CLTV)
            .push_opcode(OP_DROP)
            
            // BitVMX 증명 검증
            // 증명 포맷: [option_type || strike || spot || settlement_amount]
            .push_opcode(OP_DUP)
            .push_opcode(OP_SHA256)
            
            // 예상 증명 해시와 비교 (실제로는 동적으로 계산)
            .push_slice(&[0u8; 32]) // placeholder for proof hash
            .push_opcode(OP_EQUAL)
            .push_opcode(OP_VERIFY)
            
            // 검증자 서명 확인
            .push_slice(&self.verifier_pubkey.serialize())
            .push_opcode(OP_CHECKSIGVERIFY)
            
            // 정산 금액에 따라 수령인 결정
            // 스택: [settlement_amount]
            .push_int(0)
            .push_opcode(OP_GREATERTHAN)
            .push_opcode(OP_IF)
                // ITM: 구매자가 수령
                .push_slice(&self.buyer_pubkey.serialize())
            .push_opcode(OP_ELSE)
                // OTM: 판매자가 담보 회수
                .push_slice(&self.seller_pubkey.serialize())
            .push_opcode(OP_ENDIF)
            .push_opcode(OP_CHECKSIG)
            .into_script()
    }
    
    /// 환불 스크립트: 만기 후 일정 시간 지나면 판매자가 회수
    fn create_refund_script(&self) -> ScriptBuf {
        Builder::new()
            // 만기 + 1일 후
            .push_int((self.expiry_block + 144) as i64)
            .push_opcode(OP_CLTV)
            .push_opcode(OP_DROP)
            
            // 판매자 서명
            .push_slice(&self.seller_pubkey.serialize())
            .push_opcode(OP_CHECKSIG)
            .into_script()
    }
    
    /// 옵션 구매 트랜잭션 생성
    pub fn create_purchase_transaction(&self) -> Result<bitcoin::Transaction> {
        // TODO: 실제 트랜잭션 구성
        // 1. 구매자가 프리미엄 지불
        // 2. 판매자가 담보 잠금
        // 3. Taproot 출력 생성
        
        unimplemented!("Purchase transaction creation")
    }
    
    /// BitVMX 증명 데이터 구조
    pub fn create_settlement_proof(
        &self,
        spot_price: u64,
        oracle_signatures: Vec<Vec<u8>>,
    ) -> Result<Vec<u8>> {
        let mut proof_data = Vec::new();
        
        // 옵션 타입
        proof_data.push(match self.option_type {
            OptionType::Call => 0,
            OptionType::Put => 1,
        });
        
        // 가격 데이터 (little-endian)
        proof_data.extend_from_slice(&self.strike_price.to_le_bytes());
        proof_data.extend_from_slice(&spot_price.to_le_bytes());
        
        // 정산 금액 계산
        let settlement_amount = self.calculate_settlement(spot_price);
        proof_data.extend_from_slice(&settlement_amount.to_le_bytes());
        
        // Oracle 서명들 추가
        for sig in oracle_signatures {
            proof_data.extend_from_slice(&sig);
        }
        
        Ok(proof_data)
    }
    
    /// 정산 금액 계산
    fn calculate_settlement(&self, spot_price: u64) -> u64 {
        match self.option_type {
            OptionType::Call => {
                if spot_price > self.strike_price {
                    // ITM: (spot - strike) * contract_size
                    // 여기서는 담보 전액 반환으로 단순화
                    self.collateral
                } else {
                    0
                }
            }
            OptionType::Put => {
                if spot_price < self.strike_price {
                    // ITM: (strike - spot) * contract_size  
                    self.collateral
                } else {
                    0
                }
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use bitcoin::secp256k1::{SecretKey, PublicKey, rand::thread_rng};
    
    #[test]
    fn test_create_option_script() {
        let secp = Secp256k1::new();
        let mut rng = thread_rng();
        
        let buyer_key = SecretKey::new(&mut rng);
        let seller_key = SecretKey::new(&mut rng);
        let verifier_key = SecretKey::new(&mut rng);
        
        let option = BitcoinOption {
            option_type: OptionType::Call,
            strike_price: 50_000_000, // 0.5 BTC
            expiry_block: 800_000,
            buyer_pubkey: PublicKey::from_secret_key(&secp, &buyer_key),
            seller_pubkey: PublicKey::from_secret_key(&secp, &seller_key),
            verifier_pubkey: PublicKey::from_secret_key(&secp, &verifier_key),
            premium: 1_000_000, // 0.01 BTC
            collateral: 10_000_000, // 0.1 BTC
        };
        
        let (script, _spend_info) = option.create_taproot_script().unwrap();
        assert!(script.is_p2tr());
    }
    
    #[test]
    fn test_settlement_calculation() {
        let secp = Secp256k1::new();
        let mut rng = thread_rng();
        
        let option = BitcoinOption {
            option_type: OptionType::Call,
            strike_price: 50_000_000,
            expiry_block: 800_000,
            buyer_pubkey: PublicKey::from_secret_key(&secp, &SecretKey::new(&mut rng)),
            seller_pubkey: PublicKey::from_secret_key(&secp, &SecretKey::new(&mut rng)),
            verifier_pubkey: PublicKey::from_secret_key(&secp, &SecretKey::new(&mut rng)),
            premium: 1_000_000,
            collateral: 10_000_000,
        };
        
        // Call ITM
        assert_eq!(option.calculate_settlement(60_000_000), 10_000_000);
        
        // Call OTM
        assert_eq!(option.calculate_settlement(40_000_000), 0);
    }
}