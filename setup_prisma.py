#!/usr/bin/env python3
"""
Prisma setup script for the LinkedIn Lead Generator
This script initializes Prisma and generates the client
"""

import os
import subprocess
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)


def setup_database_url():
    """Setup DATABASE_URL environment variable"""
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5432')
    db_name = os.getenv('DB_NAME', 'postgres')
    db_user = os.getenv('DB_USER', 'postgres')
    db_password = os.getenv('DB_PASSWORD', 'Abcd$1234')

    database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

    # Set environment variable for Prisma
    os.environ['DATABASE_URL'] = database_url

    print(f"Database URL: {database_url}")
    return database_url


def install_prisma_cli():
    """Install Prisma CLI if not already installed"""
    try:
        # Check if prisma is available
        subprocess.run(['prisma', '--version'],
                       capture_output=True, check=True)
        print("Prisma CLI is already installed")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Installing Prisma CLI...")
        try:
            subprocess.run(['npm', 'install', '-g', 'prisma'], check=True)
            print("Prisma CLI installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"Failed to install Prisma CLI: {e}")
            print("Please install Node.js and npm first, then run: npm install -g prisma")
            return False
    return True


def generate_prisma_client():
    """Generate Prisma client"""
    try:
        print("Generating Prisma client...")
        result = subprocess.run(['prisma', 'generate'],
                                capture_output=True, text=True, check=True)
        print("Prisma client generated successfully")
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to generate Prisma client: {e}")
        print(f"Error output: {e.stderr}")
        return False


def run_database_migration():
    """Run database migration to create tables"""
    try:
        print("Running database migration...")
        result = subprocess.run(
            ['prisma', 'db', 'push'], capture_output=True, text=True, check=True)
        print("Database migration completed successfully")
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to run database migration: {e}")
        print(f"Error output: {e.stderr}")
        return False


def main():
    """Main setup function"""
    print("Setting up Prisma for LinkedIn Lead Generator...")

    # Setup database URL
    setup_database_url()

    # Install Prisma CLI
    if not install_prisma_cli():
        sys.exit(1)

    # Generate Prisma client
    if not generate_prisma_client():
        sys.exit(1)

    # Run database migration
    if not run_database_migration():
        sys.exit(1)

    print("\n✅ Prisma setup completed successfully!")
    print("You can now run the LinkedIn scraper with: python main.py")


if __name__ == "__main__":
    main()
