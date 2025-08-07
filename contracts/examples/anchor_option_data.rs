//! Example: Anchor option data on-chain using OP_RETURN

use anyhow::Result;
use bitcoin::secp256k1::{Secp256k1, SecretKey};
use btcfi_contracts::testnet_transaction::{TestnetTransactionSender, TransactionInput};
use std::str::FromStr;

#[tokio::main]
async fn main() -> Result<()> {
    // Initialize for MutinyNet
    let sender = TestnetTransactionSender::mutinynet();
    
    // Example private key (DO NOT USE IN PRODUCTION)
    let secp = Secp256k1::new();
    let privkey = SecretKey::from_str(
        "0000000000000000000000000000000000000000000000000000000000000001"
    )?;
    
    // Example UTXO from MutinyNet
    let input = TransactionInput {
        txid: "e7d1293bad708f6885231b796856a50c42b9b33dfa3b252119d4065a95e220fb".to_string(),
        vout: 0,
        value: 10000, // 0.0001 BTC
        script_pubkey: "0014abcd1234567890abcdef1234567890abcdef1234".to_string(),
    };
    
    // Create option registration data
    // Format: "BTCFI:OPTION:{TYPE}:{STRIKE}:{EXPIRY}"
    let option_data = format!(
        "BTCFI:OPTION:CALL:{}:{}",
        50000,       // Strike price: $50,000
        1735689600   // Expiry: 2025-01-01 00:00:00 UTC
    );
    
    println!("Option data to anchor: {}", option_data);
    println!("Data size: {} bytes", option_data.len());
    
    // Create OP_RETURN transaction
    println!("\nCreating OP_RETURN transaction...");
    let tx = sender.create_op_return_transaction(
        input,
        option_data.as_bytes(),
        1000, // 1000 satoshi fee
        &privkey,
    )?;
    
    // Print transaction details
    let tx_hex = bitcoin::consensus::encode::serialize_hex(&tx);
    println!("Transaction hex: {}", tx_hex);
    println!("Transaction ID: {}", tx.txid());
    
    // Show OP_RETURN output
    for (i, output) in tx.output.iter().enumerate() {
        if output.value == 0 {
            println!("\nOP_RETURN output #{}: {:?}", i, output.script_pubkey);
        }
    }
    
    // Broadcast transaction
    println!("\nBroadcasting to MutinyNet...");
    match sender.broadcast_transaction(&tx).await {
        Ok(txid) => {
            println!("✅ Option data anchored successfully!");
            println!("Transaction ID: {}", txid);
            println!("View on explorer: https://mutinynet.com/tx/{}", txid);
            println!("\nThe option data is now permanently recorded on Bitcoin!");
        }
        Err(e) => {
            println!("❌ Failed to broadcast: {}", e);
            println!("\nYou can manually broadcast at: https://mutinynet.com/broadcast");
        }
    }
    
    Ok(())
}