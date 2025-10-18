# %%
# Apollo.io Automation with Local PostgreSQL and Prisma ORM
import os
import time
import json
import asyncio
import logging
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from prisma import Prisma
from prisma.models import Recruiter, Company, Job, ProcessingLog
import undetected_chromedriver as uc  # Working Cloudflare bypass

# Load environment variables
load_dotenv(override=True)

# Ensure DATABASE_URL is set for Prisma
if not os.getenv('DATABASE_URL'):
    # Construct DATABASE_URL from individual DB_* variables
    DATABASE_URL = f"postgresql://{os.getenv('DB_USER', 'postgres')}:{os.getenv('DB_PASSWORD', 'password')}@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', 5432)}/{os.getenv('DB_NAME', 'lead_generator')}"
    os.environ['DATABASE_URL'] = DATABASE_URL

# Setup logging with UTF-8 encoding
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('apollo_automation.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
BATCH_SIZE = 10
SEQUENCE_DELAY = 5  # seconds between sequence additions
DEFAULT_SEQUENCE_NAME = "Default Lead Sequence"  # Configure this as needed

# Global Prisma client instance
prisma_client = Prisma()

def calculate_name_match(expected_name, found_name):
    """Calculate similarity between expected and found person names"""
    if not expected_name or not found_name:
        return 0.0
    
    # Normalize names
    expected = expected_name.lower().strip()
    found = found_name.lower().strip()
    
    # Exact match
    if expected == found:
        return 1.0
    
    # Split into words and check overlap
    expected_words = set(expected.split())
    found_words = set(found.split())
    
    if not expected_words or not found_words:
        return 0.0
    
    # Calculate word overlap percentage
    common_words = expected_words.intersection(found_words)
    union_words = expected_words.union(found_words)
    
    # Jaccard similarity
    jaccard_score = len(common_words) / len(union_words) if union_words else 0.0
    
    # Also check if all expected words are in found name
    expected_in_found = len(expected_words.intersection(found_words)) / len(expected_words)
    
    # Return the higher of the two scores
    return max(jaccard_score, expected_in_found)


# %%
async def setup_database():
    """Setup database connection and create Prisma client"""
    try:
        # Connect to Prisma
        await prisma_client.connect()
        logger.info("Successfully connected to database via Prisma")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False

async def disconnect_database():
    """Disconnect from database"""
    try:
        await prisma_client.disconnect()
        logger.info("Successfully disconnected from database")
    except Exception as e:
        logger.error(f"Database disconnection failed: {e}")



async def fetch_pending_recruiters():
    """Fetch recruiters that haven't been added to Apollo sequences using Prisma ORM"""
    try:
        # Get recruiters with company and job information who haven't been processed
        recruiters = await prisma_client.recruiter.find_many(
            where={
                'apolloSequenceStatus': {
                    'in': ['pending', 'failed']
                },
                'companyDomain': {
                    'not': None
                },
                'name': {
                    'not': None
                }
            },
            include={
                'company': True,
                'jobs': True
            },
            order={
                'createdAt': 'desc'
            }
        )

        # Format the results to match expected structure
        result = []
        for recruiter in recruiters:
            result.append({
                'recruiter_id': recruiter.id,
                'name': recruiter.name,
                'company_domain': recruiter.companyDomain,
                'company_name': recruiter.company.name if recruiter.company else None,
                'status': recruiter.apolloSequenceStatus,
                'job_count': len(recruiter.jobs) if recruiter.jobs else 0
            })

        logger.info(f"Found {len(result)} pending recruiters")
        return result

    except Exception as e:
        logger.error(f"Error fetching pending recruiters: {e}")
        return []

async def update_recruiter_status(recruiter_id, status, sequence_id=None, error_message=None):
    """Update recruiter's Apollo sequence status using Prisma ORM"""
    try:
        # Prepare update data
        update_data = {
            'apolloSequenceStatus': status
        }

        if status == 'success':
            update_data['apolloSequenceAddedAt'] = datetime.now()
            if sequence_id:
                update_data['apolloSequenceId'] = sequence_id

        # Update recruiter status
        await prisma_client.recruiter.update(
            where={'id': recruiter_id},
            data=update_data
        )

        # Log the update in processing_logs
        await prisma_client.processingLog.create(
            data={
                'recruiterId': recruiter_id,
                'status': status,
                'errorMessage': error_message
            }
        )

        logger.info(f"Updated recruiter {recruiter_id} status to {status}")
        return True

    except Exception as e:
        logger.error(f"Error updating recruiter status: {e}")
        return False

def login(driver):
    """Login to Apollo.io with CAPTCHA handling"""
    logger.info("Starting Apollo.io login")
    driver.get("https://app.apollo.io/#/login")
    
    # Wait for page to load
    time.sleep(5)
    
    logger.info("APOLLO LOGIN INSTRUCTIONS")
    logger.info("=" * 50)
    logger.info("Please complete the login process manually in the browser:")
    logger.info("")
    logger.info("STEPS:")
    logger.info("   1. Check 'Verify you are human' checkbox")
    logger.info("   2. Enter email: tejasw@thevotum.com")
    logger.info("   3. Enter password from your .env file")
    logger.info("   4. If error popup appears, close it and try again")
    logger.info("   5. Complete any additional verification if needed")
    logger.info("   6. Wait until you see the Apollo dashboard")
    logger.info("")
    logger.info("TIP: If verification fails, try:")
    logger.info("   • Refresh the page (F5)")
    logger.info("   • Use a different browser tab")
    logger.info("   • Wait a few minutes and try again")
    logger.info("")
    print("=" * 50)
    
    # Give user time to see instructions
    time.sleep(2)
    
    # Wait for user to complete login
    input("After successfully logging in to Apollo, press Enter to continue: ")
    
    # Verify login was successful
    try:
        # Check if we're on the dashboard or people page
        current_url = driver.current_url
        if "apollo.io" in current_url and ("dashboard" in current_url or "people" in current_url or "app.apollo.io" in current_url):
            logger.info("Login verification successful!")
        else:
            logger.warning(f"Current URL: {current_url}")
            logger.warning("Please make sure you're logged in to Apollo")
            confirm = input("Are you successfully logged in to Apollo? (y/n): ")
            if confirm.lower() != 'y':
                logger.error("Login verification failed")
                return False
    except Exception as e:
        logger.warning(f"Could not verify login status: {e}")
    
    logger.info("Login completed, proceeding with automation...")
    return True

def clean_person_name(name):
    """Clean person name by removing extra text like 's verified profile, etc."""
    if not name:
        return name
    
    # Remove common suffixes that appear in LinkedIn data
    suffixes_to_remove = [
        "'s verified profile",
        "’s verified profile", 
        "'s profile",
        "s profile",
        " verified profile",
        "verified profile",
        "'s linkedin profile",
        "s linkedin profile",
        " linkedin profile",
        "linkedin profile"
    ]
    
    cleaned_name = name.strip()
    logger.debug(f"Step 1 - Initial name: '{cleaned_name}'")
    
    # Remove each suffix (case insensitive)
    for suffix in suffixes_to_remove:
        if cleaned_name.lower().endswith(suffix.lower()):
            cleaned_name = cleaned_name[:-len(suffix)].strip()
            logger.debug(f"Step 2 - After removing '{suffix}': '{cleaned_name}'")
            break
    
    # Remove any trailing apostrophes and quotes that might be left
    before_apostrophe_removal = cleaned_name
    cleaned_name = cleaned_name.rstrip("'\"").strip()
    if before_apostrophe_removal != cleaned_name:
        logger.debug(f"Step 3 - After removing trailing apostrophes: '{before_apostrophe_removal}' -> '{cleaned_name}'")
    
    # Remove any extra whitespace and return
    cleaned_name = ' '.join(cleaned_name.split())
    
    logger.info(f"Name cleaning: '{name}' -> '{cleaned_name}'")
    return cleaned_name

def search_recruiter(driver, hiring_manager, company_domain):
    """Search for a specific recruiter on Apollo.io"""
    # Clean the hiring manager name first
    clean_name = clean_person_name(hiring_manager)
    
    logger.info(f"Starting search for {clean_name} at {company_domain}")
    if clean_name != hiring_manager:
        logger.info(f"Original name: '{hiring_manager}' -> Cleaned: '{clean_name}'")
    logger.info(f"Step 1: Navigate to People page")
    
    driver.get("https://app.apollo.io/#/people")
    logger.info("Waiting for People page to load completely...")
    time.sleep(8)  # Increased wait time for page load
    
    # Verify page loaded by checking for key elements
    try:
        WebDriverWait(driver, 15).until(
            EC.any_of(
                EC.presence_of_element_located((By.CSS_SELECTOR, "button[data-cy='company-filter']")),
                EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Company')]")),
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder*='Search']"))
            )
        )
        logger.info("People page loaded successfully")
    except Exception as e:
        logger.warning(f"Could not verify page load: {e}")
        time.sleep(5)  # Additional wait as fallback

    # Updated selectors for Apollo 2025
    company_dropdown_selectors = [
        "button[data-cy='company-filter']",
        "div[data-testid='company-dropdown']",
        "button[aria-label*='Company']",
        "div[role='button']:has-text('Company')",
        "//button[contains(text(), 'Company')]",
        "//div[contains(@class, 'filter-item')]//span[text()='Company']/parent::div",
        "//div[contains(@data-cy, 'company')]",
        "//div[contains(@class, 'zp_YfgQq')]/span[text()='Company']/parent::div"
    ]

    # Try multiple selectors for company dropdown
    company_dropdown_btn = None
    for selector in company_dropdown_selectors:
        try:
            if selector.startswith("//"):
                company_dropdown_btn = driver.find_element(By.XPATH, selector)
            else:
                company_dropdown_btn = driver.find_element(By.CSS_SELECTOR, selector)
            logger.debug(f"Found company dropdown with selector: {selector}")
            break
        except:
            continue
    
    if not company_dropdown_btn:
        logger.error("Could not find company dropdown button")
        return None
    
    logger.info(f"Step 2: Click company filter dropdown")
    # Click company dropdown
    driver.execute_script("arguments[0].scrollIntoView(true);", company_dropdown_btn)
    time.sleep(1)
    company_dropdown_btn.click()
    time.sleep(2)
    
    # Updated selectors for company input
    company_input_selectors = [
        "input[data-cy='company-input']",
        "input[placeholder*='company']",
        "input[placeholder*='Company']",
        "input[role='combobox']",
        "input[type='text']",
        ".Select-input input",
        "Select-input"
    ]
    
    company_input_box = None
    for selector in company_input_selectors:
        try:
            if selector == "Select-input":
                company_input_box = driver.find_element(By.CLASS_NAME, selector)
            else:
                company_input_box = driver.find_element(By.CSS_SELECTOR, selector)
            logger.debug(f"Found company input with selector: {selector}")
            break
        except:
            continue
    
    if not company_input_box:
        logger.error("Could not find company input box")
        return None
    
    logger.info(f"Step 3: Enter company domain in filter")
    # Clear and enter company domain with better error handling
    company_typed_successfully = False
    max_typing_attempts = 3
    
    for typing_attempt in range(max_typing_attempts):
        try:
            logger.info(f"Typing attempt {typing_attempt + 1}/{max_typing_attempts}")
            
            # Clear the input field
            company_input_box.clear()
            time.sleep(0.5)
            
            # Type the company domain
            company_input_box.send_keys(company_domain)
            logger.info(f"Typed company domain: {company_domain}")
            
            # Immediately check if the text is still there
            time.sleep(1)  # Give it a moment to register
            current_value = company_input_box.get_attribute('value')
            logger.info(f"Current input value after typing: '{current_value}'")
            
            if current_value and company_domain.lower() in current_value.lower():
                logger.info("✓ Company domain typed successfully and persisted")
                company_typed_successfully = True
                break
            else:
                logger.warning(f"❌ Company domain disappeared! Expected: '{company_domain}', Found: '{current_value}'")
                if typing_attempt < max_typing_attempts - 1:
                    logger.info("Retrying typing...")
                    time.sleep(2)  # Wait before retry
                    continue
                
        except Exception as e:
            logger.error(f"Error typing company domain (attempt {typing_attempt + 1}): {e}")
            if typing_attempt < max_typing_attempts - 1:
                time.sleep(2)
                continue
    
    if not company_typed_successfully:
        logger.error("Failed to type company domain successfully after multiple attempts")
        return None
    
    # Now wait for suggestions to appear - but don't wait too long as field might clear
    logger.info(f"Step 4: Quickly look for company suggestions before field clears")
    logger.info("Looking for company suggestions immediately...")
    
    # Try to catch suggestions quickly before they disappear
    suggestion_found = False
    quick_suggestion_attempts = 3
    
    for quick_attempt in range(quick_suggestion_attempts):
        logger.info(f"Quick suggestion attempt {quick_attempt + 1}/{quick_suggestion_attempts}")
        
        # Check if input still has our text
        try:
            current_value = company_input_box.get_attribute('value')
            if not current_value or company_domain.lower() not in current_value.lower():
                logger.warning(f"Input field cleared! Re-typing company domain...")
                company_input_box.clear()
                time.sleep(0.3)
                company_input_box.send_keys(company_domain)
                time.sleep(0.5)
        except:
            pass

        
        # Look for suggestions immediately with shorter timeouts
        suggestion_selectors = [
            # Based on screenshot structure - try fastest selectors first
            "div.Select-menu-outer div.Select-option",
            ".Select-menu-outer .Select-option",
            "div[class*='Select-menu-outer'] div[class*='Select-option']",
            "//div[contains(@class, 'Select-menu-outer')]//div[contains(@class, 'Select-option')]",
            # Generic quick selectors
            "div[role='option']",
            ".Select-option",
            "//div[@role='option']"
        ]
        
        for selector in suggestion_selectors:
            try:
                # Use very short timeout to catch suggestions quickly
                if selector.startswith("//"):
                    suggestions = WebDriverWait(driver, 1).until(
                        EC.presence_of_all_elements_located((By.XPATH, selector))
                    )
                else:
                    suggestions = WebDriverWait(driver, 1).until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                    )
                
                if suggestions and len(suggestions) > 0:
                    logger.info(f"🎯 FOUND {len(suggestions)} suggestions quickly with: {selector}")
                    
                    # Click the first suggestion immediately
                    for suggestion in suggestions:
                        try:
                            if suggestion.is_displayed() and suggestion.is_enabled():
                                suggestion_text = suggestion.text.strip()
                                logger.info(f"⚡ Immediately clicking suggestion: '{suggestion_text}'")
                                
                                # Use JavaScript click for speed
                                driver.execute_script("arguments[0].click();", suggestion)
                                time.sleep(1)  # Brief wait to see if it worked
                                
                                # Verify selection worked
                                try:
                                    post_click_value = company_input_box.get_attribute('value')
                                    logger.info(f"✅ After click, input value: '{post_click_value}'")
                                    if post_click_value and len(post_click_value) > 0:
                                        suggestion_found = True
                                        logger.info(f"SUCCESS: Company suggestion selected: '{suggestion_text}'")
                                        break
                                except:
                                    pass
                                    
                        except Exception as click_error:
                            logger.debug(f"Failed to click suggestion: {click_error}")
                            continue
                    
                    if suggestion_found:
                        break
                        
            except Exception as e:
                logger.debug(f"Quick selector {selector} failed: {e}")
                continue
        
        if suggestion_found:
            break
            
        # If no suggestions found quickly, wait a bit and try again
        if quick_attempt < quick_suggestion_attempts - 1:
            logger.info("No quick suggestions found, waiting 0.5 seconds...")
            time.sleep(0.5)
    
    # If still no company selected after quick attempts, try the original slower method
    if not suggestion_found:
        logger.warning("⚠️ Quick suggestion method failed, trying slower comprehensive method...")
        
        # Re-type the company domain one more time
        try:
            company_input_box.clear()
            time.sleep(0.5)
            company_input_box.send_keys(company_domain)
            logger.info(f"Re-typed company domain for slower method: {company_domain}")
            time.sleep(2)  # Wait for suggestions to appear
        except Exception as retype_error:
            logger.error(f"Failed to re-type company domain: {retype_error}")
            return None
            return None
        
        # Try the original comprehensive method
        comprehensive_suggestion_selectors = [
            "div.Select-menu-outer div.Select-option",
            ".Select-menu-outer .Select-option",
            "div[class*='Select-menu'] div[class*='Select-option']",
            "div[class*='Select-menu-outer'] div[class*='Select-option']",
            "//div[contains(@class, 'Select-menu-outer')]//div[contains(@class, 'Select-option')]",
            "//div[contains(@class, 'Select-menu')]//div[contains(@class, 'Select-option')]",
            "div[role='option']",
            "li[role='option']", 
            ".Select-option",
            "div[data-cy='dropdown-option']",
            "div[data-testid='company-option']",
            "//div[@role='option']",
            "//li[@role='option']"
        ]
        
        company_selected = False
        
        # Try multiple attempts to catch suggestions
        for attempt in range(3):  # Reduced attempts since we tried quick method first
            logger.info(f"Comprehensive attempt {attempt + 1}/3 to find company suggestions")
            
            for selector in comprehensive_suggestion_selectors:
                try:
                    # Wait for suggestions to appear
                    if selector.startswith("//"):
                        suggestions = WebDriverWait(driver, 2).until(
                            EC.presence_of_all_elements_located((By.XPATH, selector))
                        )
                    else:
                        suggestions = WebDriverWait(driver, 2).until(
                            EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                        )
                    
                    if suggestions and len(suggestions) > 0:
                        logger.info(f"Found {len(suggestions)} company suggestions with selector: {selector}")
                        
                        # Log first few suggestions for debugging
                        for i, suggestion in enumerate(suggestions[:3]):
                            try:
                                suggestion_text = suggestion.text.strip()
                                logger.info(f"  Suggestion {i+1}: '{suggestion_text}'")
                            except:
                                logger.info(f"  Suggestion {i+1}: (text not readable)")
                        
                        # Click the first visible and clickable suggestion
                        for suggestion in suggestions:
                            try:
                                if suggestion.is_displayed() and suggestion.is_enabled():
                                    suggestion_text = suggestion.text.strip()
                                    logger.info(f"Selecting first available suggestion: '{suggestion_text}'")
                                    
                                    # Scroll to suggestion and click
                                    driver.execute_script("arguments[0].scrollIntoView(true);", suggestion)
                                    time.sleep(0.5)
                                    
                                    # Try multiple click methods
                                    try:
                                        suggestion.click()
                                        logger.info("Clicked using regular click")
                                    except:
                                        try:
                                            driver.execute_script("arguments[0].click();", suggestion)
                                            logger.info("Clicked using JavaScript click")
                                        except:
                                            # Try ActionChains as final fallback
                                            from selenium.webdriver.common.action_chains import ActionChains
                                            ActionChains(driver).move_to_element(suggestion).click().perform()
                                            logger.info("Clicked using ActionChains")
                                    
                                    company_selected = True
                                    time.sleep(2)  # Wait for selection to process
                                    logger.info(f"SUCCESS: Selected company suggestion: '{suggestion_text}'")
                                    break
                            except Exception as click_error:
                                logger.debug(f"Failed to click suggestion: {click_error}")
                                continue
                        
                        if company_selected:
                            break
                    
                except Exception as e:
                    logger.debug(f"Selector {selector} failed on attempt {attempt + 1}: {e}")
                    continue
            
            if company_selected:
                break
                
            # If no suggestions found, wait a bit and try again
            if not company_selected and attempt < 2:
                logger.info("No suggestions found, waiting 1 second before retry...")
                time.sleep(1)
    
    # Final verification and fallback
    if not suggestion_found and not company_selected:
        logger.warning("❌ Both quick and comprehensive methods failed")
        
        # Final fallback - just press Enter to confirm whatever is in the field
        try:
            current_value = company_input_box.get_attribute('value')
            logger.info(f"Final fallback: Current input value is '{current_value}'")
            
            if current_value and len(current_value.strip()) > 0:
                logger.info("Pressing Enter to confirm typed domain as fallback")
                company_input_box.send_keys(Keys.ENTER)
                time.sleep(2)
                company_selected = True
            else:
                logger.error("Input field is empty, cannot proceed")
                return None
                
        except Exception as fallback_error:
            logger.error(f"Final fallback failed: {fallback_error}")
            return None
    else:
        company_selected = True  # Either quick method or comprehensive method worked
    
    if not company_selected:
        logger.error(f"❌ Failed to select company for {company_domain}")
        return None
    
    logger.info(f"✅ Company selection completed for {company_domain}")
    
    logger.info(f"Step 5: Wait for company people to load (5 seconds)")
    # Wait for company filter to be applied and people to load
    logger.info("Waiting for company filter to be applied and people to load...")
    time.sleep(5)  # Wait for the company people to load
    
    # Verify company filter was applied by checking if company name appears in filter
    try:
        # Look for applied company filter indicator
        filter_indicators = [
            "//span[contains(@class, 'filter-tag')]",
            "//div[contains(@class, 'applied-filter')]",
            "//div[contains(@class, 'filter-chip')]"
        ]
        
        filter_applied = False
        for indicator_selector in filter_indicators:
            try:
                filter_elements = driver.find_elements(By.XPATH, indicator_selector)
                if filter_elements:
                    logger.info("Company filter appears to be applied")
                    filter_applied = True
                    break
            except:
                continue
        
        if not filter_applied:
            logger.warning("Could not verify if company filter was applied")
    except Exception as e:
        logger.debug(f"Could not verify filter application: {e}")
    
    logger.info(f"Step 6: Search for person in main search box")
    # Now search for the hiring manager in the search box beside filters
    logger.info(f"Searching for person: {clean_name}")
    
    # Look for the search input box beside the filters (top right area)
    search_box_selectors = [
        "input[placeholder*='Search']",
        "input[data-cy='search-input']", 
        "input[data-testid='search-input']",
        "input[type='search']",
        "input[aria-label*='Search']",
        "//input[contains(@placeholder, 'Search')]",
        "//div[contains(@class, 'search')]//input",
        "//input[@type='search']"
    ]
    
    search_input = None
    for selector in search_box_selectors:
        try:
            if selector.startswith("//"):
                search_input = driver.find_element(By.XPATH, selector)
            else:
                search_input = driver.find_element(By.CSS_SELECTOR, selector)
            
            # Verify this is the right search box (not inside filters)
            search_input_location = search_input.location
            logger.debug(f"Found search input with selector: {selector} at location: {search_input_location}")
            break
        except:
            continue
    
    if not search_input:
        logger.error("Could not find the main search input box")
        return None
    
    # Clear and enter the hiring manager's cleaned name
    logger.info(f"Entering person name: {clean_name}")
    search_input.clear()
    time.sleep(1)
    search_input.send_keys(clean_name)
    time.sleep(3)  # Wait for typing to complete
    search_input.send_keys(Keys.RETURN)
    
    # Wait for search results to load
    logger.info("Waiting for person search results to load...")
    time.sleep(8)  # Increased wait time for search results

    # Find hiring manager in results
    try:
        logger.info(f"Looking for {clean_name} in search results")
        
        # Wait longer for search results to load with better error handling
        try:
            WebDriverWait(driver, 15).until(
                EC.any_of(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-cy='person-card']")),
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".zp_xVJ20")),
                    EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='person']")),
                    EC.presence_of_element_located((By.CSS_SELECTOR, "tr[data-testid='person-row']"))
                )
            )
            logger.info("Search results loaded successfully")
        except Exception as e:
            logger.warning(f"Search results may not have loaded properly: {e}")
            
        time.sleep(5)  # Additional wait for results to stabilize
        
        # Look for person cards/links in the results - updated based on actual Apollo HTML structure
        person_card_selectors = [
            # From screenshot - these appear to be the actual classes used
            ".zp_TPOm2",  # Person card container class from screenshot
            ".zp_jZq6M",  # Another person element class visible
            "div[data-testid='contact-name-cell']",  # Contact name cell
            "div[class*='zp_TPOm2']",  # Any div with zp_TPOm2 class
            "div[class*='zp_jZq6M']",  # Any div with zp_jZq6M class
            # Original selectors as fallback
            "div[data-cy='person-card']",
            ".zp_xVJ20", 
            "a[href*='person']",
            "div[data-testid='person-card']",
            "tr[data-testid='person-row']",
            # XPath selectors for broader matching
            "//div[contains(@class, 'zp_TPOm2')]",
            "//div[contains(@class, 'zp_jZq6M')]",
            "//div[contains(@class, 'person')]//a",
            "//tr[contains(@data-testid, 'person')]",
            "//a[contains(@href, 'person')]"
        ]
        
        hiring_manager_element = None
        found_person_name = ""
        
        # Add debugging to see what's actually on the page
        logger.info("Looking for person elements on page...")
        
        for selector in person_card_selectors:
            try:
                if selector.startswith("//"):
                    elements = driver.find_elements(By.XPATH, selector)
                else:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                
                if elements and len(elements) > 0:
                    logger.info(f"Found {len(elements)} person element(s) using selector: {selector}")
                    
                    # Check each element to find the best name match
                    for i, element in enumerate(elements[:5]):  # Check first 5 results
                        try:
                            # Look for the name within this element
                            name_selectors = [
                                ".//div[contains(@class, 'zp_TPOm2')]//span",
                                ".//div[contains(@class, 'zp_jZq6M')]//span", 
                                ".//a[contains(@href, 'person')]",
                                ".//*[contains(@data-testid, 'contact-name')]",
                                ".//span[contains(@class, 'name')]",
                                ".//div[contains(@class, 'name')]",
                                ".//a",
                                ".//span"
                            ]
                            
                            element_name = ""
                            for name_sel in name_selectors:
                                try:
                                    name_elem = element.find_element(By.XPATH, name_sel)
                                    potential_name = name_elem.text.strip()
                                    if potential_name and len(potential_name) > 2:
                                        element_name = potential_name
                                        break
                                except:
                                    continue
                            
                            if not element_name:
                                element_name = element.text.strip()
                            
                            logger.info(f"  Person {i+1}: '{element_name}'")
                            
                            # Verify name match using improved logic
                            if element_name:
                                name_match_score = calculate_name_match(clean_name, element_name)
                                logger.info(f"  Name match score for '{element_name}': {name_match_score}")
                                
                                # Accept if high similarity (80% or higher)
                                if name_match_score >= 0.8:
                                    hiring_manager_element = element
                                    found_person_name = element_name
                                    logger.info(f"EXACT MATCH: Found '{element_name}' (score: {name_match_score:.2f})")
                                    break
                                # For moderate similarity (50-79%), ask user
                                elif name_match_score >= 0.5:
                                    logger.warning(f"PARTIAL MATCH: Found '{element_name}' for search '{clean_name}' (score: {name_match_score:.2f})")
                                    logger.warning(f"Expected: '{clean_name}'")
                                    logger.warning(f"Found: '{element_name}'")
                                    
                                    # Ask user if they want to proceed
                                    user_input = input(f"\nPartial name match found!\nSearched for: '{clean_name}'\nFound: '{element_name}'\nMatch score: {name_match_score:.2f}\n\nProceed with this person? (y/n): ").strip().lower()
                                    
                                    if user_input in ['y', 'yes']:
                                        hiring_manager_element = element
                                        found_person_name = element_name
                                        logger.info(f"USER APPROVED: Proceeding with '{element_name}'")
                                        break
                                    else:
                                        logger.info(f"USER REJECTED: Skipping '{element_name}'")
                                        continue
                                else:
                                    logger.info(f"  Low match score ({name_match_score:.2f}), skipping")
                            
                        except Exception as elem_error:
                            logger.debug(f"Error processing element {i}: {elem_error}")
                            continue
                    
                    if hiring_manager_element:
                        break
                    
            except Exception as e:
                logger.debug(f"Selector {selector} failed: {e}")
                continue
        
        if not hiring_manager_element:
            logger.warning(f"Could not find any person results for {clean_name}")
            
            # Basic page state check
            try:
                current_url = driver.current_url
                if "people" not in current_url:
                    logger.warning("Not on people search page")
                    return None
                
                # Look for "no results" messages
                no_results_indicators = [
                    "No results found",
                    "no people found", 
                    "0 results",
                    "Try adjusting your filters"
                ]
                
                page_text = driver.page_source.lower()
                for indicator in no_results_indicators:
                    if indicator.lower() in page_text:
                        logger.info(f"Found no results indicator: {indicator}")
                        break
                        
            except Exception as debug_error:
                logger.debug(f"Debug info collection failed: {debug_error}")
            
            return None

        logger.info(f"Found person element for {clean_name}")
        
        # Safer scrolling with error handling
        try:
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", hiring_manager_element)
            time.sleep(2)
        except Exception as scroll_error:
            logger.debug(f"Scrolling failed: {scroll_error}")
        
        return hiring_manager_element
        
    except Exception as e:
        logger.error(f"Error finding hiring manager {clean_name}: {e}")
        # Don't return None immediately, try to continue
        logger.info("Attempting to continue despite error...")
        return None

def find_correct_sequence_button(driver, hiring_manager_element):
    """Helper function to find the correct 'Add to sequence' button and avoid search triggers"""
    try:
        # Look for parent container using classes from screenshot
        parent_container = hiring_manager_element.find_element(By.XPATH, "./ancestor::div[contains(@class, 'zp_TPOm2') or contains(@class, 'zp_jZq6M') or contains(@class, 'zp_') or contains(@class, 'result') or contains(@class, 'person')]")
        logger.debug("Found parent container for person element")
    except:
        parent_container = driver  # Fall back to searching the whole page
        logger.debug("Using whole page as container")
    
    # More targeted selectors that look for buttons within the person's row/card
    sequence_button_selectors = [
        # Look specifically in table cells or person cards for sequence buttons
        ".//td//button[.//span[normalize-space(text())='Add to sequence']]",
        ".//td//button[.//span[normalize-space(text())='Manage sequences']]",
        ".//div[contains(@class, 'zp_')]//button[.//span[contains(text(), 'sequence')] and not(contains(text(), 'search'))]",
        # Look for buttons that are siblings to the person name
        ".//button[.//span[normalize-space(text())='Add to sequence'] and ancestor::tr]",
        ".//button[.//span[normalize-space(text())='Manage sequences'] and ancestor::tr]",
        # Look in action columns or button groups
        ".//div[contains(@class, 'action') or contains(@class, 'button')]//button[.//span[contains(text(), 'sequence')]]"
    ]
    
    for selector in sequence_button_selectors:
        try:
            button = parent_container.find_element(By.XPATH, selector)
            if button and button.is_displayed():
                # Additional validation
                button_text = button.text.strip()
                button_classes = button.get_attribute("class") or ""
                
                # Make sure it's not a search-related button
                if not any(search_term in button_classes.lower() for search_term in ['search', 'filter', 'quick']):
                    if not any(search_term in button_text.lower() for search_term in ['search', 'filter', 'quick']):
                        logger.info(f"Found valid sequence button: {button_text}")
                        return button
        except Exception as e:
            logger.debug(f"Sequence button selector failed: {selector} - {e}")
            continue
    
    return None

def add_to_sequence(driver, hiring_manager_element, hiring_manager, company_domain):
    """Add hiring manager to Apollo sequence using the exact workflow from screenshots"""
    try:
        logger.info(f"Starting sequence addition for {hiring_manager}")
        
        # Step 1: Find the "Manage sequences" button with the exact classes from screenshot
        logger.info("Step 1: Looking for 'Manage sequences' button")
        
        # Enhanced selectors based on Apollo's current structure
        # Since person is found with div[data-testid='contact-name-cell'], we know it's in a table
        manage_sequences_selectors = [
            # Look within the same table row as the contact-name-cell
            ".//ancestor::tr//button[contains(text(), 'Manage sequences')]",
            ".//ancestor::tr//button[.//span[contains(text(), 'Manage sequences')]]",
            ".//ancestor::tr//button[contains(text(), 'Add to sequence')]", 
            ".//ancestor::tr//button[.//span[contains(text(), 'Add to sequence')]]",
            
            # Look for buttons with specific data attributes in the same row
            ".//ancestor::tr//button[@data-testid]",
            ".//ancestor::tr//button[contains(@data-testid, 'sequence')]",
            ".//ancestor::tr//button[contains(@data-testid, 'manage')]",
            ".//ancestor::tr//button[contains(@data-testid, 'action')]",
            
            # Look for action buttons in table cells
            ".//ancestor::tr//td//button[contains(@class, 'zp_TPOm2')]",
            ".//ancestor::tr//td//button[contains(@class, 'zp_jZq6M')]",
            ".//ancestor::tr//td//button[contains(@class, 'zp_')]",
            
            # Look for any button in the actions column (usually last column)
            ".//ancestor::tr//td[last()]//button",
            ".//ancestor::tr//td[position()>=last()-1]//button",
            
            # Look within specific table cell types
            ".//ancestor::tr//td[contains(@class, 'action')]//button",
            ".//ancestor::tr//td[@data-testid]//button",
            
            # Generic button search in same row
            ".//ancestor::tr//button",
            
            # Look for buttons by visual position (right side of row)
            ".//ancestor::tr//button[contains(@style, 'float: right') or contains(@class, 'right')]",
            
            # Look for dropdown triggers or menu buttons
            ".//ancestor::tr//button[contains(@aria-haspopup, 'true')]",
            ".//ancestor::tr//button[contains(@class, 'dropdown')]",
            ".//ancestor::tr//button[contains(@class, 'menu')]",
            
            # Global search as last resort
            "//button[contains(text(), 'Manage sequences')]",
            "//button[.//span[contains(text(), 'Manage sequences')]]",
            "//button[contains(@class, 'zp_TPOm2')]",
            "//button[contains(@class, 'zp_jZq6M')]"
        ]
        
        manage_sequences_button = None
        
        # Add debugging to see what buttons are available
        logger.info("🔍 Debugging: Looking for all buttons in the person's row...")
        
        # First, verify we have the right element structure
        try:
            parent_row = hiring_manager_element.find_element(By.XPATH, ".//ancestor::tr")
            logger.info("✓ Found parent table row for the person")
            
            # Check row structure
            cells = parent_row.find_elements(By.TAG_NAME, "td")
            logger.info(f"Row has {len(cells)} table cells")
            
            for i, cell in enumerate(cells[:7]):  # Check first 7 cells
                try:
                    cell_text = cell.text.strip()[:50]  # First 50 chars
                    cell_classes = cell.get_attribute("class") or ""
                    cell_testid = cell.get_attribute("data-testid") or ""
                    logger.info(f"  Cell {i+1}: text='{cell_text}...', classes='{cell_classes[:30]}...', testid='{cell_testid}'")
                except Exception as cell_error:
                    logger.debug(f"Error analyzing cell {i}: {cell_error}")
                    
        except Exception as row_error:
            logger.warning(f"Could not find parent table row: {row_error}")
        
        try:
            # Look for all buttons in the same row
            debug_buttons = hiring_manager_element.find_elements(By.XPATH, ".//ancestor::tr//button")
            logger.info(f"Found {len(debug_buttons)} total buttons in the row")
            
            for i, btn in enumerate(debug_buttons[:8]):  # Show first 8 buttons
                try:
                    btn_text = btn.text.strip()
                    btn_classes = btn.get_attribute("class") or ""
                    btn_aria = btn.get_attribute("aria-label") or ""
                    btn_title = btn.get_attribute("title") or ""
                    btn_testid = btn.get_attribute("data-testid") or ""
                    btn_displayed = btn.is_displayed()
                    btn_enabled = btn.is_enabled()
                    
                    logger.info(f"  Button {i+1}: text='{btn_text}', classes='{btn_classes[:50]}...', aria='{btn_aria}', title='{btn_title}', testid='{btn_testid}', displayed={btn_displayed}, enabled={btn_enabled}")
                except Exception as btn_debug_error:
                    logger.debug(f"Error debugging button {i}: {btn_debug_error}")
        except Exception as debug_error:
            logger.debug(f"Debug button search failed: {debug_error}")
        
        # Try to find button within the person's context first
        for selector in manage_sequences_selectors:
            try:
                if selector.startswith(".//"):
                    # Search relative to the person element
                    button = hiring_manager_element.find_element(By.XPATH, selector)
                elif selector.startswith("//"):
                    # Search the whole page
                    button = driver.find_element(By.XPATH, selector)
                else:
                    # CSS selector
                    button = driver.find_element(By.CSS_SELECTOR, selector)
                
                if button and button.is_displayed():
                    button_text = button.text.strip()
                    button_classes = button.get_attribute("class") or ""
                    logger.info(f"Found button with selector '{selector}': text='{button_text}', classes='{button_classes[:50]}...'")
                    
                    # Verify it's the right button - be more flexible about text matching
                    # Check multiple indicators for sequence/action buttons
                    text_match = any(keyword in button_text.lower() for keyword in ['manage', 'sequence', 'add', 'contact', 'action'])
                    class_match = any(keyword in button_classes.lower() for keyword in ['sequence', 'manage', 'action', 'dropdown', 'menu'])
                    aria_match = any(keyword in (button.get_attribute("aria-label") or "").lower() for keyword in ['manage', 'sequence', 'menu', 'action'])
                    testid_match = any(keyword in (button.get_attribute("data-testid") or "").lower() for keyword in ['sequence', 'manage', 'action'])
                    
                    # Special class indicators from Apollo UI
                    special_class_match = any(cls in button_classes for cls in ['zp_TPOm2', 'zp_jZq6M', 'zp_'])
                    
                    # Position-based matching (buttons in action columns are often empty)
                    is_in_action_area = False
                    try:
                        button_parent = button.find_element(By.XPATH, ".//ancestor::td")
                        parent_classes = button_parent.get_attribute("class") or ""
                        parent_testid = button_parent.get_attribute("data-testid") or ""
                        is_in_action_area = any(keyword in parent_classes.lower() for keyword in ['action', 'menu', 'button']) or \
                                          any(keyword in parent_testid.lower() for keyword in ['action', 'menu', 'button'])
                    except:
                        pass
                    
                    # Accept button if any indicator matches
                    if text_match or class_match or aria_match or testid_match or special_class_match or is_in_action_area:
                        manage_sequences_button = button
                        logger.info(f"✓ Selected button based on: text={text_match}, class={class_match}, aria={aria_match}, testid={testid_match}, special_class={special_class_match}, action_area={is_in_action_area}")
                        logger.info(f"   Button details: text='{button_text}', classes='{button_classes[:50]}...'")
                        break
                        
            except Exception as e:
                logger.debug(f"Selector '{selector}' failed: {e}")
                continue
        
        if not manage_sequences_button:
            logger.warning("⚠️ Could not find 'Manage sequences' button, trying alternative approaches...")
            
            # Alternative approach: look for any action button or dropdown trigger
            alternative_selectors = [
                # Look for any button with action/menu classes
                ".//ancestor::tr//button[contains(@class, 'dropdown')]",
                ".//ancestor::tr//button[contains(@class, 'menu')]",
                ".//ancestor::tr//button[contains(@class, 'action')]",
                ".//ancestor::tr//button[contains(@aria-haspopup, 'true')]",
                
                # Look for buttons with icons or specific patterns
                ".//ancestor::tr//button[.//svg]",
                ".//ancestor::tr//button[.//i[contains(@class, 'icon')]]",
                ".//ancestor::tr//button[@aria-label]",
                
                # Try to find the last button in the row (often the action button)
                "(.//ancestor::tr//button)[last()]",
                
                # Look for any clickable element that might be the action button
                ".//ancestor::tr//*[@role='button']",
                ".//ancestor::tr//div[contains(@class, 'clickable') or contains(@class, 'button')]"
            ]
            
            for alt_selector in alternative_selectors:
                try:
                    alt_button = hiring_manager_element.find_element(By.XPATH, alt_selector)
                    if alt_button and alt_button.is_displayed():
                        alt_text = alt_button.text.strip()
                        alt_classes = alt_button.get_attribute("class") or ""
                        logger.info(f"Found alternative button: text='{alt_text}', classes='{alt_classes[:50]}...'")
                        
                        # Use this as fallback
                        manage_sequences_button = alt_button
                        logger.info(f"✓ Using alternative button as fallback")
                        break
                        
                except Exception as alt_error:
                    logger.debug(f"Alternative selector failed: {alt_selector} - {alt_error}")
                    continue
        
        if not manage_sequences_button:
            logger.error("❌ Could not find 'Manage sequences' button or any alternative action button")
            return False
        
        # Step 2: Click the button (whether it's "Manage sequences" or alternative)
        logger.info("Step 2: Clicking the action button")
        
        try:
            # Scroll to button and ensure it's visible
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", manage_sequences_button)
            time.sleep(1)
            
            # Try multiple click methods for better reliability
            click_successful = False
            click_methods = [
                ("JavaScript click", lambda: driver.execute_script("arguments[0].click();", manage_sequences_button)),
                ("Regular click", lambda: manage_sequences_button.click()),
                ("ActionChains click", lambda: ActionChains(driver).move_to_element(manage_sequences_button).click().perform())
            ]
            
            for method_name, click_method in click_methods:
                try:
                    click_method()
                    logger.info(f"✓ Successfully clicked using {method_name}")
                    click_successful = True
                    break
                except Exception as method_error:
                    logger.debug(f"{method_name} failed: {method_error}")
                    continue
            
            if not click_successful:
                logger.error("❌ All click methods failed")
                return False
            
        except Exception as click_error:
            logger.error(f"❌ Failed to click action button: {click_error}")
            return False
        
        # Step 3: Wait for dropdown and click "Add to sequence"
        logger.info("Step 3: Waiting for dropdown and looking for 'Add to sequence' option")
        time.sleep(3)  # Wait for dropdown to appear
        
        # Look for the "Add to sequence" option in the dropdown (from your 3rd screenshot)
        add_to_sequence_selectors = [
            # Text-based selectors for "Add to sequence"
            "//div[normalize-space(text())='Add to sequence']",
            "//span[normalize-space(text())='Add to sequence']",
            "//button[normalize-space(text())='Add to sequence']",
            "//div[contains(text(), 'Add to sequence')]",
            "//span[contains(text(), 'Add to sequence')]",
            "//button[contains(text(), 'Add to sequence')]",
            # Role-based selectors
            "//*[@role='menuitem' and contains(text(), 'Add to sequence')]",
            "//*[@role='option' and contains(text(), 'Add to sequence')]",
            # Class-based selectors for dropdown options
            "//div[contains(@class, 'option')]//span[contains(text(), 'Add to sequence')]",
            "//div[contains(@class, 'menu')]//div[contains(text(), 'Add to sequence')]",
            "//div[contains(@class, 'dropdown')]//div[contains(text(), 'Add to sequence')]"
        ]
        
        add_to_sequence_option = None
        
        for selector in add_to_sequence_selectors:
            try:
                option = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                if option and option.is_displayed():
                    option_text = option.text.strip()
                    logger.info(f"Found 'Add to sequence' option: '{option_text}'")
                    add_to_sequence_option = option
                    break
                    
            except Exception as e:
                logger.debug(f"Add to sequence selector '{selector}' failed: {e}")
                continue
        
        if not add_to_sequence_option:
            logger.error("❌ Could not find 'Add to sequence' option in dropdown")
            return False
        
        # Click "Add to sequence"
        logger.info("Step 4: Clicking 'Add to sequence' option")
        try:
            driver.execute_script("arguments[0].click();", add_to_sequence_option)
            logger.info("✓ Successfully clicked 'Add to sequence' option")
        except Exception as click_error:
            logger.error(f"❌ Failed to click 'Add to sequence': {click_error}")
            return False
        
        # Step 5: Wait for sequence selection modal and select "Lead Generator"
        logger.info("Step 5: Waiting for sequence selection modal")
        time.sleep(3)  # Wait for modal to appear
        
        # Look for the sequence selection dropdown/modal (from your 4th screenshot)
        sequence_selectors = [
            # Look for "Lead Generator" sequence option
            "//div[contains(text(), 'Lead Generator')]",
            "//span[contains(text(), 'Lead Generator')]",
            "//option[contains(text(), 'Lead Generator')]",
            # Look for sequence selection dropdown
            "//select[contains(@class, 'sequence')]//option[contains(text(), 'Lead Generator')]",
            "//div[contains(@class, 'select')]//div[contains(text(), 'Lead Generator')]",
            # Look in modal for sequence options
            "//div[contains(@class, 'modal')]//div[contains(text(), 'Lead Generator')]",
            "//div[contains(@class, 'dropdown')]//div[contains(text(), 'Lead Generator')]",
            # More generic - find any clickable element with "Lead Generator"
            "//*[contains(text(), 'Lead Generator') and (self::div or self::span or self::option or self::button)]"
        ]
        
        lead_generator_option = None
        
        # First, try to find "Lead Generator" sequence
        for selector in sequence_selectors:
            try:
                option = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                if option and option.is_displayed():
                    option_text = option.text.strip()
                    logger.info(f"Found 'Lead Generator' sequence: '{option_text}'")
                    lead_generator_option = option
                    break
                    
            except Exception as e:
                logger.debug(f"Lead Generator selector '{selector}' failed: {e}")
                continue
        
        if not lead_generator_option:
            logger.warning("⚠️ Could not find 'Lead Generator' sequence, looking for sequence dropdown")
            
            # Try to find sequence dropdown first
            dropdown_selectors = [
                "//select[contains(@class, 'sequence')]",
                "//div[contains(@class, 'select')]",
                "//div[contains(@class, 'dropdown')]",
                "//select",
                "//input[contains(@placeholder, 'Select sequence')]",
                "//input[contains(@placeholder, 'sequence')]"
            ]
            
            for dropdown_sel in dropdown_selectors:
                try:
                    dropdown = driver.find_element(By.XPATH, dropdown_sel)
                    if dropdown and dropdown.is_displayed():
                        logger.info(f"Found sequence dropdown with selector: {dropdown_sel}")
                        
                        # If it's a select element, look for options
                        if dropdown.tag_name == 'select':
                            options = dropdown.find_elements(By.TAG_NAME, 'option')
                            for option in options:
                                if 'lead generator' in option.text.lower():
                                    lead_generator_option = option
                                    logger.info(f"Found Lead Generator in select: {option.text}")
                                    break
                        else:
                            # Try clicking to open dropdown
                            dropdown.click()
                            time.sleep(2)
                            
                            # Look for options again
                            for selector in sequence_selectors:
                                try:
                                    option = driver.find_element(By.XPATH, selector)
                                    if option and option.is_displayed():
                                        lead_generator_option = option
                                        logger.info(f"Found Lead Generator after dropdown click: {option.text}")
                                        break
                                except:
                                    continue
                            
                        if lead_generator_option:
                            break
                            
                except Exception as e:
                    logger.debug(f"Dropdown selector '{dropdown_sel}' failed: {e}")
                    continue
        
        # If still no Lead Generator found, use the first available sequence
        if not lead_generator_option:
            logger.warning("⚠️ Could not find 'Lead Generator', looking for any available sequence")
            
            generic_sequence_selectors = [
                "//option[position()>1]",  # Skip the first option (usually placeholder)
                "//div[contains(@class, 'option') and contains(@class, 'sequence')]",
                "//div[contains(@class, 'sequence-option')]",
                "//select//option[position()=2]"  # Second option
            ]
            
            for selector in generic_sequence_selectors:
                try:
                    option = driver.find_element(By.XPATH, selector)
                    if option and option.is_displayed():
                        option_text = option.text.strip()
                        if option_text and option_text.lower() not in ['select sequence', 'choose sequence', '']:
                            lead_generator_option = option
                            logger.info(f"Using available sequence: '{option_text}'")
                            break
                except:
                    continue
        
        if not lead_generator_option:
            logger.error("❌ Could not find any sequence to select")
            return False
        
        # Click the sequence option
        logger.info("Step 6: Selecting sequence")
        try:
            driver.execute_script("arguments[0].click();", lead_generator_option)
            sequence_name = lead_generator_option.text.strip()
            logger.info(f"✓ Selected sequence: '{sequence_name}'")
        except Exception as click_error:
            logger.error(f"❌ Failed to select sequence: {click_error}")
            return False
        
        # Step 7: Click Save button
        logger.info("Step 7: Looking for and clicking Save button")
        time.sleep(2)  # Wait for selection to process
        
        save_button_selectors = [
            "//button[normalize-space(text())='Save']",
            "//button[contains(text(), 'Save')]",
            "//input[@type='submit' and @value='Save']",
            "//button[@type='submit']",
            "//div[contains(@class, 'modal')]//button[contains(text(), 'Save')]",
            "//div[contains(@class, 'dialog')]//button[contains(text(), 'Save')]",
            "//*[contains(text(), 'Save') and (self::button or self::input)]"
        ]
        
        save_button = None
        
        for selector in save_button_selectors:
            try:
                button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                if button and button.is_displayed():
                    button_text = button.text.strip() or button.get_attribute('value') or 'Save'
                    logger.info(f"Found Save button: '{button_text}'")
                    save_button = button
                    break
                    
            except Exception as e:
                logger.debug(f"Save button selector '{selector}' failed: {e}")
                continue
        
        if not save_button:
            logger.error("❌ Could not find Save button")
            return False
        
        # Click Save button
        try:
            driver.execute_script("arguments[0].click();", save_button)
            logger.info("✓ Successfully clicked Save button")
        except Exception as click_error:
            logger.error(f"❌ Failed to click Save button: {click_error}")
            return False
        
        # Wait for save operation to complete
        logger.info("Step 8: Waiting for save operation to complete")
        time.sleep(3)
        
        logger.info(f"✅ Successfully added {hiring_manager} to sequence!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error in add_to_sequence for {hiring_manager}: {e}")
        return False

def find_correct_sequence_button(driver, hiring_manager_element):
    """Helper function to find the correct 'Add to sequence' button and avoid search triggers"""
    try:
        # Look for parent container using classes from screenshot
        parent_container = hiring_manager_element.find_element(By.XPATH, "./ancestor::div[contains(@class, 'zp_TPOm2') or contains(@class, 'zp_jZq6M') or contains(@class, 'zp_') or contains(@class, 'result') or contains(@class, 'person')]")
        logger.debug("Found parent container for person element")
    except:
        parent_container = driver  # Fall back to searching the whole page
        logger.debug("Using whole page as container")
    
    # More targeted selectors that look for buttons within the person's row/card
    sequence_button_selectors = [
        # Look specifically in table cells or person cards for sequence buttons
        ".//td//button[.//span[normalize-space(text())='Add to sequence']]",
        ".//td//button[.//span[normalize-space(text())='Manage sequences']]",
        ".//div[contains(@class, 'zp_')]//button[.//span[contains(text(), 'sequence')] and not(contains(text(), 'search'))]",
        # Look for buttons that are siblings to the person name
        ".//button[.//span[normalize-space(text())='Add to sequence'] and ancestor::tr]",
        ".//button[.//span[normalize-space(text())='Manage sequences'] and ancestor::tr]",
        # Look in action columns or button groups
        ".//div[contains(@class, 'action') or contains(@class, 'button')]//button[.//span[contains(text(), 'sequence')]]"
    ]
    
    for selector in sequence_button_selectors:
        try:
            button = parent_container.find_element(By.XPATH, selector)
            if button and button.is_displayed():
                # Additional validation
                button_text = button.text.strip()
                button_classes = button.get_attribute("class") or ""
                
                # Make sure it's not a search-related button
                if not any(search_term in button_classes.lower() for search_term in ['search', 'filter', 'quick']):
                    if not any(search_term in button_text.lower() for search_term in ['search', 'filter', 'quick']):
                        logger.info(f"Found valid sequence button: {button_text}")
                        return button
        except Exception as e:
            logger.debug(f"Sequence button selector failed: {selector} - {e}")
            continue
    
    return None

def clear_search_filters(driver):
    """Clear search filters to prepare for next search"""
    try:
        # Clear search input
        search_input_selectors = [
            "input[data-cy='search-input']",
            "input[placeholder*='Search']",
            "//input[@placeholder='Search']"
        ]
        
        for selector in search_input_selectors:
            try:
                if selector.startswith("//"):
                    search_input = driver.find_element(By.XPATH, selector)
                else:
                    search_input = driver.find_element(By.CSS_SELECTOR, selector)
                search_input.clear()
                break
            except:
                continue
        
        # Clear company filter
        clear_selectors = [
            "button[data-cy='clear-filters']",
            "button[aria-label*='clear']",
            "//button[contains(text(), 'Clear')]",
            "//i[contains(@class, 'close')]"
        ]
        
        for selector in clear_selectors:
            try:
                if selector.startswith("//"):
                    clear_button = driver.find_element(By.XPATH, selector)
                else:
                    clear_button = driver.find_element(By.CSS_SELECTOR, selector)
                clear_button.click()
                break
            except:
                continue
        
        time.sleep(1)
        logger.debug("Cleared search filters")
        
    except Exception as e:
        logger.warning(f"Could not clear search filters: {e}")

async def process_recruiter_batch(driver, recruiters_batch):
    """Process a batch of recruiters"""
    success_count = 0
    failed_count = 0
    
    logger.info(f"Processing batch of {len(recruiters_batch)} recruiters")
    
    for i, recruiter in enumerate(recruiters_batch):
        try:
            logger.info(f"Processing recruiter {i+1}/{len(recruiters_batch)}: {recruiter['name']} ({recruiter['company_domain']})")
            
            # Search for the recruiter
            hiring_manager_element = search_recruiter(
                driver, 
                recruiter['name'], 
                recruiter['company_domain']
            )
            
            if not hiring_manager_element:
                logger.warning(f"FAILED: Could not find {recruiter['name']} in Apollo search results")
                failed_count += 1
                continue
            
            # Try to add to sequence
            sequence_success = add_to_sequence(
                driver, 
                hiring_manager_element, 
                recruiter['name'], 
                recruiter['company_domain']
            )
            
            if sequence_success:
                logger.info(f"SUCCESS: {recruiter['name']} - Add to sequence button clicked successfully")
                success_count += 1
            else:
                logger.warning(f"FAILED: {recruiter['name']} - Could not click Add to sequence button")
                failed_count += 1
            
            # Clear filters for next search
            clear_search_filters(driver)
            
            # Wait between processing to avoid rate limits
            if i < len(recruiters_batch) - 1:  # Don't wait after the last one
                logger.info(f"Waiting {SEQUENCE_DELAY} seconds before next recruiter...")
                time.sleep(SEQUENCE_DELAY)
                
        except Exception as e:
            logger.error(f"ERROR: Exception processing recruiter {recruiter['name']}: {e}")
            failed_count += 1
    
    logger.info(f"Batch completed: {success_count} successful, {failed_count} failed")
    return success_count, failed_count

async def main():
    """Main function to run Apollo automation with Prisma ORM"""
    logger.info("Starting Apollo.io automation with Prisma ORM")

    # Setup database connection
    if not await setup_database():
        logger.error("Database setup failed, exiting")
        return

    # Setup undetected Chrome driver (same as working test)
    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")

    # This driver is specifically designed to bypass Cloudflare
    driver = uc.Chrome(options=options)

    try:
        # Login to Apollo
        login_success = login(driver)
        if not login_success:
            logger.error("Login failed, exiting automation")
            return

        # Fetch pending recruiters
        pending_recruiters = await fetch_pending_recruiters()

        if not pending_recruiters:
            logger.info("No pending recruiters found")
            return

        logger.info(f"Found {len(pending_recruiters)} recruiters to process")

        # Process in batches
        total_success = 0
        total_failed = 0

        for i in range(0, len(pending_recruiters), BATCH_SIZE):
            batch = pending_recruiters[i:i+BATCH_SIZE]
            batch_num = (i // BATCH_SIZE) + 1
            total_batches = (len(pending_recruiters) + BATCH_SIZE - 1) // BATCH_SIZE

            logger.info(f"Processing batch {batch_num}/{total_batches}")

            # Manual confirmation for each batch
            print(f"\nBatch {batch_num}/{total_batches} contains {len(batch)} recruiters:")
            for j, recruiter in enumerate(batch):
                print(f"  {j+1}. {recruiter['name']} - {recruiter['company_name']} ({recruiter['job_count']} jobs)")

            proceed = input(f"\nProceed with batch {batch_num}? (y/n): ").lower().strip()
            if proceed != 'y':
                logger.info(f"Skipping batch {batch_num} by user request")
                continue

            # Process the batch
            success, failed = await process_recruiter_batch(driver, batch)
            total_success += success
            total_failed += failed

            # Wait between batches (except for the last one)
            if i + BATCH_SIZE < len(pending_recruiters):
                logger.info(f"Waiting {SEQUENCE_DELAY * 2} seconds between batches...")
                time.sleep(SEQUENCE_DELAY * 2)

        logger.info(f"Apollo automation completed: {total_success} successful, {total_failed} failed")

    except Exception as e:
        logger.error(f"Apollo automation error: {e}")

    finally:
        # Close browser
        driver.quit()

        # Disconnect from database
        await disconnect_database()

        logger.info("Apollo automation finished")

if __name__ == "__main__":
    asyncio.run(main())
