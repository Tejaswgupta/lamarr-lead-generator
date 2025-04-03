# %%
import asyncio
import concurrent.futures
import csv
import json
import os
import shutil
import tempfile
import time
import traceback

import asyncpg
# import chromedriver_binary
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
from supabase import Client, create_client
from webdriver_manager.chrome import ChromeDriverManager

# Load environment variables from .env file
load_dotenv(override=True)

# Replace the PostgreSQL connection with Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError(
        "Please set SUPABASE_URL and SUPABASE_KEY environment variables in .env file")

print(SUPABASE_URL, SUPABASE_KEY)
print(f"URL: {SUPABASE_URL}")
# Print partial key for security
print(f"Key: {SUPABASE_KEY[:5]}...{SUPABASE_KEY[-5:]}")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# %%

# %%
# 8k2AuYHhAyHMwfwj


# %%
# item_count = int(input("Enter page index to start from (multiple of 25): "))

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
        return None


# %%


def extract_name(profile_text):
    # Remove 'View' and all variations of profile suffixes
    name = profile_text.replace("View ", "").strip()
    
    # Remove common profile suffixes
    suffixes = ["'s profile", "'s verified profile", "' verified profile", "' profile"]
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    
    return name.strip()


async def insert_data(pool, company_name, company_location, company_url, title, role_meta, hiring_manager_name, hiring_manager_linkedin_url, job_details, job_id, company_domain, company_details):

    company_url = company_url.replace("/about", "")
    # First check if company exists by LinkedIn URL
    company_response = supabase.table('companies').select(
        'id').eq('linkedin_url', company_url).execute()
    company_id = company_response.data[0]['id'] if company_response.data else None

    # If not found by LinkedIn URL and we have a domain, check by domain
    if not company_id and company_domain:
        domain_response = supabase.table('companies').select(
            'id').eq('company_domain', company_domain).execute()
        company_id = domain_response.data[0]['id'] if domain_response.data else None

    if not company_id:
        # Insert new company
        company_response = supabase.table('companies').insert({
            'name': company_name,
            'linkedin_url': company_url,
            'location': company_location,
            'company_domain': company_domain,
            'metadata': company_details
        }).execute()
        company_id = company_response.data[0]['id']
    else:
        # Update existing company if we have new information
        update_data = {}
        if company_domain:
            update_data['company_domain'] = company_domain
        if company_details and company_details != '{}':
            update_data['metadata'] = company_details
        
        # Only update if we have new data
        if update_data:
            supabase.table('companies').update(update_data).eq('id', company_id).execute()

    recruiter_id = None
    if hiring_manager_name and hiring_manager_linkedin_url:
        # First check if recruiter already exists
        try:
            recruiter_response = supabase.table('recruiters').select(
                'id').eq('linkedin_url', hiring_manager_linkedin_url).execute()
            
            if recruiter_response.data:
                # Recruiter already exists, just get the ID
                recruiter_id = recruiter_response.data[0]['id']
                
                # Update the recruiter with any new information
                supabase.table('recruiters').update({
                    'name': hiring_manager_name,
                    'company_domain': company_domain
                }).eq('id', recruiter_id).execute()
            else:
                # Insert new recruiter
                recruiter_response = supabase.table('recruiters').insert({
                    'name': hiring_manager_name,
                    'linkedin_url': hiring_manager_linkedin_url,
                    'company_domain': company_domain
                }).execute()
                recruiter_id = recruiter_response.data[0]['id']
        except Exception as e:
            print(f"Error handling recruiter: {str(e)}")
            # If there's an error, try to get the recruiter ID directly
            try:
                recruiter_response = supabase.table('recruiters').select(
                    'id').eq('linkedin_url', hiring_manager_linkedin_url).execute()
                if recruiter_response.data:
                    recruiter_id = recruiter_response.data[0]['id']
            except:
                pass

    # Insert job data
    supabase.table('linkedin_jobs').insert({
        'company_id': company_id,
        'title': title,
        'description': job_details,
        'role_metadata': role_meta,
        'id': int(job_id),
        'recruiter_id': recruiter_id
    }).execute()


def extract_company_details(driver):
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

        return company_details_json

    except Exception as e:
        print(f"Error extracting company details: {e}")
        return json.dumps({})


async def write_data(driver, job_id):
    # Check if job exists
    job_response = supabase.table('linkedin_jobs').select(
        'id').eq('id', int(job_id)).execute()
    exists = len(job_response.data) > 0
    print(f'Job ID {job_id} exists: {exists}')

    if exists:
        return

    title_el = safe_find_element(
        driver, By.CLASS_NAME, 'job-details-jobs-unified-top-card__job-title')
    title = title_el.text if title_el else None
    print(f"Title: {title}")

    try:
        company_link = driver.find_element(
            By.XPATH, "//a[starts-with(@href, 'https://www.linkedin.com/company/')]")
        company_name = company_link.text
        company_url = company_link.get_attribute('href')
    except NoSuchElementException:
        print("Could not find company link")
        return

    # Check if company already exists by LinkedIn URL
    company_response = supabase.table('companies').select(
        'id, company_domain, metadata').eq('linkedin_url', company_url.replace("/life", "")).execute()

    print(f"Company response: {company_response}")
    company_exists = len(company_response.data) > 0
    
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
        print("Could not find company location")
        company_location = None

    print(f"Company: {company_name}")
    print(f"Location: {company_location}")
    print(f"Company LinkedIn URL: {company_url}")
    print(f"Company exists: {company_exists}")

    # Only scrape company details if company doesn't exist
    if not company_exists:
        company_url = company_url.replace("life", "about")

        # Open a new window
        driver.execute_script("window.open('');")
        driver.switch_to.window(driver.window_handles[1])
        driver.get(company_url)
        time.sleep(1)

        try:
            print("About tab opened")

            domain_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//a[@target='_blank' and contains(@class, 'link-without-visited-state')]"))
            )
            company_domain = domain_element.get_attribute('href')
            
            # Check if company exists by domain (secondary check)
            if company_domain:
                domain_response = supabase.table('companies').select(
                    'id, metadata').eq('company_domain', company_domain).execute()
                if len(domain_response.data) > 0:
                    print(f"Company already exists with domain: {company_domain}")
                    company_details = domain_response.data[0]['metadata']
                    company_exists = True  # Update company_exists when found by domain
                else:
                    company_details = extract_company_details(driver)
                    print(f"Company Details: {company_details}")
                    print(f"Company Domain: {company_domain}")
            else:
                company_details = extract_company_details(driver)
                print(f"Company Details: {company_details}")

        except (NoSuchElementException, TimeoutException) as e:
            print(f"Error finding element or waiting: {e}")
            company_domain = None
            company_details = json.dumps({})
        
        finally:
            # Always close the new window and switch back to the original
            driver.close()
            driver.switch_to.window(driver.window_handles[0])
    else:
        # Use existing company data
        print(f"Company already exists with LinkedIn URL: {company_url}")
        if company_response.data[0]['company_domain']:
            company_domain = company_response.data[0]['company_domain']
        if company_response.data[0]['metadata']:
            company_details = company_response.data[0]['metadata']

    role_meta = {
        "posted_at": posted_at,
        "applicants": applicants
    }
    print(f"Role Metadata: {json.dumps(role_meta)}")

    hiring_manager_element = safe_find_element(
        driver, By.CLASS_NAME, 'hirer-card__hirer-information')

    if hiring_manager_element:
        hiring_manager = hiring_manager_element.find_element(
            By.TAG_NAME, 'a')
        hiring_manager_name = extract_name(
            hiring_manager.get_attribute('aria-label'))
        hiring_manager_linkedin_url = hiring_manager.get_attribute('href')
    else:
        hiring_manager_name = None
        hiring_manager_linkedin_url = None
    print(f"Hiring Manager: {hiring_manager_name}")

    job_details = driver.find_element(By.ID, 'job-details').text

    await insert_data(None, company_name, company_location, company_url, title, role_meta, hiring_manager_name, hiring_manager_linkedin_url, job_details, job_id, company_domain, company_details)

# %%


def login(driver):
    driver.get("https://linkedin.com/uas/login")
    time.sleep(1)
    username = driver.find_element(By.ID, "username")
    username.send_keys(os.getenv("LINKEDIN_USERNAME"))
    password_field = driver.find_element(By.ID, "password")
    password_field.send_keys(os.getenv("LINKEDIN_PASSWORD"))
    driver.find_element(By.XPATH, "//button[@type='submit']").click()
    time.sleep(3)


def check_for_captcha(driver):
    # Replace with an appropriate selector to detect CAPTCHA on the LinkedIn page
    captcha_selector = '/html/body/div/main/h1'
    try:
        captcha_element = driver.find_element(
            By.XPATH, captcha_selector)
        if captcha_element:
            print("CAPTCHA detected. Please solve the CAPTCHA to continue.")
            input("Press Enter after solving the CAPTCHA...")
    except NoSuchElementException:
        pass


def is_promoted(driver) -> bool:
    # get all the <li> elements
    li_elements = driver.find_elements_by_xpath('//li')

    # loop through each <li> element
    for li in li_elements:
        # check if the text 'promoted' is in the element
        if 'promoted' in li.find_element_by_xpath('.//li[contains(@class, "job-card-container__footer-item")]').text:
            return True

    return False


# %%
chrome_options = Options()
# Uncomment the following line for headless mode
# chrome_options.add_argument("--headless=new")
# chrome_options.add_argument("--headless=false")

# temp_profile_dir = tempfile.mkdtemp()
# chrome_options.add_argument(f'--user-data-dir={temp_profile_dir}')
# chrome_options.add_argument(f'--profile-directory=Default')
# chrome_options.add_argument("--headless=new")

# chrome_options.binary_location = chromedriver_binary.chromedriver_filename #"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# driver = webdriver.Chrome(service=Service(
#     executable_path=ChromeDriverManager().install()), options=chrome_options)

driver = webdriver.Chrome(options=chrome_options)

login(driver)
check_for_captcha(driver=driver)



url = f"https://www.linkedin.com/jobs/search/?currentJobId=3555162466&f_TPR=r604800&geoId=91000007&keywords=React.js&location=India&sortBy=DD"
print(url)
driver.get(url)
time.sleep(4)


def scroll_to_parent_ul(driver, li_class_name):
    # Wait for initial items to load
    try:
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located(
            (By.CLASS_NAME, li_class_name)))

        # Get initial count of items
        items = driver.find_elements(By.CLASS_NAME, li_class_name)
        prev_count = len(items)

        # Keep scrolling until no new items are loaded
        max_attempts = 10  # Limit scrolling attempts to avoid infinite loops
        attempts = 0

        while attempts < max_attempts:
            # Scroll to the last item
            last_item = items[-1]
            driver.execute_script(
                "arguments[0].scrollIntoView(true);", last_item)

            # Wait for potential new items to load
            time.sleep(2)

            # Get new count of items
            items = driver.find_elements(By.CLASS_NAME, li_class_name)
            current_count = len(items)

            print(f"Found {current_count} items after scrolling")

            # If no new items were loaded, break
            if current_count == prev_count:
                attempts += 1
            else:
                attempts = 0  # Reset attempts if we found new items

            prev_count = current_count

        return items
    except Exception as e:
        print(f"Error scrolling to parent ul: {e}")
        return []


async def worker_process(driver, start_url, item_count):
    try:
        while True:
            if item_count >= 1000:
                break

            print('Item count', item_count)
            url = f"{start_url}&start={item_count}"
            print(f"Processing page at index {item_count}")

            # Use WebDriverWait instead of sleep
            driver.get(url)

            try:
                list_items = scroll_to_parent_ul(driver, 'job-card-container')

                if len(list_items) == 0:
                    print("No items found on page")
                    break

                print(f'Found {len(list_items)} items')

                for index, item in enumerate(list_items):
                    for attempt in range(3):
                        try:
                            item.click()
                            time.sleep(2)

                            job_id = item.get_attribute('data-job-id')
                            
                            try:
                                # Wrap in try/except to continue even if one job fails
                                await write_data(driver, job_id)
                            except Exception as job_error:
                                print(f"Error processing job {job_id}: {str(job_error)}")
                                # Continue to the next job even if this one fails
                            
                            break

                        except StaleElementReferenceException:
                            if attempt == 2:
                                print(f"Failed to process item after 3 attempts")
                            else:
                                print(f"Retrying item (attempt {attempt + 1})")
                                await asyncio.sleep(1)
                        except Exception as e:
                            print(f"Error processing item: {str(e)}")
                            break  # Move to next item if there's any other error

                print('Moving to next page')
                item_count += 25

            except Exception as e:
                print(f"Error processing page: {str(e)}")
                # Continue to next page even if there's an error
                item_count += 25

    except Exception as e:
        traceback.print_exc()
        return





async def main():
    urls = [

        # "https://www.linkedin.com/jobs/search/?currentJobId=3902849504&f_TPR=r86400&geoId=92000000&keywords=frontend%20developer&location=Worldwide&origin=JOB_SEARCH_PAGE_JOB_FILTER&refresh&sortBy=DD",
        # "https://www.linkedin.com/jobs/search/?currentJobId=3904713377&f_TPR=r86400&geoId=92000000&keywords=nextjs&location=Worldwide&origin=JOB_SEARCH_PAGE_SEARCH_BUTTON&refresh=true&sortBy=DD",

        "https://www.linkedin.com/jobs/search/?currentJobId=3843718022&f_TPR=r86400&geoId=92000000&keywords=generative%20ai&location=Worldwide&origin=JOB_SEARCH_PAGE_SEARCH_BUTTON&refresh=true&sortBy=DD",

        # "https://www.linkedin.com/jobs/search/?currentJobId=3906221884&f_TPR=r86400&geoId=92000000&keywords=golang&location=Worldwide&origin=JOB_SEARCH_PAGE_SEARCH_BUTTON&refresh=true&sortBy=DD",

        "https://www.linkedin.com/jobs/search/?currentJobId=3902861304&f_TPR=r86400&geoId=92000000&keywords=java&location=Worldwide&origin=JOB_SEARCH_PAGE_SEARCH_BUTTON&refresh=true&sortBy=DD",
        "https://www.linkedin.com/jobs/search/?currentJobId=3906224840&f_TPR=r86400&geoId=92000000&keywords=php&location=Worldwide&origin=JOB_SEARCH_PAGE_SEARCH_BUTTON&refresh=true&sortBy=DD",
        # "https://www.linkedin.com/jobs/search/?currentJobId=3902866029&f_TPR=r86400&geoId=92000000&keywords=full%20stack&location=Worldwide&origin=JOB_SEARCH_PAGE_SEARCH_BUTTON&refresh=true&sortBy=DD",
        "https://www.linkedin.com/jobs/search/?currentJobId=3902943834&f_TPR=r86400&geoId=92000000&keywords=ios&location=Worldwide&origin=JOB_SEARCH_PAGE_SEARCH_BUTTON&refresh=true&sortBy=DD",
        "https://www.linkedin.com/jobs/search/?currentJobId=3906227962&f_TPR=r86400&geoId=92000000&keywords=kotlin&location=Worldwide&origin=JOB_SEARCH_PAGE_SEARCH_BUTTON&refresh=true&sortBy=DD",
        # "https://www.linkedin.com/jobs/search/?currentJobId=3838451749&f_TPR=r86400&geoId=92000000&keywords=machine%20learning&location=Worldwide&origin=JOB_SEARCH_PAGE_KEYWORD_AUTOCOMPLETE&refresh=true&sortBy=DD",
        "https://www.linkedin.com/jobs/search/?currentJobId=3878359179&f_TPR=r86400&geoId=92000000&keywords=data%20science&location=Worldwide&origin=JOB_SEARCH_PAGE_KEYWORD_AUTOCOMPLETE&refresh=true&sortBy=DD",

        # "https://www.linkedin.com/jobs/search/?currentJobId=3906230642&f_TPR=r86400&geoId=92000000&keywords=Machine%20learning&location=Worldwide&origin=JOB_SEARCH_PAGE_SEARCH_BUTTON&refresh=true&sortBy=DD",
        "https://www.linkedin.com/jobs/search/?currentJobId=3906234356&f_TPR=r86400&geoId=92000000&keywords=python&location=Worldwide&origin=JOB_SEARCH_PAGE_SEARCH_BUTTON&refresh=true&sortBy=DD",
        # "https://www.linkedin.com/jobs/search/?currentJobId=3906234187&f_TPR=r86400&geoId=92000000&keywords=c%2B%2B&location=Worldwide&origin=JOB_SEARCH_PAGE_SEARCH_BUTTON&refresh=true&sortBy=DD",
        # "https://www.linkedin.com/jobs/search/?currentJobId=3902863196&f_TPR=r86400&geoId=92000000&keywords=c%23&location=Worldwide&origin=JOB_SEARCH_PAGE_SEARCH_BUTTON&refresh=true&sortBy=DD",
    ]

    for u in urls:
        await worker_process(driver, u, 0)

if __name__ == "__main__":
    asyncio.run(main())
