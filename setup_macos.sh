#!/bin/bash

# macOS Setup Script for LinkedIn Lead Generator
echo "🍎 macOS Setup for LinkedIn Lead Generator"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Check if running on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    print_error "This script is designed for macOS only."
    exit 1
fi

print_info "Checking system requirements..."

# Check if Homebrew is installed
if ! command -v brew &> /dev/null; then
    print_warning "Homebrew not found. Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # Add Homebrew to PATH
    echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
    eval "$(/opt/homebrew/bin/brew shellenv)"
else
    print_status "Homebrew is already installed"
fi

# Update Homebrew
print_info "Updating Homebrew..."
brew update

# Install Python 3 if not already installed
if ! command -v python3 &> /dev/null; then
    print_warning "Python 3 not found. Installing Python 3..."
    brew install python
else
    print_status "Python 3 is already installed"
fi

# Install Google Chrome if not already installed
if [ ! -d "/Applications/Google Chrome.app" ]; then
    print_warning "Google Chrome not found. Installing Google Chrome..."
    brew install --cask google-chrome
else
    print_status "Google Chrome is already installed"
fi

# Check if pip is available
if ! command -v pip3 &> /dev/null; then
    print_warning "pip3 not found. Installing pip..."
    python3 -m ensurepip --upgrade
else
    print_status "pip3 is available"
fi

# Install Python dependencies
print_info "Installing Python dependencies..."
if [ -f "requirements.txt" ]; then
    pip3 install -r requirements.txt
    print_status "Python dependencies installed from requirements.txt"
else
    print_info "requirements.txt not found. Installing essential packages..."
    pip3 install selenium webdriver-manager python-dotenv supabase asyncio
    print_status "Essential Python packages installed"
fi

# Create .env file template if it doesn't exist
if [ ! -f ".env" ]; then
    print_info "Creating .env template file..."
    cat > .env << EOL
# Supabase Configuration
SUPABASE_URL=your_supabase_url_here
SUPABASE_KEY=your_supabase_key_here

# LinkedIn Credentials
LINKEDIN_USERNAME=your_linkedin_email_here
LINKEDIN_PASSWORD=your_linkedin_password_here
EOL
    print_warning ".env file created. Please edit it with your actual credentials."
    print_info "Edit the .env file: nano .env"
else
    print_status ".env file already exists"
fi

# Check Chrome profile directory
CHROME_PROFILE_DIR="$HOME/Library/Application Support/Google/Chrome/"
if [ -d "$CHROME_PROFILE_DIR" ]; then
    print_status "Chrome profile directory found"
else
    print_warning "Chrome profile directory not found. Please open Chrome at least once to create the profile."
fi

# Create a simple test script
print_info "Creating test script..."
cat > test_setup.py << 'EOL'
#!/usr/bin/env python3
"""
Simple test script to verify macOS setup for LinkedIn Lead Generator
"""
import sys
import os
import platform

def test_imports():
    """Test if all required packages can be imported"""
    try:
        import selenium
        import webdriver_manager
        import dotenv
        import supabase
        import asyncio
        print("✅ All Python packages imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_chrome():
    """Test if Chrome is available"""
    chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if os.path.exists(chrome_path):
        print("✅ Google Chrome found")
        return True
    else:
        print("❌ Google Chrome not found")
        return False

def test_chrome_profile():
    """Test if Chrome profile directory exists"""
    profile_dir = os.path.expanduser("~/Library/Application Support/Google/Chrome/")
    if os.path.exists(profile_dir):
        print("✅ Chrome profile directory found")
        return True
    else:
        print("⚠️  Chrome profile directory not found (open Chrome once to create)")
        return False

def test_env_file():
    """Test if .env file exists"""
    if os.path.exists(".env"):
        print("✅ .env file found")
        return True
    else:
        print("❌ .env file not found")
        return False

def main():
    print("🧪 Testing macOS setup for LinkedIn Lead Generator")
    print("=" * 50)
    print(f"🍎 Running on: {platform.system()} {platform.release()}")
    print(f"🐍 Python version: {sys.version}")
    print()
    
    tests = [
        test_imports,
        test_chrome,
        test_chrome_profile,
        test_env_file
    ]
    
    passed = 0
    for test in tests:
        if test():
            passed += 1
        print()
    
    print(f"📊 Test Results: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("🎉 Setup complete! You're ready to run the LinkedIn Lead Generator.")
    else:
        print("⚠️  Some tests failed. Please review the output above and fix any issues.")

if __name__ == "__main__":
    main()
EOL

chmod +x test_setup.py
print_status "Test script created: test_setup.py"

# Final instructions
echo
echo "🎉 Setup Complete!"
echo "=================="
print_info "Next steps:"
echo "1. Edit your .env file with actual credentials: nano .env"
echo "2. Run the test script: python3 test_setup.py"
echo "3. If tests pass, run the main script: python3 final_main.py"
echo
print_warning "Important macOS Security Notes:"
echo "- Chrome may ask for permissions the first time"
echo "- You might need to allow the script in System Preferences > Security & Privacy"
echo "- If you encounter permission issues, try running Chrome manually first"
echo
print_status "Setup script completed successfully!" 