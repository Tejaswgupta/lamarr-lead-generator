import datetime
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


def login(driver):
    driver.get("https://app.apollo.io/#/login")
    element = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable(
                            (By.XPATH, '/html/body/div[2]/div/div[2]/div[2]/div/div/div/div[3]/div[2]/a/button'))
                    )

    # wait for manual login to finish
    input("Login and Press Enter to continue: ")


def search(driver, hiring_manager, company_domain):
    driver.get("https://app.apollo.io/#/people")
    time.sleep(2)


    company_drobdown_btn = driver.find_element(
        By.XPATH, "//div[contains(@class, 'zp_YfgQq')]/span[text()='Company']/parent::div")
    print(company_drobdown_btn)
    # driver.execute_script("arguments[0].scrollIntoView(true);", company_drobdown_btn)
    company_drobdown_btn.click()
    
    company_input_box = driver.find_element(By.CLASS_NAME, "Select-input")
    company_input_box.send_keys(company_domain)
    
    WebDriverWait(driver, 5).until(
        EC.element_to_be_clickable(
            (By.CLASS_NAME, "Select-option"))
    )
    driver.find_element(By.CLASS_NAME, "Select-option").click()
    time.sleep(1)

    search_input_box = driver.find_element(
        By.XPATH, "//input[@placeholder='Search']")
    search_input_box.send_keys(hiring_manager)
    search_input_box.send_keys(Keys.RETURN)

    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH,
                                            "//button//span[text()='Access email']"))
        )

        hiring_manager_element = driver.find_element(By.XPATH, f"//a[text()='{hiring_manager}']")
        print(hiring_manager_element)

        driver.execute_script("arguments[0].scrollIntoView(true);", hiring_manager_element)
        manager_url = driver.find_element(By.XPATH, f"//a[text()='{hiring_manager}']").get_attribute("href")

        print(manager_url)
    
        # Open a new window 
        driver.execute_script("window.open('');") 
        driver.switch_to.window(driver.window_handles[1])


        driver.get(manager_url)
        time.sleep(5)

        # First try to get the email directly if it's already visible
        try:
            # Check if the email is already visible (meaning button was already clicked)
            manager_email = driver.find_element(By.CSS_SELECTOR, "//a[contains(text(), '@')]").text
            print("Email already accessible: ", manager_email)
        except:
            # Email not directly visible, need to click the button
            try:
                # Find and click the access email button
                button_element = driver.find_element(By.XPATH, "//button//span[text()='Access email']")
                print("Found access email button, clicking it")
                button_element.click()
                time.sleep(3.5)
                
                # Now try to get the email after clicking
                try:
                    manager_email = driver.find_element(By.XPATH, "//a[contains(text(), '@')]").text
                    print("Retrieved email after clicking button: ", manager_email)
                except:
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])
                    print(f"COULD NOT FIND EMAIL OF: {hiring_manager} ({company_domain}) even after clicking button\n")
                    return -1
            except:
                # Could not find the access email button
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
                print(f"COULD NOT FIND ACCESS BUTTON FOR: {hiring_manager} ({company_domain})\n")
                return -1
            
        print("manager_email: ", manager_email)
        driver.close()
        driver.switch_to.window(driver.window_handles[0])
        return manager_email

    except:
        print(f"COULD NOT FIND EMAIL OF: {hiring_manager} ({company_domain})\n")
        return -1


    


chrome_options = Options()
driver = webdriver.Chrome(options=chrome_options)

login(driver)

import os

from dotenv import load_dotenv
# %%
from supabase import Client, create_client

# Load environment variables
load_dotenv(override=True)

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

async def fetch_data():
    # Get recruiters with company and job information
    response = supabase.rpc('get_recruiters_with_job_info', params={}).execute()
    rows = response.data

    # Group jobs by recruiter to handle multiple postings
    recruiter_jobs = {}
    for row in rows:
        recruiter_id = row['id']
        if recruiter_id not in recruiter_jobs:
            recruiter_jobs[recruiter_id] = {
                'name': row['name'],
                'company_domain': row['company_domain'],
                'company_name': row['company_name'],
                'first_email': row.get('first_email'),
                'last_email': row.get('last_email'),
                'email_count': row.get('email_count', 0),
                'jobs': []
            }
        recruiter_jobs[recruiter_id]['jobs'].append({
            'job_title': row['job_title'],
            'job_id': row['job_id']
        })

    hiring_manager_list = []
    company_domain_list = []
    email_history = []
    job_info_list = []

    # Process each recruiter only once, combining job information if needed
    for recruiter_id, data in recruiter_jobs.items():
        # if should_send_email(data.get('last_email'), data.get('email_count', 0)):
        hiring_manager_list.append(data['name'])
        company_domain_list.append(data['company_domain'])

        # Combine job information for the email
        job_info_list.append({
            'company_name': data['company_name'],
            'jobs': data['jobs'],  # Now we pass all jobs
            # Use first job as primary for tracking
            'primary_job_id': data['jobs'][0]['job_id']
        })

        email_history.append({
            'recruiter_id': recruiter_id,
            'first_email': data.get('first_email'),
            'last_email': data.get('last_email'),
            'email_count': data.get('email_count', 0)
        })

    print(f"Found {len(hiring_manager_list)} recruiters to contact")
    return hiring_manager_list, company_domain_list, email_history, job_info_list
