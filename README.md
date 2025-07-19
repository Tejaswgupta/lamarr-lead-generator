# LinkedIn Lead Generator for macOS

## Overview
This project automates the process of scraping job postings from LinkedIn and storing relevant data in a Supabase database. The main script, `main.py`, orchestrates the workflow, leveraging several utility modules for browser automation, LinkedIn login, job data extraction, and system checks. The solution is tailored for macOS but includes fallback logic for other operating systems.

## Features
- Automated login to LinkedIn using provided credentials
- Scrapes job postings from specified LinkedIn job search URLs
- Extracts and processes job and company details
- Stores extracted data in a Supabase database
- Handles browser automation using Chrome profiles
- Includes system requirement checks for macOS

## File Structure
- `main.py`: Main entry point. Handles environment setup, driver initialization, LinkedIn login, and job scraping loop.
- `utils/`
  - `check_macos_requirements.py`: Verifies that the macOS environment meets all requirements for browser automation (e.g., Chrome installation, profile availability).
  - `setup_driver.py`: Sets up the Selenium Chrome driver with the correct user profile and binary path.
  - `extraction/`
    - `scrape_and_process_jobs.py`: Main scraping logic for LinkedIn job search pages. Handles navigation, extraction, and data upload to Supabase.
    - `extract_company_details.py`, `extract_name.py`, `process_job_data.py`, `safe_find_element.py`: Helper modules for extracting and processing specific pieces of job and company data.
  - `navigation/`
    - `login_to_linkedin.py`: Automates the login process to LinkedIn using Selenium.
    - Other helpers for UI navigation and interaction.

## Usage
1. **Install dependencies**
   - Ensure you have Python 3.8+ and Chrome installed.
   - Install required packages:
     ```bash
     pip install -r requirements.txt
     ```
2. **Set up environment variables**
   - Create a `.env` file in the project root with the following variables:
     ```env
     SUPABASE_URL=your_supabase_url
     SUPABASE_KEY=your_supabase_key
     LINKEDIN_USERNAME=your_linkedin_email
     LINKEDIN_PASSWORD=your_linkedin_password
     ```
3. **Configure Chrome profile**
   - On macOS, ensure the Chrome user profile specified in `main.py` (default: `Profile 3`) is set up and logged in to LinkedIn and Apollo (see caution below).
   - You can change the profile by editing the `DEFAULT_PROFILE` variable in `main.py`.
4. **Run the script**
   ```bash
   sudo python main.py
   ```

# Sudo is essential
- Running the script with sudo is required on macOS due to the need of controlling the mouse and keyboard, some Chrome user profile files (like Preferences or extension data) that'll cause "Permission Denied" errors otherwise.

## Important Caution: Apollo Login Required
**Before running the script, you must ensure that the selected Chrome profile is already logged in to your Apollo account.**

- If you are not logged in to Apollo before starting the script, you will be prompted to log in during the scraping process. However, this is not recommended because the script automates mouse movements and interactions, which can make manual login difficult or impossible during execution.
- To avoid issues, open Chrome with the specified profile, log in to Apollo (and LinkedIn), and verify your session is active before running the script.
  
## Troubleshooting
- If you encounter issues with Chrome driver setup or browser automation, ensure all system requirements are met (see `check_macos_requirements.py`).
- On macOS, you may need to grant accessibility permissions to Chrome and your terminal.
- If you see errors related to missing environment variables, double-check your `.env` file.

## License
This project is for personal and educational use only. Please respect LinkedIn and Apollo's terms of service when scraping data. 