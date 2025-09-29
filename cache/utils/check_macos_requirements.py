import os

from .find_chrome_binary import find_chrome_binary


def check_macos_requirements(
    IS_MACOS, CHROME_USER_DATA_DIR, DEFAULT_PROFILE, CHROME_BINARY_PATHS
):
    """Check macOS-specific requirements"""
    if not IS_MACOS:
        print(
            "⚠️  This script is optimized for macOS but will attempt to run on your system"
        )
        return True

    print("🍎 Running on macOS - performing system checks...")

    # Check if Chrome is installed
    chrome_binary = find_chrome_binary(IS_MACOS, CHROME_BINARY_PATHS)
    if not chrome_binary:
        print("❌ Google Chrome not found in standard locations")
        print("💡 Install Chrome: brew install --cask google-chrome")
        print("   Or download from: https://www.google.com/chrome/")
        return False

    # Check Chrome profile directory
    if not os.path.exists(CHROME_USER_DATA_DIR):
        print("⚠️  Chrome user data directory not found")
        print(f"   Expected: {CHROME_USER_DATA_DIR}")
        print("   This might be normal for first-time Chrome users")
    else:
        print(f"✅ Chrome profile directory found: {CHROME_USER_DATA_DIR}")

    # Check for Chrome permissions (common macOS issue)
    try:
        # Try to read Chrome preferences to check permissions
        prefs_path = os.path.join(CHROME_USER_DATA_DIR, DEFAULT_PROFILE, "Preferences")
        if os.path.exists(prefs_path):
            with open(prefs_path, "r") as f:
                f.read(100)  # Just read a small portion to test permissions
            print("✅ Chrome profile permissions OK")
    except (PermissionError, FileNotFoundError):
        print("⚠️  Chrome profile access issues detected")
        print(
            "   You may need to grant permissions in System Preferences > Security & Privacy"
        )

    print("✅ macOS requirements check completed")
    return True
