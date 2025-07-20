//! Bitcoin L1 Committer for Option Transaction Anchoring
//! 
//! This service commits option transactions to Bitcoin L1 using OP_RETURN.
//! Follows the business requirement for L1 anchoring of all option lifecycle events.

use std::time::Duration;
use tokio::time::sleep;
use tracing::{info, error};

mod committer;
mod config;

use committer::BitcoinCommitter;
use config::CommitterConfig;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Initialize tracing
    tracing_subscriber::fmt::init();
    
    info!("🔗 Starting Bitcoin L1 Committer Service");
    
    // Load configuration
    let config = CommitterConfig::load()?;
    info!("📋 Loaded configuration: {}", config.bitcoin_network);
    
    // Initialize Bitcoin committer
    let mut committer = BitcoinCommitter::new(config).await?;
    info!("🚀 Bitcoin committer initialized successfully");
    
    // Start main service loop
    loop {
        match committer.process_pending_transactions().await {
            Ok(committed_count) => {
                if committed_count > 0 {
                    info!("✅ Committed {} transactions to Bitcoin L1", committed_count);
                }
            }
            Err(e) => {
                error!("❌ Error processing transactions: {}", e);
            }
        }
        
        // Wait before next processing cycle
        sleep(Duration::from_secs(30)).await;
    }
}