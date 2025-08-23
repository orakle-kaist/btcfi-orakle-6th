from typing import Annotated, Dict, Any
import uuid
import asyncio
import json
import os
import traceback
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
import tempfile

from fastapi import APIRouter, Body, HTTPException, BackgroundTasks

from prover_app.api.v1.fund.crud.view_models.post import FundPostV1Input, FundPostV1Output
from prover_app.api.v1.input.crud.view_models.post import InputPostV1Input, InputPostV1Output
from prover_app.api.v1.next_step.crud.view_models.post import NextStepPostV1Input
from prover_app.api.v1.setup.crud.swagger_examples.post import (
    setup_post_v1_input_swagger_examples,
)
from prover_app.api.v1.setup.crud.view_models.post import SetupPostV1Input
from prover_app.api.v1.setup.fund.swagger_examples.post import (
    setup_fund_post_v1_input_swagger_examples,
)
from prover_app.api.v1.setup.fund.view_models.post import SetupFundPostV1Input
from prover_app.dependency_injection.api.v1.fund import FundPostViewControllers
from prover_app.dependency_injection.api.v1.input import InputPostViewControllers
from prover_app.dependency_injection.api.v1.next_step import NextStepPostViewControllers
from prover_app.dependency_injection.api.v1.setup import SetupPostViewControllers
from prover_app.dependency_injection.api.v1.setup_fund import SetupFundPostViewControllers

router = APIRouter()

# 옵션 라우터 추가
from prover_app.api.v1.option.router import router as option_router
router.include_router(option_router)

# If this becomes too big, we should create a router inside each folder, overengineering as of now

# Store for background tasks (in production, use Redis or database)
setup_tasks: Dict[str, Dict[str, Any]] = {}

# Create ProcessPoolExecutor for CPU-intensive tasks
executor = ProcessPoolExecutor(max_workers=4)

# Task status directory (shared between processes)
TASK_STATUS_DIR = tempfile.gettempdir()


def run_setup_in_separate_process(setup_input_dict: dict, task_id: str):
    """Run CPU-intensive setup logic in completely separate process with robust logging"""
    import asyncio
    import json
    import os
    import logging
    import traceback
    from datetime import datetime
    from time import time
    
    # Configure logging for this process
    log_file_path = f"/tmp/prover_task_{task_id}.log"
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file_path),
            logging.StreamHandler()  # Also output to console
        ],
        force=True  # Override any existing configuration
    )
    logger = logging.getLogger(f"Task-{task_id}")
    
    # Status file path for inter-process communication
    status_file = os.path.join(TASK_STATUS_DIR, f"task_{task_id}.json")
    
    def update_status(status_data):
        """Update task status in JSON file"""
        try:
            with open(status_file, 'w') as f:
                json.dump(status_data, f)
            logger.info(f"Updated status file: {status_data.get('status')}")
        except Exception as e:
            logger.error(f"Failed to update status file: {e}")
    
    start_time = time()
    logger.info(f"=== Task {task_id} STARTED ===")
    logger.info(f"Log file: {log_file_path}")
    logger.info(f"Status file: {status_file}")
    
    try:
        update_status({
            "status": "running",
            "started_at": datetime.now().isoformat(),
            "task_id": task_id,
            "log_file": log_file_path
        })
        
        # ============= CRITICAL: Initialize Bitcoin network for child process =============
        logger.info("Initializing Bitcoin network settings for child process...")
        from bitcoinutils.setup import setup as bitcoin_setup
        from dotenv import load_dotenv
        
        # Load environment variables
        load_dotenv('.env_common')
        network = os.getenv('NETWORK', 'mutinynet')
        
        # Map mutinynet to testnet for bitcoinutils (mutinynet is a signet variant)
        if network == 'mutinynet':
            bitcoin_network = 'testnet'
        else:
            bitcoin_network = network
            
        logger.info(f"Setting bitcoinutils network to: {bitcoin_network} (from NETWORK={network})")
        bitcoin_setup(bitcoin_network)
        logger.info("Bitcoin network initialized successfully")
        # ==================================================================================
        
        # Import required modules
        logger.info("Importing modules...")
        from prover_app.api.v1.setup.crud.view_models.post import SetupPostV1Input
        from prover_app.dependency_injection.api.v1.setup import SetupPostViewControllers
        
        # Reconstruct the setup input from dict
        logger.info("Reconstructing setup input...")
        setup_input = SetupPostV1Input(**setup_input_dict)
        logger.info(f"Setup input created: max_amount_of_steps={setup_input.max_amount_of_steps}")
        
        # Create new event loop for this process
        logger.info("Creating new event loop...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Run the CPU-intensive setup logic
        logger.info("Initializing view controller...")
        view_controller = SetupPostViewControllers.v1()
        
        logger.info("Starting setup logic execution...")
        setup_start = time()
        result = loop.run_until_complete(view_controller(setup_post_view_input=setup_input))
        setup_duration = time() - setup_start
        logger.info(f"Setup logic completed in {setup_duration:.2f}s")
        
        # Update task status with result
        update_status({
            "status": "completed",
            "result": result if isinstance(result, (dict, list, str, int, float, bool, type(None))) else str(result),
            "completed_at": datetime.now().isoformat(),
            "duration": setup_duration,
            "task_id": task_id,
            "log_file": log_file_path
        })
        
        logger.info(f"=== Task {task_id} COMPLETED SUCCESSFULLY in {time() - start_time:.2f}s ===")
        loop.close()
        return result
        
    except Exception as e:
        error_msg = str(e)
        error_details = traceback.format_exc()
        
        logger.error(f"!!! Task {task_id} FAILED !!!")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error message: {error_msg}")
        logger.error(f"Full traceback:\n{error_details}")
        
        # Save detailed error information
        update_status({
            "status": "failed",
            "error": error_msg,
            "error_type": type(e).__name__,
            "traceback": error_details,
            "failed_at": datetime.now().isoformat(),
            "duration": time() - start_time,
            "task_id": task_id,
            "log_file": log_file_path
        })
        
        logger.info(f"=== Task {task_id} FAILED after {time() - start_time:.2f}s ===")
        raise


async def run_setup_with_executor(setup_input: SetupPostV1Input, task_id: str):
    """Wrapper to run setup in ProcessPoolExecutor"""
    loop = asyncio.get_event_loop()
    
    # Convert SetupPostV1Input to dict for serialization
    setup_input_dict = setup_input.dict()
    
    # Initialize task status
    setup_tasks[task_id] = {
        "status": "pending",
        "created_at": datetime.now().isoformat()
    }
    
    try:
        # Run in separate process
        await loop.run_in_executor(
            executor,
            run_setup_in_separate_process,
            setup_input_dict,
            task_id
        )
    except Exception as e:
        print(f"[EXECUTOR] Error running task {task_id}: {str(e)}")


@router.post("/setup")
async def setup_post(
    setup_post_input: Annotated[
        SetupPostV1Input, Body(openapi_examples=setup_post_v1_input_swagger_examples)
    ],
    background_tasks: BackgroundTasks
):
    """Start setup process in separate process and return task ID immediately"""
    task_id = str(uuid.uuid4())
    
    # Add task to background using ProcessPoolExecutor
    background_tasks.add_task(run_setup_with_executor, setup_post_input, task_id)
    
    # Return task ID immediately
    return {
        "message": "Setup process started in background",
        "task_id": task_id,
        "status_url": f"/api/v1/setup/status/{task_id}"
    }


@router.get("/setup/status/{task_id}")
async def get_setup_status(task_id: str):
    """Check the status of a background setup task"""
    # First check in-memory status
    task = setup_tasks.get(task_id)
    
    # If not in memory, check JSON file from process
    if not task or task.get("status") == "pending":
        status_file = os.path.join(TASK_STATUS_DIR, f"task_{task_id}.json")
        if os.path.exists(status_file):
            try:
                with open(status_file, 'r') as f:
                    task = json.load(f)
            except Exception as e:
                print(f"Error reading status file: {e}")
    
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    return task


@router.post("/setup/sync")
async def setup_post_sync(
    setup_post_input: Annotated[
        SetupPostV1Input, Body(openapi_examples=setup_post_v1_input_swagger_examples)
    ]
):
    """Original synchronous setup endpoint (for backward compatibility)"""
    view_controller = SetupPostViewControllers.v1()
    return await view_controller(setup_post_view_input=setup_post_input)


@router.post("/setup/fund")
async def setup_fund_post(
    setup_fund_post_input: Annotated[
        SetupFundPostV1Input, Body(openapi_examples=setup_fund_post_v1_input_swagger_examples)
    ]
):
    view_controller = SetupFundPostViewControllers.v1()
    return await view_controller(setup_post_view_input=setup_fund_post_input)


@router.post("/next_step")
async def next_step_post(next_step_post_input: NextStepPostV1Input = Body()):
    view_controller = NextStepPostViewControllers.v1()
    return await view_controller(next_step_post_view_input=next_step_post_input)


@router.post("/fund")
async def fund_post(fund_post_input: FundPostV1Input = Body()) -> FundPostV1Output:
    view_controller = FundPostViewControllers.v1()
    return await view_controller(fund_post_view_input=fund_post_input)


@router.post("/input")
async def input_post(input_input: InputPostV1Input = Body()) -> InputPostV1Output:
    view_controller = InputPostViewControllers.v1()
    return await view_controller(input_post_view_input=input_input)
