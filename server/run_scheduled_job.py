#!/usr/bin/env python3
"""
Scheduled job runner for Insight-Invest data updates.
Designed to be executed by AWS EventBridge Scheduled Tasks.

Usage:
    python run_scheduled_job.py --job us-price
    python run_scheduled_job.py --job kr-price
    python run_scheduled_job.py --job macro
    python run_scheduled_job.py --job all  # Run all updates

Environment Variables:
    DATABASE_URL: PostgreSQL connection string (required)
    ENVIRONMENT: production/staging/development
    TZ: Timezone (default: Asia/Seoul)
"""
import sys
import os
import argparse
import logging
from datetime import datetime
from typing import Literal

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from module.update_data.price import update_daily_price
from module.update_data.macro import update_macro

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

JobType = Literal["us-price", "kr-price", "macro", "all"]


class JobRunner:
    """Manages scheduled job execution with proper error handling and logging."""
    
    def __init__(self, job_type: JobType):
        self.job_type = job_type
        self.start_time = datetime.now()
        self.success = False
        self.error_message = None
        
    def run(self) -> int:
        """
        Execute the scheduled job.
        
        Returns:
            0 for success, 1 for failure
        """
        logger.info("="*80)
        logger.info(f"Starting scheduled job: {self.job_type}")
        logger.info(f"Environment: {os.getenv('ENVIRONMENT', 'development')}")
        logger.info(f"Timezone: {os.getenv('TZ', 'UTC')}")
        logger.info(f"Start time: {self.start_time}")
        logger.info("="*80)
        
        try:
            if self.job_type == "us-price":
                self._run_us_price_update()
            elif self.job_type == "kr-price":
                self._run_kr_price_update()
            elif self.job_type == "macro":
                self._run_macro_update()
            elif self.job_type == "all":
                self._run_all_updates()
            else:
                raise ValueError(f"Unknown job type: {self.job_type}")
            
            self.success = True
            self._log_completion()
            return 0
            
        except Exception as error:
            self.error_message = str(error)
            self._log_error(error)
            return 1
    
    def _run_us_price_update(self):
        """Update US market price data."""
        logger.info("📊 Starting US market price update...")
        update_daily_price(market="US")
        logger.info("✅ US market price update completed successfully")
    
    def _run_kr_price_update(self):
        """Update KR market price data."""
        logger.info("📊 Starting KR market price update...")
        update_daily_price(market="KR")
        logger.info("✅ KR market price update completed successfully")
    
    def _run_macro_update(self):
        """Update macro economic data."""
        logger.info("📊 Starting macro data update...")
        update_macro()
        logger.info("✅ Macro data update completed successfully")
    
    def _run_all_updates(self):
        """Run all updates sequentially."""
        logger.info("📊 Starting all updates...")
        
        # US Market
        try:
            self._run_us_price_update()
        except Exception as e:
            logger.error(f"US price update failed: {e}")
        
        # KR Market
        try:
            self._run_kr_price_update()
        except Exception as e:
            logger.error(f"KR price update failed: {e}")
        
        # Macro
        try:
            self._run_macro_update()
        except Exception as e:
            logger.error(f"Macro update failed: {e}")
        
        logger.info("✅ All updates completed")
    
    def _log_completion(self):
        """Log successful completion with statistics."""
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        logger.info("="*80)
        logger.info(f"✅ Job completed successfully: {self.job_type}")
        logger.info(f"Start time: {self.start_time}")
        logger.info(f"End time: {end_time}")
        logger.info(f"Duration: {duration:.2f} seconds ({duration/60:.2f} minutes)")
        logger.info("="*80)
    
    def _log_error(self, error: Exception):
        """Log error with full traceback."""
        import traceback
        
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        logger.error("="*80)
        logger.error(f"❌ Job failed: {self.job_type}")
        logger.error(f"Error: {error}")
        logger.error(f"Duration before failure: {duration:.2f} seconds")
        logger.error("Traceback:")
        logger.error(traceback.format_exc())
        logger.error("="*80)


def validate_environment():
    """Validate required environment variables."""
    required_vars = ["DATABASE_URL"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        return False
    
    logger.info("✅ Environment validation passed")
    return True


def main():
    """Main entry point for the scheduled job runner."""
    parser = argparse.ArgumentParser(
        description="Run scheduled data update jobs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Update US market prices
    python run_scheduled_job.py --job us-price
    
    # Update KR market prices
    python run_scheduled_job.py --job kr-price
    
    # Update macro data
    python run_scheduled_job.py --job macro
    
    # Run all updates
    python run_scheduled_job.py --job all
        """
    )
    
    parser.add_argument(
        "--job",
        type=str,
        choices=["us-price", "kr-price", "macro", "all"],
        required=True,
        help="Job type to run"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode (no database writes)"
    )
    
    args = parser.parse_args()
    
    # Validate environment
    if not validate_environment():
        return 1
    
    # Handle dry-run mode
    if args.dry_run:
        logger.warning("🔍 Running in DRY-RUN mode (no database writes)")
        # Set environment variable for modules to check
        os.environ["DRY_RUN"] = "true"
    
    # Run the job
    runner = JobRunner(args.job)
    exit_code = runner.run()
    
    # Exit with appropriate code
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

