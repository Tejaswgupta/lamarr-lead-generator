# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a LinkedIn lead generation system that scrapes job postings and hiring managers, then automatically adds them to Apollo.io sequences. The system consists of two main components:

1. **LinkedIn Scraper** (`main.py`) - Scrapes LinkedIn job postings and hiring manager information
2. **Apollo Automation** (`apollo.py`) - Adds found recruiters to Apollo.io sequences

## Database Architecture

The system uses PostgreSQL with four main tables:

- **`companies`** - Stores company information scraped from LinkedIn
- **`recruiters`** - Stores hiring manager/recruiter information with Apollo integration status
- **`linkedin_jobs`** - Stores job posting details linked to companies and recruiters
- **`processing_logs`** - Tracks processing status and errors

## Common Development Commands

### Database Setup
```bash
# Initialize Prisma and setup database (run this first)
python setup_prisma.py

# Or use npm scripts:
npm run setup

# Generate Prisma client (after schema changes)
npm run db:generate

# Push schema changes to database
npm run db:push

# Check database contents and verify data
python check_database_results.py

# Open Prisma Studio to view database
npm run db:studio
```

### Running the Applications

**LinkedIn Scraper:**
```bash
python main.py
```
- Requires valid LinkedIn credentials in environment variables
- Uses Brave browser (ensure Brave Browser.app is installed)
- Can be stopped gracefully by creating a STOP_SCRAPING file

**Apollo Automation:**
```bash
python apollo.py
```
- Requires Apollo.io credentials in environment variables
- Uses undetected Chrome driver to bypass Cloudflare protection
- Processes recruiters in batches (configurable batch size)
- Requires manual login completion before automation begins

### Dependencies
```bash
# Install Python packages
pip install -r requirements_postgresql.txt

# Install Node.js dependencies (Prisma CLI)
npm install

# Install Prisma CLI globally
npm install -g prisma
```

## Environment Configuration

The system expects these environment variables in a `.env` file:

**Database Configuration:**
- `DB_HOST` (default: localhost)
- `DB_PORT` (default: 5432)
- `DB_NAME` (default: lead_generator)
- `DB_USER` (default: postgres)
- `DB_PASSWORD` (default: password)

**LinkedIn Credentials:**
- `LINKEDIN_USERNAME`
- `LINKEDIN_PASSWORD`

**Apollo Credentials:**
- `APOLLO_EMAIL` (used in login instructions)
- `APOLLO_PASSWORD`

**Database Configuration (for Prisma):**
- `DATABASE_URL` - Automatically constructed from individual DB_* variables
- `DB_HOST` (default: localhost)
- `DB_PORT` (default: 5432)
- `DB_NAME` (default: lead_generator)
- `DB_USER` (default: postgres)
- `DB_PASSWORD` (default: password)

## Key Implementation Details

### LinkedIn Scraper (`main.py`)
- Uses **Prisma ORM** for database operations instead of raw SQL
- Uses Selenium WebDriver with Brave browser
- Scrolls through job listings to load all items
- Extracts company details by opening company pages in new windows
- Handles CAPTCHAs with manual intervention prompts
- Supports stop/resume functionality via STOP_SCRAPING file
- Processes jobs from configurable search URLs
- Includes proper database connection management with Prisma client

### Apollo Automation (`apollo.py`)
- Uses undetected_chromedriver to bypass Cloudflare
- Implements robust name matching algorithm (80% similarity threshold)
- Handles dynamic web elements with multiple selector fallbacks
- Processes recruiters in configurable batches with user confirmation
- Includes comprehensive error handling and retry logic
- Updates recruiter status in database after processing

### Database (Prisma ORM)
- **Schema Definition**: Defined in `prisma/schema.prisma`
- **Models**: Company, Recruiter, Job, ProcessingLog
- **Client Management**: Global Prisma client instance with proper connection handling
- **Type Safety**: Full type safety with generated Prisma client
- **Migration**: Schema changes managed via Prisma migrations
- **Studio**: Visual database browser via `npm run db:studio`

### Key Prisma Functions
- `setup_database()` - Establishes Prisma client connection
- `disconnect_database()` - Properly closes Prisma client connection
- `insert_data()` - Uses Prisma queries for data insertion with upsert logic
- Model queries use `find_first()`, `create()`, `update()` methods

## Important Notes

- The system is designed for defensive security research and lead generation
- Both applications include comprehensive logging to files
- Database operations now use **Prisma ORM** for type safety and better development experience
- The Apollo automation includes manual verification steps for accuracy
- All scraping operations respect rate limits and include error handling
- The system can be extended to support additional job boards or CRMs
- Prisma provides automatic database schema management and migrations

## File Structure

```
├── main.py                    # LinkedIn job scraper (updated with Prisma)
├── apollo.py                  # Apollo.io automation
├── setup_prisma.py           # Prisma setup and initialization script
├── setup_db.py               # Legacy database initialization (deprecated)
├── check_database_results.py # Database verification utility
├── requirements_postgresql.txt # Python dependencies (updated for Prisma)
├── package.json              # Node.js dependencies for Prisma CLI
├── prisma/
│   └── schema.prisma         # Prisma database schema definition
└── .env                      # Environment variables (not tracked)
```

## Migration from asyncpg to Prisma

The system has been migrated from raw PostgreSQL queries (asyncpg) to Prisma ORM:

### Benefits of Prisma Migration:
- **Type Safety**: Full TypeScript-like type safety in Python
- **Auto-completion**: Better IDE support with auto-completion
- **Schema Management**: Declarative schema with automatic migrations
- **Query Builder**: Intuitive query API instead of raw SQL
- **Database Studio**: Visual database browser and editor
- **Connection Pooling**: Built-in connection management
- **Error Handling**: Better error messages and debugging

### Key Changes:
1. Replaced `asyncpg` with `prisma` Python client
2. Created `prisma/schema.prisma` with model definitions
3. Updated all database queries to use Prisma client methods
4. Added proper connection management with setup/disconnect functions
5. Created setup script for Prisma initialization
6. Updated requirements and documentation