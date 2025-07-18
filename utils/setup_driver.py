import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

from .find_chrome_binary import find_chrome_binary


def setup_driver(is_macos, chrome_user_data_dir, default_profile, chrome_binary_paths):
    """Setup Chrome driver with macOS-optimized configuration"""
    options = Options()

    # macOS-specific Chrome options
    if is_macos:
        # Use macOS Chrome profile path
        if os.path.exists(chrome_user_data_dir):
            print(os.listdir(chrome_user_data_dir))
            options.add_argument(f"--user-data-dir={chrome_user_data_dir}")
            options.add_argument(f"--profile-directory={default_profile}")
            options.add_argument("--remote-debugging-port=9222")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument(
                "--no-first-run --no-service-autorun --password-store=basic --no-default-browser-check"
            )

        # Find Chrome binary
        chrome_binary = find_chrome_binary(is_macos, chrome_binary_paths)
        if chrome_binary:
            options.binary_location = chrome_binary
            print(f"✅ Using Chrome binary: {chrome_binary}")

    try:
        driver_path = ChromeDriverManager().install()
        if "THIRD_PARTY_NOTICES" in driver_path or not driver_path.endswith("chromedriver"):
            driver_path = os.path.join(os.path.dirname(driver_path), "chromedriver")
            print(f"✅ Corrected ChromeDriver path: {driver_path}")

        print(f"🛠️  ChromeDriver path: {driver_path}")

        # Use ChromeDriverManager to automatically handle driver installation
        service = Service(driver_path)

        # Create driver instance
        driver = webdriver.Chrome(service=service, options=options)

 
        print("✅ Chrome driver setup successful")
        return driver

    except Exception as e:
        print(f"❌ Failed to launch Chrome: {e}")
        print("💡 Troubleshooting tips for macOS:")
        print("   - Ensure Google Chrome is installed in /Applications/")
        print("   - Try running: brew install --cask google-chrome")
        print(
            "   - Check Chrome permissions in System Preferences > Security & Privacy"
        )
        print("   - Close all Chrome instances before running the script")
        return None
