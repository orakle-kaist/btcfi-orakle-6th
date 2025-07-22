use std::sync::Arc;
use tokio::sync::Mutex;
use tracing::{info, error};
use warp::{Filter, Reply};

mod api;
mod models;
mod handlers;
mod storage;

use api::routes;
use storage::OptionStorage;

#[tokio::main]
async fn main() {
    // Initialize tracing
    tracing_subscriber::init();

    info!("🚀 Starting BTCFi Option Service API Server");

    // Initialize storage
    let storage = match OptionStorage::new("./data/options.db").await {
        Ok(storage) => {
            info!("✅ Database initialized successfully");
            Arc::new(Mutex::new(storage))
        },
        Err(e) => {
            error!("❌ Failed to initialize database: {}", e);
            std::process::exit(1);
        }
    };

    // Create routes
    let api_routes = routes(storage);
    
    // Add CORS headers
    let cors = warp::cors()
        .allow_any_origin()
        .allow_headers(vec!["content-type", "authorization"])
        .allow_methods(vec!["GET", "POST", "PUT", "DELETE", "OPTIONS"]);

    let routes = api_routes
        .with(cors)
        .with(warp::log("api"));

    info!("🌐 BTCFi Option API Server starting on http://0.0.0.0:8080");
    info!("📋 Available endpoints:");
    info!("   POST /api/v1/options/create    - Create new option product");
    info!("   POST /api/v1/options/buy       - Buy option product");
    info!("   GET  /api/v1/options/list      - List all active options");
    info!("   GET  /api/v1/options/{id}      - Get specific option details");
    info!("   GET  /api/v1/health            - Health check");

    // Start the server
    warp::serve(routes)
        .run(([0, 0, 0, 0], 8080))
        .await;
}