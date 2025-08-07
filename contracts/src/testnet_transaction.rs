//! Simple Rust implementation for sending transactions to Bitcoin testnet
//! Bypasses BitVMX verifier issues to demonstrate basic transaction capability

use anyhow::Result;
use bitcoin::{
    Transaction, TxIn, TxOut, OutPoint, Script, Witness,
    blockdata::opcodes::all::OP_RETURN,
    blockdata::script::Builder,
    consensus::encode::serialize_hex,
    hashes::Hash,
    secp256k1::{Secp256k1, SecretKey, PublicKey, Message},
    Address, Network, Txid,
    util::taproot::TaprootBuilder,
    absolute::LockTime,
    sighash::{SighashCache, TapSighashType},
};
use serde::{Deserialize, Serialize};
use std::str::FromStr;

/// Bitcoin testnet transaction sender
pub struct TestnetTransactionSender {
    network: Network,
    secp: Secp256k1<bitcoin::secp256k1::All>,
}

/// Transaction input data
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TransactionInput {
    pub txid: String,
    pub vout: u32,
    pub value: u64,  // satoshis
    pub script_pubkey: String,  // hex
}

/// Transaction output data
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TransactionOutput {
    pub address: String,
    pub value: u64,  // satoshis
}

impl TestnetTransactionSender {
    /// Create new testnet transaction sender
    pub fn new(network: Network) -> Self {
        Self {
            network,
            secp: Secp256k1::new(),
        }
    }

    /// Create for MutinyNet (Signet)
    pub fn mutinynet() -> Self {
        Self::new(Network::Signet)
    }

    /// Create for Bitcoin Testnet
    pub fn testnet() -> Self {
        Self::new(Network::Testnet)
    }

    /// Create a simple spending transaction
    pub fn create_transaction(
        &self,
        inputs: Vec<TransactionInput>,
        outputs: Vec<TransactionOutput>,
        fee: u64,
    ) -> Result<Transaction> {
        let mut tx_inputs = Vec::new();
        let mut total_input = 0u64;

        // Create transaction inputs
        for input in &inputs {
            let txid = Txid::from_str(&input.txid)?;
            tx_inputs.push(TxIn {
                previous_output: OutPoint {
                    txid,
                    vout: input.vout,
                },
                script_sig: Script::new(),
                sequence: bitcoin::Sequence::ENABLE_RBF_NO_LOCKTIME,
                witness: Witness::default(),
            });
            total_input += input.value;
        }

        let mut tx_outputs = Vec::new();
        let mut total_output = 0u64;

        // Create transaction outputs
        for output in &outputs {
            let address = Address::from_str(&output.address)?
                .require_network(self.network)?;
            tx_outputs.push(TxOut {
                value: output.value,
                script_pubkey: address.script_pubkey(),
            });
            total_output += output.value;
        }

        // Validate fee
        if total_input < total_output + fee {
            return Err(anyhow::anyhow!(
                "Insufficient input: {} < {} + {} fee",
                total_input,
                total_output,
                fee
            ));
        }

        // Add change output if needed
        let change = total_input - total_output - fee;
        if change > 546 {  // Dust limit
            // For now, send change back to first input address
            // In production, use a proper change address
            if let Ok(script) = Script::from_hex(&inputs[0].script_pubkey) {
                tx_outputs.push(TxOut {
                    value: change,
                    script_pubkey: script,
                });
            }
        }

        Ok(Transaction {
            version: 2,
            lock_time: LockTime::ZERO,
            input: tx_inputs,
            output: tx_outputs,
        })
    }

    /// Sign transaction with private key
    pub fn sign_transaction(
        &self,
        tx: &mut Transaction,
        inputs: &[TransactionInput],
        privkey: &SecretKey,
    ) -> Result<()> {
        let pubkey = PublicKey::from_secret_key(&self.secp, privkey);

        for (index, input) in inputs.iter().enumerate() {
            let script = Script::from_hex(&input.script_pubkey)?;
            
            // For P2WPKH or P2TR inputs
            if script.is_v0_p2wpkh() || script.is_v1_p2tr() {
                let mut sighash_cache = SighashCache::new(&*tx);
                
                // Create sighash
                let sighash = if script.is_v1_p2tr() {
                    // Taproot signature
                    let sighash = sighash_cache.taproot_key_spend_signature_hash(
                        index,
                        &bitcoin::sighash::Prevouts::All(&[TxOut {
                            value: input.value,
                            script_pubkey: script.clone(),
                        }]),
                        TapSighashType::Default,
                    )?;
                    sighash
                } else {
                    // P2WPKH signature
                    let sighash = sighash_cache.segwit_signature_hash(
                        index,
                        &script,
                        input.value,
                        bitcoin::EcdsaSighashType::All,
                    )?;
                    sighash
                };

                // Sign the sighash
                let msg = Message::from_slice(&sighash[..])?;
                let sig = self.secp.sign_ecdsa(&msg, privkey);

                // Create witness
                let mut witness = Witness::new();
                witness.push(sig.serialize_der());
                witness.push(&[0x01]); // SIGHASH_ALL
                witness.push(&pubkey.serialize());
                
                tx.input[index].witness = witness;
            }
        }

        Ok(())
    }

    /// Create and sign an OP_RETURN transaction for data anchoring
    pub fn create_op_return_transaction(
        &self,
        input: TransactionInput,
        data: &[u8],
        fee: u64,
        privkey: &SecretKey,
    ) -> Result<Transaction> {
        if data.len() > 80 {
            return Err(anyhow::anyhow!("OP_RETURN data too large: {} bytes", data.len()));
        }

        // Create OP_RETURN script
        let op_return_script = Builder::new()
            .push_opcode(OP_RETURN)
            .push_slice(data)
            .into_script();

        // Create transaction
        let mut tx = Transaction {
            version: 2,
            lock_time: LockTime::ZERO,
            input: vec![TxIn {
                previous_output: OutPoint {
                    txid: Txid::from_str(&input.txid)?,
                    vout: input.vout,
                },
                script_sig: Script::new(),
                sequence: bitcoin::Sequence::ENABLE_RBF_NO_LOCKTIME,
                witness: Witness::default(),
            }],
            output: vec![
                // OP_RETURN output
                TxOut {
                    value: 0,
                    script_pubkey: op_return_script,
                },
            ],
        };

        // Add change output
        let change = input.value - fee;
        if change > 546 {
            let script = Script::from_hex(&input.script_pubkey)?;
            tx.output.push(TxOut {
                value: change,
                script_pubkey: script,
            });
        }

        // Sign transaction
        self.sign_transaction(&mut tx, &[input], privkey)?;

        Ok(tx)
    }

    /// Broadcast transaction using external service or bitcoin-cli
    pub async fn broadcast_transaction(&self, tx: &Transaction) -> Result<String> {
        let hex = serialize_hex(tx);
        
        // For MutinyNet, use their API
        if self.network == Network::Signet {
            let client = reqwest::Client::new();
            let response = client
                .post("https://mutinynet.com/api/tx")
                .body(hex.clone())
                .send()
                .await?;

            if response.status().is_success() {
                let txid = response.text().await?;
                return Ok(txid.trim().to_string());
            } else {
                let error = response.text().await?;
                return Err(anyhow::anyhow!("Broadcast failed: {}", error));
            }
        }

        // For testnet, use bitcoin-cli or other service
        let output = std::process::Command::new("bitcoin-cli")
            .args(&[
                "-testnet",
                "sendrawtransaction",
                &hex,
            ])
            .output()?;

        if output.status.success() {
            let txid = String::from_utf8(output.stdout)?.trim().to_string();
            Ok(txid)
        } else {
            let error = String::from_utf8_lossy(&output.stderr);
            Err(anyhow::anyhow!("Broadcast failed: {}", error))
        }
    }
}

/// Example usage functions
impl TestnetTransactionSender {
    /// Send a simple payment transaction
    pub async fn send_payment(
        &self,
        from_txid: &str,
        from_vout: u32,
        from_value: u64,
        from_script: &str,
        to_address: &str,
        amount: u64,
        fee: u64,
        privkey: &SecretKey,
    ) -> Result<String> {
        let input = TransactionInput {
            txid: from_txid.to_string(),
            vout: from_vout,
            value: from_value,
            script_pubkey: from_script.to_string(),
        };

        let output = TransactionOutput {
            address: to_address.to_string(),
            value: amount,
        };

        let mut tx = self.create_transaction(vec![input.clone()], vec![output], fee)?;
        self.sign_transaction(&mut tx, &[input], privkey)?;
        
        let txid = self.broadcast_transaction(&tx).await?;
        Ok(txid)
    }

    /// Anchor data on-chain using OP_RETURN
    pub async fn anchor_data(
        &self,
        from_txid: &str,
        from_vout: u32,
        from_value: u64,
        from_script: &str,
        data: &[u8],
        fee: u64,
        privkey: &SecretKey,
    ) -> Result<String> {
        let input = TransactionInput {
            txid: from_txid.to_string(),
            vout: from_vout,
            value: from_value,
            script_pubkey: from_script.to_string(),
        };

        let tx = self.create_op_return_transaction(input, data, fee, privkey)?;
        let txid = self.broadcast_transaction(&tx).await?;
        Ok(txid)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use bitcoin::secp256k1::rand::thread_rng;

    #[test]
    fn test_create_transaction() {
        let sender = TestnetTransactionSender::mutinynet();
        
        let input = TransactionInput {
            txid: "e7d1293bad708f6885231b796856a50c42b9b33dfa3b252119d4065a95e220fb".to_string(),
            vout: 0,
            value: 10000,
            script_pubkey: "0014abcd1234".to_string(),
        };

        let output = TransactionOutput {
            address: "tb1qw508d6qejxtdg4y5r3zarvary0c5xw7kxpjzsx".to_string(),
            value: 5000,
        };

        let tx = sender.create_transaction(vec![input], vec![output], 1000).unwrap();
        
        assert_eq!(tx.input.len(), 1);
        assert_eq!(tx.output.len(), 2); // Output + change
        assert_eq!(tx.output[0].value, 5000);
        assert_eq!(tx.output[1].value, 4000); // Change = 10000 - 5000 - 1000
    }

    #[test]
    fn test_op_return_transaction() {
        let sender = TestnetTransactionSender::mutinynet();
        let secp = Secp256k1::new();
        let privkey = SecretKey::new(&mut thread_rng());
        
        let input = TransactionInput {
            txid: "e7d1293bad708f6885231b796856a50c42b9b33dfa3b252119d4065a95e220fb".to_string(),
            vout: 0,
            value: 10000,
            script_pubkey: "0014abcd1234".to_string(),
        };

        let data = b"BTCFI:OPTION:CALL:50000:1735689600";
        
        let tx = sender.create_op_return_transaction(
            input,
            data,
            1000,
            &privkey,
        ).unwrap();
        
        assert_eq!(tx.output[0].value, 0); // OP_RETURN has 0 value
        assert_eq!(tx.output[1].value, 9000); // Change
    }
}