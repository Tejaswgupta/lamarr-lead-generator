import asyncio
import os
import platform
import logging
from typing import Optional

from dotenv import load_dotenv
from supabase import Client, create_client

from utils.check_macos_requirements import check_macos_requirements
from utils.setup_driver import setup_driver
from utils.extraction.scrape_and_process_jobs import scrape_and_process_jobs
from utils.navigation.login_to_linkedin import login_to_linkedin


def setup_logging():
    """Configure logging for the script."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def load_config() -> dict:
    """Load and validate environment variables."""
    load_dotenv(override=True)
    config = {
        "SUPABASE_URL": os.getenv("SUPABASE_URL"),
        "SUPABASE_KEY": os.getenv("SUPABASE_KEY"),
        "LINKEDIN_USERNAME": os.getenv("LINKEDIN_USERNAME"),
        "LINKEDIN_PASSWORD": os.getenv("LINKEDIN_PASSWORD"),
    }
    missing = [k for k, v in config.items() if not v]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
    return config


def get_chrome_config() -> dict:
    """Return Chrome profile and binary config based on OS."""
    is_macos = platform.system() == "Darwin"
    if is_macos:
        return {
            "IS_MACOS": True,
            "CHROME_USER_DATA_DIR": "/Users/macmini/Library/Application Support/Google/Chrome/",
            "DEFAULT_PROFILE": "Profile 3",
            "CHROME_BINARY_PATHS": "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        }
    else:
        return {
            "IS_MACOS": False,
            "CHROME_USER_DATA_DIR": None,
            "DEFAULT_PROFILE": "Default",
            "CHROME_BINARY_PATHS": [],
        }


async def main() -> None:
    """Main function to run the LinkedIn Lead Generator script."""
    setup_logging()
    logging.info("🚀 Starting LinkedIn Lead Generator for macOS")
    logging.info("=" * 50)

    try:
        config = load_config()
        chrome_cfg = get_chrome_config()
        supabase: Client = create_client(config["SUPABASE_URL"], config["SUPABASE_KEY"])

        # Check macOS requirements
        if not check_macos_requirements(
            chrome_cfg["IS_MACOS"],
            chrome_cfg["CHROME_USER_DATA_DIR"],
            chrome_cfg["DEFAULT_PROFILE"],
            chrome_cfg["CHROME_BINARY_PATHS"],
        ):
            logging.error("System requirements not met. Please resolve the issues above.")
            return

        driver: Optional[object] = None
        try:
            logging.info("🔧 Setting up Chrome driver...")
            driver = setup_driver(
                chrome_cfg["IS_MACOS"],
                chrome_cfg["CHROME_USER_DATA_DIR"],
                chrome_cfg["DEFAULT_PROFILE"],
                chrome_cfg["CHROME_BINARY_PATHS"],
            )

            if not driver:
                logging.error("Failed to setup Chrome driver. Exiting...")
                return

            logging.info("🔐 Logging into LinkedIn...")
            login_to_linkedin(
                driver,
                config["LINKEDIN_USERNAME"],
                config["LINKEDIN_PASSWORD"],
            )

            # List of job search URLs to process
            urls = [
                "https://www.linkedin.com/jobs/search/?currentJobId=3843718022&f_TPR=r86400&geoId=92000000&keywords=generative%20ai&location=Worldwide&origin=JOB_SEARCH_PAGE_SEARCH_BUTTON&refresh=true&sortBy=DD",
                # Add more search URLs as needed
            ]

            # Process each URL
            for i, url in enumerate(urls, 1):
                logging.info(f"📋 Processing job search URL {i}/{len(urls)}")
                logging.info(f"🔗 {url}")
                await scrape_and_process_jobs(driver, url, max_items=100, supabase=supabase)

            logging.info("✅ Script completed successfully!")

        except KeyboardInterrupt:
            logging.warning("⏹️  Script interrupted by user")
        except Exception as e:
            logging.error(f"Error in main function: {str(e)}")
            if chrome_cfg["IS_MACOS"]:
                logging.error("🩺 macOS Troubleshooting:")
                logging.error("   - Try closing all Chrome windows and restart the script")
                logging.error("   - Check System Preferences > Security & Privacy for Chrome permissions")
                logging.error("   - Ensure Chrome is updated to the latest version")
                logging.error("   - Try running: brew upgrade google-chrome")
            logging.exception(e)
        finally:
            if driver:
                try:
                    driver.quit()
                    logging.info("🔒 Chrome driver closed successfully")
                except Exception as e:
                    logging.warning(f"Error closing driver: {e}")

    except Exception as e:
        logging.critical(f"Fatal error during setup: {e}")
        logging.exception(e)


if __name__ == "__main__":
    asyncio.run(main())
