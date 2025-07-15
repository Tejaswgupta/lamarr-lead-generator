import asyncio
import json
import os
import platform
import time
import traceback

from dotenv import load_dotenv
from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from supabase import Client, create_client
from webdriver_manager.chrome import ChromeDriverManager

# Load environment variables
load_dotenv(override=True)

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
LINKEDIN_USERNAME = os.getenv("LINKEDIN_USERNAME")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD")

# Validate required environment variables
if not all([SUPABASE_URL, SUPABASE_KEY, LINKEDIN_USERNAME, LINKEDIN_PASSWORD]):
    raise ValueError("Missing required environment variables in .env file")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Detect operating system
IS_MACOS = platform.system() == "Darwin"

# macOS Chrome profile configuration
if IS_MACOS:
    CHROME_USER_DATA_DIR = "/Users/tejasw/Library/Application Support/Google/Chrome/"
    DEFAULT_PROFILE = "Profile 9"
    # Check if Chrome is installed in standard macOS locations
    CHROME_BINARY_PATHS = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
else:
    # Fallback for other systems
    CHROME_USER_DATA_DIR = None
    DEFAULT_PROFILE = "Default"
    CHROME_BINARY_PATHS = []


def find_chrome_binary():
    """Find Chrome binary on macOS"""
    if not IS_MACOS:
        return None

    return CHROME_BINARY_PATHS


def setup_driver():
    """Setup Chrome driver with macOS-optimized configuration"""
    options = Options()

    # macOS-specific Chrome options
    if IS_MACOS:
        # Use macOS Chrome profile path
        if os.path.exists(CHROME_USER_DATA_DIR):
            print(os.listdir(CHROME_USER_DATA_DIR))
            options.add_argument(f"--user-data-dir={CHROME_USER_DATA_DIR}")
            options.add_argument(f"--profile-directory={DEFAULT_PROFILE}")
            options.add_argument("--remote-debugging-port=9222")

        # Find Chrome binary
        chrome_binary = find_chrome_binary()
        if chrome_binary:
            options.binary_location = chrome_binary
        #     print(f"✅ Using Chrome binary: {chrome_binary}")

        # macOS-specific optimizations
        # options.add_argument("--disable-gpu")  # Recommended for macOS
        # options.add_argument("--no-sandbox")  # Required for macOS in some cases

    # Set up Chrome service with automatic driver management
    try:
        # Use ChromeDriverManager to automatically handle driver installation
        service = Service(ChromeDriverManager().install())

        # Create driver instance
        driver = webdriver.Chrome(service=service, options=options)

        print("✅ Chrome driver setup successful")
        return driver

    except Exception as e:
        print(f"❌ Failed to launch Chrome: {e}")
        print("💡 Troubleshooting tips for macOS:")
        print("   - Ensure Google Chrome is installed in /Applications/")
        print("   - Try running: brew install --cask google-chrome")
        print(
            "   - Check Chrome permissions in System Preferences > Security & Privacy"
        )
        print("   - Close all Chrome instances before running the script")
        return None


def login_to_linkedin(driver):
    """Login to LinkedIn account"""
    driver.get("https://www.linkedin.com/uas/login")

    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "username"))
        )

        username = driver.find_element(By.ID, "username")
        username.send_keys(LINKEDIN_USERNAME)

        password = driver.find_element(By.ID, "password")
        password.send_keys(LINKEDIN_PASSWORD)

        driver.find_element(By.XPATH, "//button[@type='submit']").click()
        time.sleep(3)

        # Check for CAPTCHA
        check_for_captcha(driver)
    except Exception as e:
        print(f"Error during LinkedIn login: {e}")
        if "username" in str(e).lower():
            print("Already logged in, continuing...")


def check_for_captcha(driver):
    """Check and handle CAPTCHA if present"""
    try:
        captcha_element = driver.find_element(By.XPATH, "/html/body/div/main/h1")
        if captcha_element:
            print(
                "CAPTCHA detected. Please solve the CAPTCHA and press Enter to continue..."
            )
            input("Press Enter after solving the CAPTCHA...")
    except NoSuchElementException:
        pass


def extract_name(profile_text):
    """Extract clean name from profile text"""
    name = profile_text.replace("View ", "").strip()
    suffixes = ["'s profile", "'s verified profile", "' verified profile", "' profile"]
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    return name.strip()


def safe_find_element(driver, by, selector):
    """Safely find an element without raising exceptions"""
    try:
        return driver.find_element(by, selector)
    except Exception:
        return None


def scroll_to_parent_ul(driver, li_class_name):
    """Scroll to load all list items in a parent container"""
    try:
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, li_class_name)))

        items = driver.find_elements(By.CLASS_NAME, li_class_name)
        prev_count = len(items)

        max_attempts = 10
        attempts = 0

        while attempts < max_attempts:
            if items:
                last_item = items[-1]
                driver.execute_script("arguments[0].scrollIntoView(true);", last_item)
            time.sleep(2)

            items = driver.find_elements(By.CLASS_NAME, li_class_name)
            current_count = len(items)
            print(f"Found {current_count} items after scrolling")

            if current_count == prev_count:
                attempts += 1
            else:
                attempts = 0
            prev_count = current_count

        return items
    except Exception as e:
        print(f"Error scrolling to parent ul: {e}")
        return []


def extract_company_details(driver):
    """Extract company details from LinkedIn company page"""
    try:
        wait = WebDriverWait(driver, 10)
        section = wait.until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    "//section[@class='artdeco-card org-page-details-module__card-spacing artdeco-card org-about-module__margin-bottom']",
                )
            )
        )
        company_details = {}
        dt_elements = section.find_elements(By.XPATH, ".//dt")
        for dt in dt_elements:
            dt_text = dt.text.strip()
            dd = dt.find_element(By.XPATH, "./following-sibling::dd[1]")
            dd_text = dd.text.strip()
            company_details[dt_text] = dd_text
        return json.dumps(company_details, indent=4)
    except Exception as e:
        print(f"Error extracting company details: {e}")
        return json.dumps({})


async def insert_data(
    company_name,
    company_location,
    company_url,
    title,
    role_meta,
    hiring_manager_name,
    hiring_manager_linkedin_url,
    job_details,
    job_id,
    company_domain,
    company_details,
):
    """Insert job and company data into Supabase"""
    try:
        company_url = company_url.replace("/about", "").replace("/life", "")
        company_response = (
            supabase.table("companies")
            .select("id")
            .eq("linkedin_url", company_url)
            .execute()
        )
        company_id = company_response.data[0]["id"] if company_response.data else None

        if not company_id and company_domain:
            domain_response = (
                supabase.table("companies")
                .select("id")
                .eq("company_domain", company_domain)
                .execute()
            )
            company_id = domain_response.data[0]["id"] if domain_response.data else None

        if not company_id:
            company_response = (
                supabase.table("companies")
                .insert(
                    {
                        "name": company_name,
                        "linkedin_url": company_url,
                        "location": company_location,
                        "company_domain": company_domain,
                        "metadata": company_details,
                    }
                )
                .execute()
            )
            company_id = company_response.data[0]["id"]
        else:
            update_data = {}
            if company_domain:
                update_data["company_domain"] = company_domain
            if company_details and company_details != "{}":
                update_data["metadata"] = company_details
            if update_data:
                supabase.table("companies").update(update_data).eq(
                    "id", company_id
                ).execute()

        recruiter_id = None
        if hiring_manager_name and hiring_manager_linkedin_url:
            try:
                recruiter_response = (
                    supabase.table("recruiters")
                    .select("id")
                    .eq("linkedin_url", hiring_manager_linkedin_url)
                    .execute()
                )
                if recruiter_response.data:
                    recruiter_id = recruiter_response.data[0]["id"]
                    supabase.table("recruiters").update(
                        {"name": hiring_manager_name, "company_domain": company_domain}
                    ).eq("id", recruiter_id).execute()
                else:
                    recruiter_response = (
                        supabase.table("recruiters")
                        .insert(
                            {
                                "name": hiring_manager_name,
                                "linkedin_url": hiring_manager_linkedin_url,
                                "company_domain": company_domain,
                            }
                        )
                        .execute()
                    )
                    recruiter_id = recruiter_response.data[0]["id"]
            except Exception as e:
                print(f"Error handling recruiter: {str(e)}")
                try:
                    recruiter_response = (
                        supabase.table("recruiters")
                        .select("id")
                        .eq("linkedin_url", hiring_manager_linkedin_url)
                        .execute()
                    )
                    if recruiter_response.data:
                        recruiter_id = recruiter_response.data[0]["id"]
                except:
                    pass

        # Insert job data
        job_data = {
            "company_id": company_id,
            "title": title,
            "description": job_details,
            "role_metadata": role_meta,
            "id": int(job_id),
        }

        if recruiter_id:
            job_data["recruiter_id"] = recruiter_id

        supabase.table("linkedin_jobs").insert(job_data).execute()

        return True
    except Exception as e:
        print(f"Error inserting data: {str(e)}")
        return False


async def process_job_data(driver, job_id):
    """Process job data from LinkedIn job posting"""
    # Check if job already exists
    job_response = (
        supabase.table("linkedin_jobs").select("id").eq("id", int(job_id)).execute()
    )
    exists = len(job_response.data) > 0
    if exists:
        print(f"Job {job_id} already exists in database, skipping...")
        return None, None, None

    # Extract job title
    title_el = safe_find_element(
        driver, By.CLASS_NAME, "job-details-jobs-unified-top-card__job-title"
    )
    title = title_el.text if title_el else None

    # Extract company information
    try:
        company_link = driver.find_element(
            By.XPATH, "//a[starts-with(@href, 'https://www.linkedin.com/company/')]"
        )
        company_name = company_link.text
        company_url = company_link.get_attribute("href")
    except NoSuchElementException:
        print("Could not find company link")
        return None, None, None

    # Check if company exists in database
    company_response = (
        supabase.table("companies")
        .select("id, company_domain, metadata")
        .eq("linkedin_url", company_url.replace("/life", ""))
        .execute()
    )
    company_exists = len(company_response.data) > 0
    company_domain = None
    company_details = json.dumps({})

    # Extract role metadata
    try:
        role_metadata = driver.execute_script("""
            return document.querySelector('.job-details-jobs-unified-top-card__primary-description-container')
                    .getElementsByTagName('div')[0].innerText;
        """)
        metadata_parts = role_metadata.split("·")
        company_location = (
            metadata_parts[0].strip() if len(metadata_parts) > 0 else None
        )
        posted_at = metadata_parts[1].strip() if len(metadata_parts) > 1 else None
        applicants = metadata_parts[2].strip() if len(metadata_parts) > 2 else None
    except:
        print("Could not find company location")
        company_location = None
        posted_at = None
        applicants = None

    # Get company domain if company doesn't exist
    if not company_exists:
        company_url = company_url.replace("life", "about")
        driver.execute_script("window.open('');")
        driver.switch_to.window(driver.window_handles[1])
        driver.get(company_url)
        time.sleep(1)

        try:
            domain_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(
                    (
                        By.XPATH,
                        "//a[@target='_blank' and contains(@class, 'link-without-visited-state')]",
                    )
                )
            )
            company_domain = domain_element.get_attribute("href")
            if company_domain:
                domain_response = (
                    supabase.table("companies")
                    .select("id, metadata")
                    .eq("company_domain", company_domain)
                    .execute()
                )
                if len(domain_response.data) > 0:
                    company_details = domain_response.data[0]["metadata"]
                    company_exists = True
                else:
                    company_details = extract_company_details(driver)
            else:
                company_details = extract_company_details(driver)
        except (NoSuchElementException, TimeoutException) as e:
            print(f"Error finding element or waiting: {e}")
            company_domain = None
            company_details = json.dumps({})
        finally:
            driver.close()
            driver.switch_to.window(driver.window_handles[0])
    else:
        if company_response.data[0]["company_domain"]:
            company_domain = company_response.data[0]["company_domain"]
        if company_response.data[0]["metadata"]:
            company_details = company_response.data[0]["metadata"]

    # Set role metadata
    role_meta = {"posted_at": posted_at, "applicants": applicants}

    # Extract hiring manager information
    hiring_manager_element = safe_find_element(
        driver, By.CLASS_NAME, "hirer-card__hirer-information"
    )
    if hiring_manager_element:
        try:
            hiring_manager = hiring_manager_element.find_element(By.TAG_NAME, "a")
            hiring_manager_name = extract_name(
                hiring_manager.get_attribute("aria-label")
            )
            hiring_manager_linkedin_url = hiring_manager.get_attribute("href")
        except NoSuchElementException:
            hiring_manager_name = None
            hiring_manager_linkedin_url = None
    else:
        hiring_manager_name = None
        hiring_manager_linkedin_url = None

    # Extract job details
    job_details_element = safe_find_element(driver, By.ID, "job-details")
    job_details = job_details_element.text if job_details_element else ""

    # Insert data into Supabase
    await insert_data(
        company_name,
        company_location,
        company_url,
        title,
        role_meta,
        hiring_manager_name,
        hiring_manager_linkedin_url,
        job_details,
        job_id,
        company_domain,
        company_details,
    )

    return hiring_manager_name, hiring_manager_linkedin_url, company_domain


def interact_with_apollo(driver, linkedin_url):
    try:
        print("[INFO] Opening new tab...")
        driver.execute_script("window.open('');")
        driver.switch_to.window(driver.window_handles[1])
        driver.get(linkedin_url)
        time.sleep(10)  # Wait for Apollo sidebar to auto-load

        # Step 1: Try finding 'Add to Sequence' in normal DOM
        print("[STEP 1] Trying normal DOM search...")
        try:
            divs = driver.find_elements(By.CSS_SELECTOR, "div.x_WOCiW")
            print(f"[DEBUG] Found {len(divs)} elements with class 'x_WOCiW'")
            for div in divs:
                if div.text.strip() == "Add to Sequence":
                    driver.execute_script("arguments[0].scrollIntoView(true);", div)
                    time.sleep(1)
                    driver.execute_script("arguments[0].click();", div)
                    print("[SUCCESS] Clicked 'Add to Sequence' using normal DOM")
                    break
            else:
                raise Exception("Not found in normal DOM")
        except Exception as e:
            print(f"[WARN] Normal DOM failed: {e}")

            # Step 2: Try iframe search
            print("[STEP 2] Trying iframe...")
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            print(f"[DEBUG] Found {len(iframes)} iframes")
            clicked = False

            for idx, iframe in enumerate(iframes):
                try:
                    driver.switch_to.frame(iframe)
                    iframe_divs = driver.find_elements(By.CSS_SELECTOR, "div.x_WOCiW")
                    print(
                        f"[DEBUG] Inside iframe {idx}, found {len(iframe_divs)} elements"
                    )

                    for div in iframe_divs:
                        if div.text.strip() == "Add to Sequence":
                            driver.execute_script(
                                "arguments[0].scrollIntoView(true);", div
                            )
                            time.sleep(1)
                            driver.execute_script("arguments[0].click();", div)
                            print("[SUCCESS] Clicked 'Add to Sequence' inside iframe")
                            clicked = True
                            break

                    driver.switch_to.default_content()
                    if clicked:
                        time.sleep(10)
                        break
                except Exception as iframe_err:
                    print(f"[WARN] Failed in iframe {idx}: {iframe_err}")
                    driver.switch_to.default_content()

            if not clicked:
                print("[ERROR] Could not find 'Add to Sequence' button in any iframe.")
                return False

        # Step 3: Handle modal after click
        print("[INFO] Waiting for 'Choose a Sequence' modal to appear...")
        driver.switch_to.default_content()
        try:
            modal_header = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//div[contains(text(), 'Choose a Sequence')]")
                )
            )
            print("[SUCCESS] 'Choose a Sequence' modal is visible")

            # Click the "Next" or "Continue" button
            next_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable(
                    (
                        By.XPATH,
                        "//button[contains(., 'Next') or contains(., 'Continue')]",
                    )
                )
            )
            driver.execute_script("arguments[0].scrollIntoView(true);", next_btn)
            next_btn.click()
            print("[SUCCESS] Clicked 'Next' to proceed in modal")

            # Optional: click final confirm button if it exists
            try:
                confirm_btn = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable(
                        (
                            By.XPATH,
                            "//button[contains(., 'Add to Sequence') or contains(., 'Finish')]",
                        )
                    )
                )
                confirm_btn.click()
                print("[SUCCESS] Final confirmation clicked")
            except TimeoutException:
                print("[INFO] No final confirm button found — may not be required")

            return True  # Successfully completed the Apollo interaction

        except TimeoutException:
            print("[ERROR] 'Choose a Sequence' modal did not appear")
            return False

    except Exception as e:
        print(f"[CRITICAL ERROR] Apollo interaction failed: {e}")
        driver.save_screenshot("apollo_click_error.png")
        return False
    finally:
        # Always close the tab and switch back to the original window
        try:
            if len(driver.window_handles) > 1:
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
        except Exception as e:
            print(f"[WARN] Error closing Apollo tab: {e}")


async def scrape_and_process_jobs(driver, start_url, max_items=100):
    """Scrape and process jobs from LinkedIn search results"""
    item_count = 0

    try:
        while item_count < max_items:
            url = f"{start_url}&start={item_count}"
            driver.get(url)
            time.sleep(2)

            try:
                # Find job listings
                list_items = scroll_to_parent_ul(driver, "job-card-container")
                if not list_items or len(list_items) == 0:
                    print("No job listings found on page")
                    break

                print(f"Found {len(list_items)} job listings on current page")

                # Process each job listing
                for index, item in enumerate(list_items):
                    for attempt in range(3):
                        try:
                            # Click on job listing to view details
                            item.click()
                            time.sleep(2)

                            # Extract job ID
                            job_id = item.get_attribute("data-job-id")
                            print(f"Processing job ID: {job_id}")

                            # Process job data
                            (
                                hiring_manager_name,
                                hiring_manager_linkedin_url,
                                company_domain,
                            ) = await process_job_data(driver, job_id)

                            # Interact with Apollo if hiring manager info is available
                            if hiring_manager_name and hiring_manager_linkedin_url:
                                print(
                                    f"Found hiring manager: {hiring_manager_name}, attempting to add to Apollo sequence"
                                )
                                success = interact_with_apollo(
                                    driver, hiring_manager_linkedin_url
                                )
                                if success:
                                    print(
                                        f"Successfully added {hiring_manager_name} to Apollo sequence"
                                    )
                                else:
                                    print(
                                        f"Failed to add {hiring_manager_name} to Apollo sequence"
                                    )

                            break  # Break out of retry loop if successful

                        except StaleElementReferenceException:
                            if attempt == 2:  # Last attempt
                                print(f"Failed to process job after 3 attempts")
                            else:
                                print(
                                    f"StaleElementReferenceException occurred, retrying (attempt {attempt + 1})"
                                )
                                time.sleep(1)
                        except Exception as e:
                            print(f"Error processing job listing: {str(e)}")
                            break

                # Move to next page of results
                print(f"Processed {len(list_items)} job listings, moving to next page")
                item_count += 25

            except Exception as page_error:
                print(f"Error processing page: {str(page_error)}")
                item_count += 25  # Move to next page despite error

    except Exception as e:
        print(f"Error in scrape_and_process_jobs: {str(e)}")
        traceback.print_exc()


def check_macos_requirements():
    """Check macOS-specific requirements"""
    if not IS_MACOS:
        print(
            "⚠️  This script is optimized for macOS but will attempt to run on your system"
        )
        return True

    print("🍎 Running on macOS - performing system checks...")

    # Check if Chrome is installed
    chrome_binary = find_chrome_binary()
    if not chrome_binary:
        print("❌ Google Chrome not found in standard locations")
        print("💡 Install Chrome: brew install --cask google-chrome")
        print("   Or download from: https://www.google.com/chrome/")
        return False

    # Check Chrome profile directory
    if not os.path.exists(CHROME_USER_DATA_DIR):
        print("⚠️  Chrome user data directory not found")
        print(f"   Expected: {CHROME_USER_DATA_DIR}")
        print("   This might be normal for first-time Chrome users")
    else:
        print(f"✅ Chrome profile directory found: {CHROME_USER_DATA_DIR}")

    # Check for Chrome permissions (common macOS issue)
    try:
        # Try to read Chrome preferences to check permissions
        prefs_path = os.path.join(CHROME_USER_DATA_DIR, DEFAULT_PROFILE, "Preferences")
        if os.path.exists(prefs_path):
            with open(prefs_path, "r") as f:
                f.read(100)  # Just read a small portion to test permissions
            print("✅ Chrome profile permissions OK")
    except (PermissionError, FileNotFoundError):
        print("⚠️  Chrome profile access issues detected")
        print(
            "   You may need to grant permissions in System Preferences > Security & Privacy"
        )

    print("✅ macOS requirements check completed")
    return True


async def main():
    """Main function to run the script"""
    print("🚀 Starting LinkedIn Lead Generator for macOS")
    print("=" * 50)

    # Check macOS requirements
    if not check_macos_requirements():
        print("❌ System requirements not met. Please resolve the issues above.")
        return

    driver = None
    try:
        print("\n🔧 Setting up Chrome driver...")
        driver = setup_driver()

        if not driver:
            print("❌ Failed to setup Chrome driver. Exiting...")
            return

        print("\n🔐 Logging into LinkedIn...")
        login_to_linkedin(driver)

        # List of job search URLs to process
        urls = [
            "https://www.linkedin.com/jobs/search/?currentJobId=3843718022&f_TPR=r86400&geoId=92000000&keywords=generative%20ai&location=Worldwide&origin=JOB_SEARCH_PAGE_SEARCH_BUTTON&refresh=true&sortBy=DD",
            # Add more search URLs as needed
        ]

        # Process each URL
        for i, url in enumerate(urls, 1):
            print(f"\n📋 Processing job search URL {i}/{len(urls)}")
            print(f"🔗 {url}")
            await scrape_and_process_jobs(driver, url, max_items=100)

        print("\n✅ Script completed successfully!")

    except KeyboardInterrupt:
        print("\n⏹️  Script interrupted by user")
    except Exception as e:
        print(f"\n❌ Error in main function: {str(e)}")
        if IS_MACOS:
            print("\n🩺 macOS Troubleshooting:")
            print("   - Try closing all Chrome windows and restart the script")
            print(
                "   - Check System Preferences > Security & Privacy for Chrome permissions"
            )
            print("   - Ensure Chrome is updated to the latest version")
            print("   - Try running: brew upgrade google-chrome")
        traceback.print_exc()
    finally:
        if driver:
            try:
                driver.quit()
                print("🔒 Chrome driver closed successfully")
            except Exception as e:
                print(f"⚠️  Warning: Error closing driver: {e}")


if __name__ == "__main__":
    asyncio.run(main())
