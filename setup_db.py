# Database Setup Script for Local PostgreSQL
# Run this script to set up the database schema

import asyncpg
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

print(os.getenv('DB_NAME'))

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', 5432),
    'database': os.getenv('DB_NAME', 'lead_generator'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'password')
}

async def setup_database():
    """Setup database tables"""
    try:
        # Connect to PostgreSQL
        conn = await asyncpg.connect(**DB_CONFIG)
        
        print("Creating database tables...")
        
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
        
        # Create indexes for better performance
        await conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_companies_linkedin_url ON companies(linkedin_url);
            CREATE INDEX IF NOT EXISTS idx_companies_domain ON companies(company_domain);
            CREATE INDEX IF NOT EXISTS idx_recruiters_linkedin_url ON recruiters(linkedin_url);
            CREATE INDEX IF NOT EXISTS idx_recruiters_status ON recruiters(apollo_sequence_status);
            CREATE INDEX IF NOT EXISTS idx_recruiters_domain ON recruiters(company_domain);
            CREATE INDEX IF NOT EXISTS idx_jobs_company ON linkedin_jobs(company_id);
            CREATE INDEX IF NOT EXISTS idx_jobs_recruiter ON linkedin_jobs(recruiter_id);
            CREATE INDEX IF NOT EXISTS idx_logs_recruiter ON processing_logs(recruiter_id);
        ''')
        
        # Create a function to get recruiters with job info
        await conn.execute('''
            CREATE OR REPLACE FUNCTION get_recruiters_with_job_info()
            RETURNS TABLE (
                id INTEGER,
                name VARCHAR,
                company_domain VARCHAR,
                company_name VARCHAR,
                first_email TIMESTAMP,
                last_email TIMESTAMP,
                email_count INTEGER,
                apollo_sequence_status VARCHAR,
                job_title VARCHAR,
                job_id BIGINT
            ) AS $$
            BEGIN
                RETURN QUERY
                SELECT 
                    r.id,
                    r.name,
                    r.company_domain,
                    c.name as company_name,
                    r.first_email,
                    r.last_email,
                    r.email_count,
                    r.apollo_sequence_status,
                    lj.title as job_title,
                    lj.id as job_id
                FROM recruiters r
                LEFT JOIN companies c ON r.company_domain = c.company_domain
                LEFT JOIN linkedin_jobs lj ON r.id = lj.recruiter_id
                WHERE r.company_domain IS NOT NULL
                ORDER BY r.created_at DESC;
            END;
            $$ LANGUAGE plpgsql;
        ''')
        
        await conn.close()
        print("Database setup completed successfully!")
        
        # Print table information
        print("\nCreated tables:")
        print("1. companies - Stores company information")
        print("2. recruiters - Stores recruiter/hiring manager information")
        print("3. linkedin_jobs - Stores job posting information")
        print("4. processing_logs - Stores processing logs and errors")
        print("\nDatabase is ready for use!")
        
    except Exception as e:
        print(f"Database setup failed: {e}")
        return False

if __name__ == "__main__":
    print("PostgreSQL Database Setup")
    print("=" * 30)
    print(f"Host: {DB_CONFIG['host']}")
    print(f"Port: {DB_CONFIG['port']}")
    print(f"Database: {DB_CONFIG['database']}")
    print(f"User: {DB_CONFIG['user']}")
    print()
    
    asyncio.run(setup_database())
