import os
import time
from typing import Optional, Tuple

import pyautogui
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from .find_chrome_binary import find_chrome_binary


class ExtensionClicker:
    """Handles Chrome setup with preset profile and extension clicking functionality"""

    def __init__(
        self,
        is_macos: bool = True,
        chrome_user_data_dir: str = None,
        default_profile: str = "Profile 1",
        chrome_binary_paths: str = None,
    ):
        """
        Initialize the ExtensionClicker

        Args:
            is_macos: Whether running on macOS
            chrome_user_data_dir: Path to Chrome user data directory
            default_profile: Chrome profile to use
            chrome_binary_paths: Path to Chrome binary
        """
        self.is_macos = is_macos
        self.chrome_user_data_dir = chrome_user_data_dir
        self.default_profile = default_profile
        self.chrome_binary_paths = chrome_binary_paths
        self.driver: Optional[webdriver.Chrome] = None

    def setup_chrome_with_profile(self) -> bool:
        """
        Setup Chrome driver with preset profile

        Returns:
            bool: True if setup successful, False otherwise
        """
        try:
            options = Options()

            # macOS-specific Chrome options
            if self.is_macos:
                # Use macOS Chrome profile path
                if os.path.exists(self.chrome_user_data_dir):
                    print(f"📁 Using Chrome profile: {self.chrome_user_data_dir}")
                    options.add_argument(f"--user-data-dir={self.chrome_user_data_dir}")
                    options.add_argument(f"--profile-directory={self.default_profile}")
                    options.add_argument("--remote-debugging-port=9222")
                    options.add_argument(
                        "--disable-blink-features=AutomationControlled"
                    )
                    options.add_argument("--window-size=1200,800")
                    options.add_argument(
                        "--no-first-run --no-service-autorun --password-store=basic --no-default-browser-check"
                    )
                else:
                    print(
                        f"⚠️  Chrome user data directory not found: {self.chrome_user_data_dir}"
                    )
                    return False

                # Find Chrome binary
                chrome_binary = find_chrome_binary(
                    self.is_macos, self.chrome_binary_paths
                )
                if chrome_binary:
                    options.binary_location = chrome_binary
                    print(f"✅ Using Chrome binary: {chrome_binary}")
                else:
                    print("❌ Chrome binary not found")
                    return False

            # Setup ChromeDriver
            driver_path = ChromeDriverManager().install()
            if "THIRD_PARTY_NOTICES" in driver_path or not driver_path.endswith(
                "chromedriver"
            ):
                driver_path = os.path.join(os.path.dirname(driver_path), "chromedriver")
                print(f"✅ Corrected ChromeDriver path: {driver_path}")

            service = Service(driver_path)
            self.driver = webdriver.Chrome(service=service, options=options)

            print("✅ Chrome driver setup successful with preset profile")
            return True

        except Exception as e:
            print(f"❌ Failed to setup Chrome driver: {e}")
            return False

    def click_extension_coordinates(
        self,
        x: int,
        y: int,
        clicks: int = 1,
        delay: float = 0.2,
        wait_after: float = 1.0,
    ) -> bool:
        """
        Click on predefined x,y coordinates for extension

        Args:
            x: X coordinate to click
            y: Y coordinate to click
            clicks: Number of clicks to perform
            delay: Delay before clicking
            wait_after: Wait time after clicking

        Returns:
            bool: True if click successful, False otherwise
        """
        try:
            print(f"🖱️  Moving mouse to ({x}, {y}) and clicking {clicks} time(s)...")

            # Move to coordinates with smooth animation
            pyautogui.moveTo(x, y, duration=delay)

            # Perform clicks
            for i in range(clicks):
                pyautogui.click()
                if i < clicks - 1:  # Don't sleep after the last click
                    time.sleep(0.1)

            print(f"✅ Successfully clicked at ({x}, {y})")
            time.sleep(wait_after)
            return True

        except Exception as e:
            print(f"❌ Failed to click at ({x}, {y}): {e}")
            return False

    def click_multiple_coordinates(
        self,
        coordinates: list[Tuple[int, int]],
        clicks_per_coord: int = 1,
        delay: float = 0.2,
    ) -> bool:
        """
        Click on multiple predefined coordinates

        Args:
            coordinates: List of (x, y) coordinate tuples
            clicks_per_coord: Number of clicks per coordinate
            delay: Delay between coordinates

        Returns:
            bool: True if all clicks successful, False otherwise
        """
        try:
            print(f"🎯 Clicking on {len(coordinates)} coordinates...")

            for i, (x, y) in enumerate(coordinates, 1):
                print(f"📍 Coordinate {i}/{len(coordinates)}: ({x}, {y})")

                if not self.click_extension_coordinates(x, y, clicks_per_coord, delay):
                    print(f"❌ Failed at coordinate {i}")
                    return False

                if i < len(coordinates):  # Don't delay after the last coordinate
                    time.sleep(delay)

            print("✅ All coordinates clicked successfully")
            return True

        except Exception as e:
            print(f"❌ Error clicking multiple coordinates: {e}")
            return False

    def get_mouse_position(self) -> Tuple[int, int]:
        """
        Get current mouse position for debugging

        Returns:
            Tuple[int, int]: Current (x, y) mouse coordinates
        """
        x, y = pyautogui.position()
        print(f"📍 Current mouse position: ({x}, {y})")
        return (x, y)

    def close_driver(self) -> None:
        """Close the Chrome driver"""
        if self.driver:
            try:
                self.driver.quit()
                print("🔒 Chrome driver closed successfully")
            except Exception as e:
                print(f"⚠️  Error closing driver: {e}")
            finally:
                self.driver = None


def create_extension_clicker(
    is_macos: bool = True,
    chrome_user_data_dir: str = "/Users/tejasw/Library/Application Support/Google/Chrome/",
    default_profile: str = "Profile 1",
    chrome_binary_paths: str = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
) -> ExtensionClicker:
    """
    Factory function to create an ExtensionClicker instance with default macOS settings

    Args:
        is_macos: Whether running on macOS
        chrome_user_data_dir: Path to Chrome user data directory
        default_profile: Chrome profile to use
        chrome_binary_paths: Path to Chrome binary

    Returns:
        ExtensionClicker: Configured ExtensionClicker instance
    """
    return ExtensionClicker(
        is_macos=is_macos,
        chrome_user_data_dir=chrome_user_data_dir,
        default_profile=default_profile,
        chrome_binary_paths=chrome_binary_paths,
    )
