# LinkedIn Lead Generator for macOS

A complete LinkedIn lead generation pipeline optimized for macOS that automatically scrapes job postings, extracts hiring manager information, and integrates with Apollo.io for sequence management. The system uses Selenium WebDriver for LinkedIn automation and Supabase for data storage.

## 🍎 macOS Optimized Features

- **Native macOS Chrome Integration**: Uses macOS Chrome profile paths and optimized settings
- **Automatic Chrome Driver Management**: Handles ChromeDriver installation and updates
- **macOS Permission Handling**: Guides users through common macOS security settings
- **System Requirements Check**: Validates all dependencies before running
- **Homebrew Integration**: Automated installation of required tools via Homebrew

## System Components

1. **LinkedIn Job Scraping**: Automatically scrapes job postings from LinkedIn job search results
2. **Company Data Extraction**: Extracts detailed company information and metadata
3. **Hiring Manager Detection**: Identifies and extracts hiring manager LinkedIn profiles
4. **Apollo.io Integration**: Automatically adds hiring managers to Apollo.io sequences
5. **Data Storage**: Stores all data in Supabase with proper relationships
6. **Duplicate Prevention**: Checks for existing jobs and companies to avoid duplicates

## 🚀 Quick Setup for macOS

### Option 1: Automated Setup (Recommended)

```bash
# Make the setup script executable and run it
chmod +x setup_macos.sh
./setup_macos.sh
```

The setup script will:

- Install Homebrew (if not present)
- Install Python 3 and Google Chrome
- Install all Python dependencies
- Create a template `.env` file
- Generate a test script to verify setup

### Option 2: Manual Setup

#### Prerequisites

- macOS 10.15+ (Catalina or later)
- Google Chrome installed
- Python 3.8+
- Supabase account and project
- LinkedIn account
- Apollo.io account (optional, for sequence management)

#### Manual Installation Steps

1. **Install Homebrew** (if not already installed):

   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```

2. **Install Python and Chrome**:

   ```bash
   brew install python
   brew install --cask google-chrome
   ```

3. **Install Python Dependencies**:

   ```bash
   pip3 install -r requirements.txt
   ```

4. **Setup Environment Variables** (see below)

## Environment Variables

Create a `.env` file in the project root with the following variables:

```env
# Supabase Configuration
SUPABASE_URL=https://your-supabase-url.supabase.co
SUPABASE_KEY=your-supabase-anon-key

# LinkedIn Credentials
LINKEDIN_USERNAME=your-linkedin-email
LINKEDIN_PASSWORD=your-linkedin-password
```

## 🗄️ Database Setup

The script requires the following Supabase tables:

```sql
-- Companies table
CREATE TABLE companies (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    linkedin_url TEXT UNIQUE,
    location TEXT,
    company_domain TEXT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Recruiters table
CREATE TABLE recruiters (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    linkedin_url TEXT UNIQUE,
    company_domain TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- LinkedIn Jobs table
CREATE TABLE linkedin_jobs (
    id INTEGER PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id),
    recruiter_id INTEGER REFERENCES recruiters(id),
    title TEXT NOT NULL,
    description TEXT,
    role_metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## Usage

### 1. Test Your Setup

```bash
python3 test_setup.py
```

This will verify that all dependencies are properly installed and configured.

### 2. Run the Lead Generator

```bash
python3 final_main.py
```

The script will:

1. Open Chrome with your existing profile
2. Log into LinkedIn
3. Scrape job postings from configured search URLs
4. Extract company and hiring manager information
5. Store data in Supabase
6. Optionally add hiring managers to Apollo.io sequences

### 3. Customize Job Search URLs

Edit the `urls` list in the `main()` function of `final_main.py` to include your desired LinkedIn job search URLs:

```python
urls = [
    "https://www.linkedin.com/jobs/search/?keywords=your%20keywords&location=Your%20Location",
    # Add more URLs as needed
]
```

## 🔧 Configuration Options

### Chrome Profile Setup

The script uses your default Chrome profile by default. If you want to use a different profile:

1. Open Chrome and go to `chrome://settings/people`
2. Note the profile directory name
3. Update the `DEFAULT_PROFILE` variable in `final_main.py`

### Apollo.io Integration

To enable Apollo.io integration:

1. Install the Apollo.io Chrome extension
2. Log into Apollo.io in your Chrome profile
3. The script will automatically detect and use the Apollo sidebar

## 🩺 Troubleshooting

### Common macOS Issues

1. **Chrome Permission Errors**:

   - Go to System Preferences > Security & Privacy > Privacy
   - Add Terminal/your IDE to "Full Disk Access"

2. **Chrome Profile Access**:

   - Close all Chrome windows before running the script
   - Open Chrome manually once to ensure profile is created

3. **ChromeDriver Issues**:

   - The script uses `webdriver-manager` to automatically handle ChromeDriver
   - If issues persist, try: `brew upgrade google-chrome`

4. **Python Import Errors**:
   - Ensure you're using Python 3: `python3 final_main.py`
   - Reinstall dependencies: `pip3 install -r requirements.txt`

### Debug Mode

For debugging, add print statements or use the browser in non-headless mode by commenting out headless options in the `setup_driver()` function.

## 📊 Features

- ✅ macOS native Chrome integration
- ✅ Automatic job posting scraping
- ✅ Company information extraction
- ✅ Hiring manager identification
- ✅ Apollo.io sequence automation
- ✅ Duplicate prevention
- ✅ Comprehensive error handling
- ✅ Progress tracking and logging

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test on macOS
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## ⚠️ Disclaimer

This tool is for educational and legitimate business purposes only. Please ensure compliance with:

- LinkedIn's Terms of Service
- Apollo.io's Terms of Service
- Applicable data protection laws (GDPR, CCPA, etc.)
- Your organization's policies

Use responsibly and respect rate limits and privacy policies.
