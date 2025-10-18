#!/usr/bin/env python3
"""
Test script to verify Prisma implementation works correctly
"""

import os
import asyncio
import json
from dotenv import load_dotenv
from prisma import Prisma

# Load environment variables
load_dotenv(override=True)

# Test database connection and basic operations
async def test_prisma_connection():
    """Test basic Prisma connection and operations"""
    print("Testing Prisma connection...")

    # Initialize Prisma client
    client = Prisma()

    try:
        # Connect to database
        await client.connect()
        print("✅ Successfully connected to database via Prisma")

        # Test creating a company
        test_company = await client.company.create(
            data={
                'name': 'Test Company',
                'linkedinUrl': 'https://linkedin.com/company/test',
                'location': 'Test Location',
                'companyDomain': 'testcompany.com',
                'metadata': '{"test": true, "source": "prisma_test"}'
            }
        )
        print(f"✅ Created test company: {test_company.name} (ID: {test_company.id})")

        # Test creating a recruiter
        test_recruiter = await client.recruiter.create(
            data={
                'name': 'Test Recruiter',
                'linkedinUrl': 'https://linkedin.com/in/testrecruiter',
                'companyDomain': 'testcompany.com'
            }
        )
        print(f"✅ Created test recruiter: {test_recruiter.name} (ID: {test_recruiter.id})")

        # Test creating a job
        test_job = await client.job.create(
            data={
                'id': 999999999,  # Use a unique test ID
                'companyId': test_company.id,
                'recruiterId': test_recruiter.id,
                'title': 'Test Job Position',
                'description': 'This is a test job description',
                'roleMetadata': '{"posted_at": "2024-01-01", "applicants": "5 applicants"}'
            }
        )
        print(f"✅ Created test job: {test_job.title} (ID: {test_job.id})")

        # Test querying the data
        companies = await client.company.find_many()
        print(f"✅ Found {len(companies)} companies in database")

        recruiters = await client.recruiter.find_many()
        print(f"✅ Found {len(recruiters)} recruiters in database")

        jobs = await client.job.find_many()
        print(f"✅ Found {len(jobs)} jobs in database")

        # Clean up test data
        await client.job.delete(where={'id': test_job.id})
        await client.recruiter.delete(where={'id': test_recruiter.id})
        await client.company.delete(where={'id': test_company.id})
        print("✅ Cleaned up test data")

        print("\n🎉 All Prisma tests passed successfully!")
        return True

    except Exception as e:
        print(f"❌ Prisma test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Always disconnect
        await client.disconnect()
        print("✅ Disconnected from database")

def test_environment_variables():
    """Test that required environment variables are set"""
    print("Testing environment variables...")

    required_vars = ['DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD']
    missing_vars = []

    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        return False

    print("✅ All required environment variables are set")

    # Test DATABASE_URL construction
    database_url = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
    print(f"✅ DATABASE_URL constructed: {database_url}")

    # Set for Prisma
    os.environ['DATABASE_URL'] = database_url

    return True

async def main():
    """Main test function"""
    print("🧪 Testing Prisma Implementation for LinkedIn Lead Generator")
    print("=" * 60)

    # Test environment variables
    if not test_environment_variables():
        print("\n❌ Environment variable tests failed. Please check your .env file.")
        return

    print("\n" + "=" * 60)

    # Test Prisma connection and operations
    if await test_prisma_connection():
        print("\n✅ All tests passed! Prisma implementation is working correctly.")
        print("\nYou can now run the LinkedIn scraper with:")
        print("python main.py")
    else:
        print("\n❌ Prisma tests failed. Please check your database connection and Prisma setup.")
        print("\nTroubleshooting steps:")
        print("1. Ensure PostgreSQL is running")
        print("2. Check database credentials in .env file")
        print("3. Run 'python setup_prisma.py' to initialize Prisma")
        print("4. Run 'npm run db:push' to create database tables")

if __name__ == "__main__":
    asyncio.run(main())