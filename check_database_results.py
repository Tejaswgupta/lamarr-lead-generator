#!/usr/bin/env python3
"""
Database Results Checker
This script helps you verify the data in your PostgreSQL database after running main_1.py and apollo_1.py
"""

import os
import asyncio
import asyncpg
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv(override=True)

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', 5432),
    'database': os.getenv('DB_NAME', 'lead_generator'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'password')
}

async def get_db_connection():
    """Get database connection"""
    try:
        conn = await asyncpg.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"Database connection failed: {e}")
        return None

async def check_companies():
    """Check companies table"""
    conn = await get_db_connection()
    if not conn:
        return
    
    try:
        print("\n" + "="*60)
        print("📊 COMPANIES TABLE")
        print("="*60)
        
        # Count total companies
        count = await conn.fetchval("SELECT COUNT(*) FROM companies")
        print(f"Total companies: {count}")
        
        if count > 0:
            # Show recent companies
            companies = await conn.fetch("""
                SELECT name, company_domain, location, created_at 
                FROM companies 
                ORDER BY created_at DESC 
                LIMIT 10
            """)
            
            print(f"\nRecent companies (last 10):")
            print("-" * 80)
            for company in companies:
                domain = company['company_domain'] or 'No domain'
                location = company['location'] or 'No location'
                print(f"• {company['name']}")
                print(f"  Domain: {domain}")
                print(f"  Location: {location}")
                print(f"  Added: {company['created_at'].strftime('%Y-%m-%d %H:%M:%S')}")
                print()
        
        await conn.close()
        
    except Exception as e:
        print(f"Error checking companies: {e}")
        if conn:
            await conn.close()

async def check_recruiters():
    """Check recruiters table"""
    conn = await get_db_connection()
    if not conn:
        return
    
    try:
        print("\n" + "="*60)
        print("👥 RECRUITERS TABLE")
        print("="*60)
        
        # Count total recruiters
        count = await conn.fetchval("SELECT COUNT(*) FROM recruiters")
        print(f"Total recruiters: {count}")
        
        # Count by Apollo status
        status_counts = await conn.fetch("""
            SELECT apollo_sequence_status, COUNT(*) as count
            FROM recruiters 
            GROUP BY apollo_sequence_status
            ORDER BY count DESC
        """)
        
        print(f"\nApollo Sequence Status:")
        for status in status_counts:
            print(f"  {status['apollo_sequence_status']}: {status['count']}")
        
        if count > 0:
            # Show recent recruiters
            recruiters = await conn.fetch("""
                SELECT name, company_domain, apollo_sequence_status, 
                       apollo_sequence_added_at, created_at 
                FROM recruiters 
                ORDER BY created_at DESC 
                LIMIT 10
            """)
            
            print(f"\nRecent recruiters (last 10):")
            print("-" * 80)
            for recruiter in recruiters:
                status = recruiter['apollo_sequence_status']
                added_at = recruiter['apollo_sequence_added_at']
                if added_at:
                    added_at_str = added_at.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    added_at_str = 'Not added'
                    
                print(f"• {recruiter['name']}")
                print(f"  Company: {recruiter['company_domain'] or 'No domain'}")
                print(f"  Apollo Status: {status}")
                print(f"  Added to Apollo: {added_at_str}")
                print(f"  Found: {recruiter['created_at'].strftime('%Y-%m-%d %H:%M:%S')}")
                print()
        
        await conn.close()
        
    except Exception as e:
        print(f"Error checking recruiters: {e}")
        if conn:
            await conn.close()

async def check_jobs():
    """Check linkedin_jobs table"""
    conn = await get_db_connection()
    if not conn:
        return
    
    try:
        print("\n" + "="*60)
        print("💼 LINKEDIN JOBS TABLE")
        print("="*60)
        
        # Count total jobs
        count = await conn.fetchval("SELECT COUNT(*) FROM linkedin_jobs")
        print(f"Total jobs scraped: {count}")
        
        if count > 0:
            # Show recent jobs with company and recruiter info
            jobs = await conn.fetch("""
                SELECT lj.id, lj.title, c.name as company_name, 
                       r.name as recruiter_name, lj.created_at
                FROM linkedin_jobs lj
                LEFT JOIN companies c ON lj.company_id = c.id
                LEFT JOIN recruiters r ON lj.recruiter_id = r.id
                ORDER BY lj.created_at DESC 
                LIMIT 10
            """)
            
            print(f"\nRecent jobs (last 10):")
            print("-" * 80)
            for job in jobs:
                company = job['company_name'] or 'Unknown Company'
                recruiter = job['recruiter_name'] or 'No recruiter found'
                print(f"• Job ID: {job['id']}")
                print(f"  Title: {job['title']}")
                print(f"  Company: {company}")
                print(f"  Recruiter: {recruiter}")
                print(f"  Scraped: {job['created_at'].strftime('%Y-%m-%d %H:%M:%S')}")
                print()
        
        await conn.close()
        
    except Exception as e:
        print(f"Error checking jobs: {e}")
        if conn:
            await conn.close()

async def check_processing_logs():
    """Check processing_logs table"""
    conn = await get_db_connection()
    if not conn:
        return
    
    try:
        print("\n" + "="*60)
        print("📋 PROCESSING LOGS")
        print("="*60)
        
        # Count total logs
        count = await conn.fetchval("SELECT COUNT(*) FROM processing_logs")
        print(f"Total processing events: {count}")
        
        # Count by status
        status_counts = await conn.fetch("""
            SELECT status, COUNT(*) as count
            FROM processing_logs 
            GROUP BY status
            ORDER BY count DESC
        """)
        
        print(f"\nProcessing Status:")
        for status in status_counts:
            print(f"  {status['status']}: {status['count']}")
        
        if count > 0:
            # Show recent logs
            logs = await conn.fetch("""
                SELECT pl.recruiter_id, r.name, pl.status, 
                       pl.error_message, pl.created_at
                FROM processing_logs pl
                LEFT JOIN recruiters r ON pl.recruiter_id = r.id
                ORDER BY pl.created_at DESC 
                LIMIT 10
            """)
            
            print(f"\nRecent processing events (last 10):")
            print("-" * 80)
            for log in logs:
                recruiter = log['name'] or f"Recruiter ID: {log['recruiter_id']}"
                error = log['error_message'] or 'No error'
                print(f"• {recruiter}")
                print(f"  Status: {log['status']}")
                if log['error_message']:
                    print(f"  Error: {error}")
                print(f"  Time: {log['created_at'].strftime('%Y-%m-%d %H:%M:%S')}")
                print()
        
        await conn.close()
        
    except Exception as e:
        print(f"Error checking processing logs: {e}")
        if conn:
            await conn.close()

async def get_recruitment_pipeline_summary():
    """Get a summary of the recruitment pipeline"""
    conn = await get_db_connection()
    if not conn:
        return
    
    try:
        print("\n" + "="*60)
        print("🎯 RECRUITMENT PIPELINE SUMMARY")
        print("="*60)
        
        # Get counts for pipeline stages
        summary = await conn.fetchrow("""
            SELECT 
                (SELECT COUNT(*) FROM linkedin_jobs) as total_jobs,
                (SELECT COUNT(*) FROM companies) as total_companies,
                (SELECT COUNT(*) FROM recruiters) as total_recruiters,
                (SELECT COUNT(*) FROM recruiters WHERE apollo_sequence_status = 'pending') as pending_apollo,
                (SELECT COUNT(*) FROM recruiters WHERE apollo_sequence_status = 'success') as added_to_apollo,
                (SELECT COUNT(*) FROM recruiters WHERE apollo_sequence_status = 'failed') as failed_apollo
        """)
        
        print(f"📊 Pipeline Overview:")
        print(f"  Total Jobs Scraped: {summary['total_jobs']}")
        print(f"  Companies Found: {summary['total_companies']}")
        print(f"  Recruiters Identified: {summary['total_recruiters']}")
        print()
        print(f"🎯 Apollo.io Status:")
        print(f"  ⏳ Pending Addition: {summary['pending_apollo']}")
        print(f"  ✅ Successfully Added: {summary['added_to_apollo']}")
        print(f"  ❌ Failed to Add: {summary['failed_apollo']}")
        
        # Calculate conversion rates
        if summary['total_recruiters'] > 0:
            success_rate = (summary['added_to_apollo'] / summary['total_recruiters']) * 100
            print(f"\n📈 Conversion Rate: {success_rate:.1f}% recruiters added to Apollo")
        
        await conn.close()
        
    except Exception as e:
        print(f"Error getting pipeline summary: {e}")
        if conn:
            await conn.close()

async def main():
    """Main function to check all database tables"""
    print("🔍 LEAD GENERATOR DATABASE CHECKER")
    print("=" * 60)
    print(f"Checking database: {DB_CONFIG['database']} on {DB_CONFIG['host']}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Test connection first
    conn = await get_db_connection()
    if not conn:
        print("❌ Could not connect to database. Please check your connection.")
        return
    await conn.close()
    print("✅ Database connection successful!")
    
    # Check all tables
    await get_recruitment_pipeline_summary()
    await check_companies()
    await check_recruiters()
    await check_jobs()
    await check_processing_logs()
    
    print("\n" + "="*60)
    print("🎉 Database check completed!")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())
