# %%
# LinkedIn Lead Generator with Local PostgreSQL
import os
import time
import json
import asyncio
import traceback
import logging
from datetime import datetime
from dotenv import load_dotenv
from selenium import webdriver
from selenium.common.exceptions import (NoSuchElementException,
                                        StaleElementReferenceException,
                                        TimeoutException)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
import asyncpg  # PostgreSQL database connector

# Load environment variables from .env file
load_dotenv(override=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('linkedin_scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', 5432),
    'database': os.getenv('DB_NAME', 'lead_generator'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'password')
}

# %%
def safe_find_element(driver, tag_or_css, css=None):
    """
    Find an element safely, handling possible exceptions.
    If called with 2 args: driver, css - uses CLASS_NAME as the By type
    If called with 3 args: driver, tag_type, css - uses the provided tag_type
    """
    try:
        if css is None:
            # Old pattern: driver, css (using CLASS_NAME)
            return driver.find_element(By.CLASS_NAME, tag_or_css)
        else:
            # New pattern: driver, tag_type, css
            return driver.find_element(tag_or_css, css)
    except Exception as e:
        logger.debug(f"Element not found: {e}")
        return None

def extract_name(profile_text):
    """Extract clean name from LinkedIn profile text"""
    # Remove 'View' and all variations of profile suffixes
    name = profile_text.replace("View ", "").strip()
    
    # Remove common profile suffixes
    suffixes = ["'s profile", "'s verified profile", "' verified profile", "' profile"]
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    
    return name.strip()

async def get_db_connection():
    """Get database connection"""
    try:
        conn = await asyncpg.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return None

async def setup_database():
    """Setup database tables"""
    conn = await get_db_connection()
    if not conn:
        return False
    
    try:
        # Create companies table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS companies (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                linkedin_url VARCHAR(500) UNIQUE,
                location VARCHAR(255),
                company_domain VARCHAR(255),
                metadata JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create recruiters table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS recruiters (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                linkedin_url VARCHAR(500) UNIQUE,
                company_domain VARCHAR(255),
                email VARCHAR(255),
                first_email TIMESTAMP,
                last_email TIMESTAMP,
                email_count INTEGER DEFAULT 0,
                apollo_sequence_status VARCHAR(50) DEFAULT 'pending',
                apollo_sequence_added_at TIMESTAMP,
                apollo_sequence_id VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create linkedin_jobs table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS linkedin_jobs (
                id BIGINT PRIMARY KEY,
                company_id INTEGER REFERENCES companies(id),
                recruiter_id INTEGER REFERENCES recruiters(id),
                title VARCHAR(500),
                description TEXT,
                role_metadata JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create processing_logs table for tracking
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS processing_logs (
                id SERIAL PRIMARY KEY,
                job_id BIGINT,
                recruiter_id INTEGER,
                status VARCHAR(50),
                error_message TEXT,
                processing_time FLOAT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        logger.info("Database tables created successfully")
        await conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Database setup failed: {e}")
        if conn:
            await conn.close()
        return False

async def insert_data(company_name, company_location, company_url, title, role_meta, 
                     hiring_manager_name, hiring_manager_linkedin_url, job_details, 
                     job_id, company_domain, company_details):
    """Insert scraped data into database"""
    conn = await get_db_connection()
    if not conn:
        return False
    
    try:
        company_url = company_url.replace("/about", "")
        
        # First check if company exists by LinkedIn URL
        company_row = await conn.fetchrow(
            "SELECT id FROM companies WHERE linkedin_url = $1", company_url
        )
        
        if not company_row and company_domain:
            # Check by domain if not found by LinkedIn URL
            company_row = await conn.fetchrow(
                "SELECT id FROM companies WHERE company_domain = $1", company_domain
            )
        
        if not company_row:
            # Insert new company
            company_id = await conn.fetchval('''
                INSERT INTO companies (name, linkedin_url, location, company_domain, metadata)
                VALUES ($1, $2, $3, $4, $5) RETURNING id
            ''', company_name, company_url, company_location, company_domain, company_details)
        else:
            company_id = company_row['id']
            # Update existing company if we have new information
            if company_domain:
                await conn.execute('''
                    UPDATE companies SET company_domain = $1, metadata = $2, updated_at = CURRENT_TIMESTAMP
                    WHERE id = $3
                ''', company_domain, company_details, company_id)
        
        recruiter_id = None
        if hiring_manager_name and hiring_manager_linkedin_url:
            # Check if recruiter exists
            recruiter_row = await conn.fetchrow(
                "SELECT id FROM recruiters WHERE linkedin_url = $1", hiring_manager_linkedin_url
            )
            
            if recruiter_row:
                recruiter_id = recruiter_row['id']
                # Update recruiter info
                await conn.execute('''
                    UPDATE recruiters SET name = $1, company_domain = $2, updated_at = CURRENT_TIMESTAMP
                    WHERE id = $3
                ''', hiring_manager_name, company_domain, recruiter_id)
            else:
                # Insert new recruiter
                recruiter_id = await conn.fetchval('''
                    INSERT INTO recruiters (name, linkedin_url, company_domain)
                    VALUES ($1, $2, $3) RETURNING id
                ''', hiring_manager_name, hiring_manager_linkedin_url, company_domain)
        
        # Insert job data
        await conn.execute('''
            INSERT INTO linkedin_jobs (id, company_id, recruiter_id, title, description, role_metadata)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (id) DO NOTHING
        ''', int(job_id), company_id, recruiter_id, title, job_details, json.dumps(role_meta))
        
        logger.info(f"Successfully inserted job {job_id} for company {company_name}")
        await conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Data insertion failed for job {job_id}: {e}")
        if conn:
            await conn.close()
        return False

def extract_company_details(driver):
    """Extract company details from LinkedIn company page"""
    try:
        # Wait for the section to be present
        wait = WebDriverWait(driver, 10)
        section = wait.until(EC.presence_of_element_located(
            (By.XPATH, "//section[@class='artdeco-card org-page-details-module__card-spacing artdeco-card org-about-module__margin-bottom']")))

        # Initialize a dictionary to store dt/dd pairs
        company_details = {}

        # Find all dt elements within the section
        dt_elements = section.find_elements(By.XPATH, ".//dt")

        for dt in dt_elements:
            # Get the text of the dt element
            dt_text = dt.text.strip()

            # Find the following dd element
            dd = dt.find_element(By.XPATH, "./following-sibling::dd[1]")
            dd_text = dd.text.strip()

            # Store the dt/dd pair in the dictionary
            company_details[dt_text] = dd_text

        # Convert the dictionary to a JSON object
        company_details_json = json.dumps(company_details, indent=4)
        logger.debug(f"Extracted company details: {company_details}")
        return company_details_json

    except Exception as e:
        logger.error(f"Error extracting company details: {e}")
        return json.dumps({})

async def write_data(driver, job_id):
    """Process and write job data"""
    start_time = time.time()
    
    # Check if job exists (commented out database check)
    """
    conn = await get_db_connection()
    if conn:
        existing_job = await conn.fetchrow("SELECT id FROM linkedin_jobs WHERE id = $1", int(job_id))
        await conn.close()
        if existing_job:
            logger.info(f'Job ID {job_id} already exists, skipping')
            return
    """
    
    logger.info(f'Processing job ID: {job_id}')
    
    try:
        title_el = safe_find_element(
            driver, By.CLASS_NAME, 'job-details-jobs-unified-top-card__job-title')
        title = title_el.text if title_el else None
        logger.info(f"Job title: {title}")

        try:
            company_link = driver.find_element(
                By.XPATH, "//a[starts-with(@href, 'https://www.linkedin.com/company/')]")
            company_name = company_link.text
            company_url = company_link.get_attribute('href')
        except NoSuchElementException:
            logger.error("Could not find company link")
            return

        company_domain = None
        company_details = json.dumps({})
        
        try:
            role_metadata = driver.execute_script("""
                return document.querySelector('.job-details-jobs-unified-top-card__primary-description-container')
                        .getElementsByTagName('div')[0].innerText;
            """)
            company_location = role_metadata.split("·")[0].strip()
            posted_at = role_metadata.split("·")[1].strip()
            applicants = role_metadata.split("·")[2].strip()

        except:
            logger.warning("Could not find company location metadata")
            company_location = None
            posted_at = None
            applicants = None

        logger.info(f"Company: {company_name}, Location: {company_location}")

        # Scrape company details by opening company page
        company_url_about = company_url.replace("life", "about")

        # Open a new window
        driver.execute_script("window.open('');")
        driver.switch_to.window(driver.window_handles[1])
        driver.get(company_url_about)
        time.sleep(2)

        try:
            logger.info("Extracting company domain and details")

            domain_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//a[@target='_blank' and contains(@class, 'link-without-visited-state')]"))
            )
            company_domain = domain_element.get_attribute('href')
            company_details = extract_company_details(driver)
            logger.info(f"Company domain: {company_domain}")

        except (NoSuchElementException, TimeoutException) as e:
            logger.warning(f"Could not extract company domain: {e}")
            company_domain = None
            company_details = json.dumps({})
        
        finally:
            # Always close the new window and switch back to the original
            driver.close()
            driver.switch_to.window(driver.window_handles[0])

        role_meta = {
            "posted_at": posted_at,
            "applicants": applicants
        }

        # Extract hiring manager info
        hiring_manager_element = safe_find_element(
            driver, By.CLASS_NAME, 'hirer-card__hirer-information')

        if hiring_manager_element:
            hiring_manager = hiring_manager_element.find_element(By.TAG_NAME, 'a')
            hiring_manager_name = extract_name(hiring_manager.get_attribute('aria-label'))
            hiring_manager_linkedin_url = hiring_manager.get_attribute('href')
        else:
            hiring_manager_name = None
            hiring_manager_linkedin_url = None
        
        logger.info(f"Hiring Manager: {hiring_manager_name}")

        job_details = driver.find_element(By.ID, 'job-details').text

        # Insert data into database
        success = await insert_data(
            company_name, company_location, company_url, title, role_meta, 
            hiring_manager_name, hiring_manager_linkedin_url, job_details, 
            job_id, company_domain, company_details
        )
        
        processing_time = time.time() - start_time
        
        if success:
            logger.info(f"Successfully processed job {job_id} in {processing_time:.2f} seconds")
        else:
            logger.error(f"Failed to process job {job_id}")
            
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"Error processing job {job_id}: {e}")
        traceback.print_exc()

def login(driver):
    """Login to LinkedIn"""
    logger.info("Starting LinkedIn login")
    driver.get("https://linkedin.com/uas/login")
    time.sleep(1)
    
    username = driver.find_element(By.ID, "username")
    username.send_keys(os.getenv("LINKEDIN_USERNAME"))
    password_field = driver.find_element(By.ID, "password")
    password_field.send_keys(os.getenv("LINKEDIN_PASSWORD"))
    driver.find_element(By.XPATH, "//button[@type='submit']").click()
    time.sleep(3)
    
    logger.info("LinkedIn login completed")

def check_for_captcha(driver):
    """Check and handle CAPTCHA if present"""
    captcha_selector = '/html/body/div/main/h1'
    try:
        captcha_element = driver.find_element(By.XPATH, captcha_selector)
        if captcha_element:
            logger.warning("CAPTCHA detected. Please solve the CAPTCHA to continue.")
            input("Press Enter after solving the CAPTCHA...")
    except NoSuchElementException:
        pass

def scroll_to_parent_ul(driver, li_class_name):
    """Scroll and load all job items on the page"""
    try:
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, li_class_name)))

        items = driver.find_elements(By.CLASS_NAME, li_class_name)
        prev_count = len(items)

        max_attempts = 10
        attempts = 0

        while attempts < max_attempts:
            last_item = items[-1]
            driver.execute_script("arguments[0].scrollIntoView(true);", last_item)
            time.sleep(2)

            items = driver.find_elements(By.CLASS_NAME, li_class_name)
            current_count = len(items)

            logger.info(f"Found {current_count} items after scrolling")

            if current_count == prev_count:
                attempts += 1
            else:
                attempts = 0

            prev_count = current_count

        return items
    except Exception as e:
        logger.error(f"Error scrolling to load items: {e}")
        return []

async def worker_process(driver, start_url, item_count):
    """Main worker process to scrape LinkedIn jobs"""
    try:
        while True:
            # Check for stop file
            if os.path.exists("STOP_SCRAPING"):
                logger.info("Stop file detected, ending scraping gracefully")
                break
                
            if item_count >= 1000:
                logger.info("Reached maximum item limit (1000)")
                break

            logger.info(f'Processing page at index {item_count}')
            url = f"{start_url}&start={item_count}"

            driver.get(url)

            try:
                list_items = scroll_to_parent_ul(driver, 'job-card-container')

                if len(list_items) == 0:
                    logger.info("No items found on page, ending scraping")
                    break

                logger.info(f'Found {len(list_items)} job items')

                for index, item in enumerate(list_items):
                    # Check for stop file before processing each job
                    if os.path.exists("STOP_SCRAPING"):
                        logger.info("Stop file detected, ending scraping gracefully")
                        return
                        
                    for attempt in range(3):
                        try:
                            item.click()
                            time.sleep(2)

                            job_id = item.get_attribute('data-job-id')
                            
                            try:
                                await write_data(driver, job_id)
                            except Exception as job_error:
                                logger.error(f"Error processing job {job_id}: {str(job_error)}")
                            
                            break

                        except StaleElementReferenceException:
                            if attempt == 2:
                                logger.error(f"Failed to process item after 3 attempts")
                            else:
                                logger.warning(f"Retrying item (attempt {attempt + 1})")
                                await asyncio.sleep(1)
                        except Exception as e:
                            logger.error(f"Error processing item: {str(e)}")
                            break

                logger.info('Moving to next page')
                item_count += 25

            except Exception as e:
                logger.error(f"Error processing page: {str(e)}")
                item_count += 25

    except Exception as e:
        logger.error(f"Worker process error: {e}")
        traceback.print_exc()

async def main():
    """Main function to run the scraper"""
    logger.info("Starting LinkedIn Lead Generator")
    
    # Setup database
    if not await setup_database():
        logger.error("Database setup failed, exiting")
        return
    
    # Setup Brave driver
    brave_options = Options()
    # brave_options.add_argument("--headless=new")  # Uncomment for headless mode
    brave_options.binary_location = "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
    
    # Use Chrome driver with Brave browser
    driver = webdriver.Chrome(options=brave_options)
    
    try:
        login(driver)
        check_for_captcha(driver=driver)

        # Job search URLs
        urls = [
            "https://www.linkedin.com/jobs/search/?currentJobId=3843718022&f_TPR=r86400&geoId=92000000&keywords=generative%20ai&location=Worldwide&origin=JOB_SEARCH_PAGE_SEARCH_BUTTON&refresh=true&sortBy=DD",
            # "https://www.linkedin.com/jobs/search/?currentJobId=3902861304&f_TPR=r86400&geoId=92000000&keywords=java&location=Worldwide&origin=JOB_SEARCH_PAGE_SEARCH_BUTTON&refresh=true&sortBy=DD",
            # "https://www.linkedin.com/jobs/search/?currentJobId=3906224840&f_TPR=r86400&geoId=92000000&keywords=php&location=Worldwide&origin=JOB_SEARCH_PAGE_SEARCH_BUTTON&refresh=true&sortBy=DD",
            # "https://www.linkedin.com/jobs/search/?currentJobId=3902943834&f_TPR=r86400&geoId=92000000&keywords=ios&location=Worldwide&origin=JOB_SEARCH_PAGE_SEARCH_BUTTON&refresh=true&sortBy=DD",
            # "https://www.linkedin.com/jobs/search/?currentJobId=3906227962&f_TPR=r86400&geoId=92000000&keywords=kotlin&location=Worldwide&origin=JOB_SEARCH_PAGE_SEARCH_BUTTON&refresh=true&sortBy=DD",
            # "https://www.linkedin.com/jobs/search/?currentJobId=3878359179&f_TPR=r86400&geoId=92000000&keywords=data%20science&location=Worldwide&origin=JOB_SEARCH_PAGE_KEYWORD_AUTOCOMPLETE&refresh=true&sortBy=DD",
            # "https://www.linkedin.com/jobs/search/?currentJobId=3906234356&f_TPR=r86400&geoId=92000000&keywords=python&location=Worldwide&origin=JOB_SEARCH_PAGE_SEARCH_BUTTON&refresh=true&sortBy=DD",
        ]

        for url in urls:
            logger.info(f"Processing URL: {url}")
            await worker_process(driver, url, 0)
            
    finally:
        # Clean up stop file if it exists
        if os.path.exists("STOP_SCRAPING"):
            os.remove("STOP_SCRAPING")
            logger.info("Removed stop file")
            
        driver.quit()
        logger.info("LinkedIn scraping completed")

if __name__ == "__main__":
    asyncio.run(main())
