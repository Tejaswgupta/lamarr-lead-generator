import asyncio
import datetime
import json
import os
import time
from enum import Enum

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from supabase import Client, create_client

# Import existing Apollo functionality
from apollo import fetch_data, login, search

# Load environment variables
load_dotenv(override=True)

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize AWS SES client
AWS_REGION = os.getenv("AWS_REGION")
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_NAME = os.getenv("SENDER_NAME")

ses_client = boto3.client(
    'ses',
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY
)

class EmailStatus(Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    OPENED = "opened"
    REPLIED = "replied"
    BOUNCED = "bounced"
    FAILED = "failed"

class EmailType(Enum):
    INITIAL = "initial"
    FOLLOW_UP_3 = "follow_up_3"
    FOLLOW_UP_5 = "follow_up_5"

def should_send_email(last_email_date, email_count):
    """
    Determine if we should send an email based on the last email date and count
    """
    # If no emails sent yet, send initial email
    if email_count == 0 or last_email_date is None:
        return True, EmailType.INITIAL
    
    # Convert last_email_date to datetime object if it's a string
    if isinstance(last_email_date, str):
        last_email_date = datetime.datetime.fromisoformat(last_email_date.replace('Z', '+00:00'))
    
    days_since_last_email = (datetime.datetime.now(datetime.timezone.utc) - last_email_date).days
    
    # Follow-up logic
    if email_count == 1 and days_since_last_email >= 3:
        return True, EmailType.FOLLOW_UP_3
    elif email_count == 2 and days_since_last_email >= 5:
        return True, EmailType.FOLLOW_UP_5
    
    return False, None

def generate_email_content(recruiter_name, company_name, job_info, email_type):
    """
    Generate appropriate email content based on type (initial or follow-up)
    """
    job_titles = ", ".join([job["job_title"] for job in job_info["jobs"]])
    
    if email_type == EmailType.INITIAL:
        subject = f"Regarding {job_titles} position at {company_name}"
        body_html = f"""
        <html>
        <body>
            <p>Hi {recruiter_name},</p>
            <p>I hope this email finds you well. My name is {SENDER_NAME}, and I came across your company's job posting for {job_titles}.</p>
            <p>I have experience in this field and would love to discuss how my skills could be a good fit for your team at {company_name}.</p>
            <p>Would you be available for a quick chat this week to discuss the opportunity further?</p>
            <p>Best regards,<br>{SENDER_NAME}</p>
        </body>
        </html>
        """
    elif email_type == EmailType.FOLLOW_UP_3:
        subject = f"Following up: {job_titles} position at {company_name}"
        body_html = f"""
        <html>
        <body>
            <p>Hi {recruiter_name},</p>
            <p>I wanted to follow up on my previous email regarding the {job_titles} position at {company_name}.</p>
            <p>I'm still very interested in the role and would appreciate the opportunity to discuss how I could contribute to your team.</p>
            <p>Please let me know if you'd like to schedule a brief conversation.</p>
            <p>Best regards,<br>{SENDER_NAME}</p>
        </body>
        </html>
        """
    elif email_type == EmailType.FOLLOW_UP_5:
        subject = f"One last follow-up: {job_titles} position at {company_name}"
        body_html = f"""
        <html>
        <body>
            <p>Hi {recruiter_name},</p>
            <p>I hope you've been well. I'm reaching out one final time regarding the {job_titles} position at {company_name}.</p>
            <p>If the timing isn't right or if the position has been filled, I completely understand. However, if you're still considering candidates, I'd be grateful for the opportunity to discuss how my background aligns with your needs.</p>
            <p>Thank you for your consideration.</p>
            <p>Best regards,<br>{SENDER_NAME}</p>
        </body>
        </html>
        """
    
    return subject, body_html

async def send_email_with_ses(to_email, subject, body_html, recruiter_id, job_id, email_type):
    """
    Send email using Amazon SES and record the attempt in the database
    """
    try:
        # Send email via SES
        response = ses_client.send_email(
            Source=f"{SENDER_NAME} <{SENDER_EMAIL}>",
            Destination={'ToAddresses': [to_email]},
            Message={
                'Subject': {'Data': subject},
                'Body': {'Html': {'Data': body_html}}
            },
            ConfigurationSetName='EmailMetrics'  # SES configuration set for tracking
        )
        
        message_id = response['MessageId']
        
        # Record the email in the database
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        email_data = {
            'recruiter_id': recruiter_id,
            'job_id': job_id,
            'message_id': message_id,
            'email_type': email_type.value,
            'sent_at': now,
            'status': EmailStatus.SENT.value,
            'subject': subject,
            'content': body_html
        }
        
        # Insert email record
        supabase.table('email_log').insert(email_data).execute()
        
        # Update recruiter record with email count and timestamp
        email_count_response = supabase.table('recruiters').select('email_count').eq('id', recruiter_id).execute()
        current_count = email_count_response.data[0]['email_count'] if email_count_response.data else 0
        
        supabase.table('recruiters').update({
            'last_email': now,
            'email_count': current_count + 1
        }).eq('id', recruiter_id).execute()
        
        print(f"Email sent to {to_email} with message ID: {message_id}")
        return True, message_id
    
    except ClientError as e:
        error_message = e.response['Error']['Message']
        print(f"Failed to send email to {to_email}: {error_message}")
        
        # Record the failure
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        email_data = {
            'recruiter_id': recruiter_id,
            'job_id': job_id,
            'email_type': email_type.value,
            'sent_at': now,
            'status': EmailStatus.FAILED.value,
            'error_message': error_message,
            'subject': subject,
            'content': body_html
        }
        
        supabase.table('email_log').insert(email_data).execute()
        return False, None

async def process_ses_notifications():
    """
    Process SES notifications from SNS (bounce, complaint, delivery)
    This would typically be run as a separate serverless function triggered by SNS
    """
    # This is a placeholder for actual SNS processing
    # In a real implementation, this would be a Lambda function triggered by SNS
    pass

async def scrape_missing_emails(driver):
    """
    Scrape emails for recruiters that don't have emails in the database
    """
    # Get recruiters without emails
    response = supabase.rpc('get_recruiters_without_emails').execute()
    recruiters_without_emails = response.data
    
    print(f"Found {len(recruiters_without_emails)} recruiters without emails")
    
    for recruiter in recruiters_without_emails:
        recruiter_id = recruiter['id']
        name = recruiter['name']
        company_domain = recruiter['company_domain']
        
        # Try to find email using Apollo
        email = search(driver, name, company_domain)
        
        if email != -1:  # If email was found
            # Update recruiter record with email
            supabase.table('recruiters').update({
                'email': email
            }).eq('id', recruiter_id).execute()
            
            print(f"Updated email for {name}: {email}")
        else:
            print(f"Could not find email for {name} at {company_domain}")
        
        # Sleep to avoid rate limiting
        time.sleep(2)

async def send_due_emails():
    """
    Send emails to recruiters who are due for initial or follow-up emails
    """
    # Get recruiters with emails who are due for emails
    response = supabase.rpc('get_recruiters_due_for_emails').execute()
    recruiters_due = response.data
    
    print(f"Found {len(recruiters_due)} recruiters due for emails")
    
    for recruiter in recruiters_due:
        recruiter_id = recruiter['id']
        name = recruiter['name']
        email = recruiter['email']
        company_name = recruiter['company_name']
        last_email = recruiter.get('last_email')
        email_count = recruiter.get('email_count', 0)
        
        # Get job info for this recruiter
        job_response = supabase.rpc('get_job_info_for_recruiter', {
            'recruiter_id': recruiter_id
        }).execute()
        
        job_info = {
            'company_name': company_name,
            'jobs': job_response.data,
            'primary_job_id': job_response.data[0]['job_id'] if job_response.data else None
        }
        
        should_send, email_type = should_send_email(last_email, email_count)
        
        if should_send and job_info['primary_job_id']:
            subject, body_html = generate_email_content(name, company_name, job_info, email_type)
            
            success, message_id = await send_email_with_ses(
                email, 
                subject, 
                body_html, 
                recruiter_id, 
                job_info['primary_job_id'],
                email_type
            )
            
            if success:
                print(f"Sent {email_type.value} email to {name} <{email}>")
            else:
                print(f"Failed to send {email_type.value} email to {name} <{email}>")
            
            # Sleep to avoid SES rate limiting
            time.sleep(1)

async def main():
    """
    Main function to orchestrate the lead generation pipeline
    """
    # Initialize Chrome driver
    chrome_options = Options()
    # chrome_options.add_argument("--headless")  # Uncomment for headless mode
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        # Login to Apollo
        login(driver)
        
        # 1. Scrape missing emails
        await scrape_missing_emails(driver)
        
        # 2. Send due emails (initial and follow-ups)
        await send_due_emails()
        
        # 3. Process any SES notifications (in a real implementation, this would be a separate service)
        await process_ses_notifications()
        
    finally:
        # Close the browser
        driver.quit()

if __name__ == "__main__":
    asyncio.run(main()) 