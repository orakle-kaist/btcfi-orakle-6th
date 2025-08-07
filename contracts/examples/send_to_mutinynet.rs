//! Example: Send a transaction to MutinyNet (Bitcoin Signet testnet)

use anyhow::Result;
use bitcoin::secp256k1::{Secp256k1, SecretKey};
use btcfi_contracts::testnet_transaction::{
    TestnetTransactionSender, TransactionInput, TransactionOutput,
};
use std::str::FromStr;

#[tokio::main]
async fn main() -> Result<()> {
    // Initialize for MutinyNet
    let sender = TestnetTransactionSender::mutinynet();
    
    // Example private key (DO NOT USE IN PRODUCTION)
    // In production, load from secure storage or use wallet
    let secp = Secp256k1::new();
    let privkey = SecretKey::from_str(
        "0000000000000000000000000000000000000000000000000000000000000001"
    )?;
    
    // Example UTXO from MutinyNet (replace with your actual UTXO)
    let input = TransactionInput {
        txid: "e7d1293bad708f6885231b796856a50c42b9b33dfa3b252119d4065a95e220fb".to_string(),
        vout: 0,
        value: 10000, // 0.0001 BTC in satoshis
        script_pubkey: "0014abcd1234567890abcdef1234567890abcdef1234".to_string(), // P2WPKH
    };
    
    // Destination address (replace with your address)
    let output = TransactionOutput {
        address: "tb1qw508d6qejxtdg4y5r3zarvary0c5xw7kxpjzsx".to_string(),
        value: 5000, // Send 0.00005 BTC
    };
    
    // Create and sign transaction
    println!("Creating transaction...");
    let mut tx = sender.create_transaction(
        vec![input.clone()],
        vec![output],
        1000, // 1000 satoshi fee
    )?;
    
    println!("Signing transaction...");
    sender.sign_transaction(&mut tx, &[input], &privkey)?;
    
    // Print transaction hex for verification
    let tx_hex = bitcoin::consensus::encode::serialize_hex(&tx);
    println!("Transaction hex: {}", tx_hex);
    println!("Transaction ID: {}", tx.txid());
    
    // Broadcast transaction
    println!("\nBroadcasting to MutinyNet...");
    match sender.broadcast_transaction(&tx).await {
        Ok(txid) => {
            println!("✅ Transaction broadcast successfully!");
            println!("Transaction ID: {}", txid);
            println!("View on explorer: https://mutinynet.com/tx/{}", txid);
        }
        Err(e) => {
            println!("❌ Failed to broadcast: {}", e);
            println!("You can manually broadcast the hex above at:");
            println!("https://mutinynet.com/broadcast");
        }
    }
    
    Ok(())
}