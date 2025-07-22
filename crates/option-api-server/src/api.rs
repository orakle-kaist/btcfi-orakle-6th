use warp::{Filter, filters::BoxedFilter, Reply};
use std::sync::Arc;
use tokio::sync::Mutex;

use crate::handlers::*;
use crate::models::*;
use crate::storage::OptionStorage;

pub fn routes(
    storage: Arc<Mutex<OptionStorage>>,
) -> BoxedFilter<(impl Reply,)> {
    let storage = warp::any().map(move || storage.clone());

    // Health check endpoint
    let health = warp::path!("api" / "v1" / "health")
        .and(warp::get())
        .and(storage.clone())
        .and_then(health_handler);

    // Create option endpoint
    let create_option = warp::path!("api" / "v1" / "options" / "create")
        .and(warp::post())
        .and(warp::body::json())
        .and(storage.clone())
        .and_then(create_option_handler);

    // Buy option endpoint
    let buy_option = warp::path!("api" / "v1" / "options" / "buy")
        .and(warp::post())
        .and(warp::body::json())
        .and(storage.clone())
        .and_then(buy_option_handler);

    // List all active options
    let list_options = warp::path!("api" / "v1" / "options" / "list")
        .and(warp::get())
        .and(storage.clone())
        .and_then(list_options_handler);

    // Get specific option details
    let get_option = warp::path!("api" / "v1" / "options")
        .and(warp::path::param::<String>())
        .and(warp::get())
        .and(storage.clone())
        .and_then(get_option_handler);

    health
        .or(create_option)
        .or(buy_option)
        .or(list_options)
        .or(get_option)
        .boxed()
}