from supabase import Client, create_client
import json
import time
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from .safe_find_element import safe_find_element
from .extract_name import extract_name
from .extract_company_details import extract_company_details
from ..insert_data import insert_data


async def process_job_data(driver, job_id, supabase: Client):
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
        role_metadata = driver.execute_script(
            """
            return document.querySelector('.job-details-jobs-unified-top-card__primary-description-container')
                    .getElementsByTagName('div')[0].innerText;
        """
        )
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
        supabase,
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
