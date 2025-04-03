import asyncio
import logging
import os
import time
from datetime import datetime

import schedule
from dotenv import load_dotenv

from lead_pipeline import main as run_pipeline

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scheduler.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv(override=True)

def job():
    """
    Run the lead generation pipeline
    """
    try:
        logger.info(f"Starting lead generation pipeline at {datetime.now()}")
        
        # Run the pipeline asynchronously
        asyncio.run(run_pipeline())
        
        logger.info(f"Finished lead generation pipeline at {datetime.now()}")
    except Exception as e:
        logger.error(f"Error running lead generation pipeline: {str(e)}")
        logger.exception(e)

def main():
    """
    Main scheduler function
    """
    # Define the schedule - default to running once a day at 9 AM
    run_time = os.getenv("PIPELINE_RUN_TIME", "09:00")
    logger.info(f"Scheduling lead generation pipeline to run daily at {run_time}")
    
    # Schedule the job
    schedule.every().day.at(run_time).do(job)
    
    # If RUN_IMMEDIATELY is set to true, run the job immediately
    if os.getenv("RUN_IMMEDIATELY", "false").lower() == "true":
        logger.info("Running job immediately")
        job()
    
    # Keep the script running and check for scheduled jobs
    while True:
        schedule.run_pending()
        time.sleep(60)  # Sleep for 1 minute between checks

if __name__ == "__main__":
    main() 