#!/usr/bin/env python3
"""
Example usage of the ExtensionClicker class for Chrome profile setup and extension clicking
"""

import asyncio

from utils.extension_clicker import create_extension_clicker


async def main():
    """Example of using ExtensionClicker to setup Chrome and click extension coordinates"""

    print("🚀 Extension Clicker Example")
    print("=" * 40)

    # Create ExtensionClicker instance with default macOS settings
    clicker = create_extension_clicker()

    try:
        # Setup Chrome with preset profile
        print("🔧 Setting up Chrome with preset profile...")
        if not clicker.setup_chrome_with_profile():
            print("❌ Failed to setup Chrome. Exiting...")
            return

        print("✅ Chrome setup successful!")

        # Example: Click on a single extension coordinate
        print("\n🎯 Example 1: Single coordinate click")
        extension_x, extension_y = 100, 100  # Replace with your extension coordinates
        if clicker.click_extension_coordinates(extension_x, extension_y, clicks=1):
            print("✅ Single click successful!")

        # Example: Click on multiple extension coordinates
        print("\n🎯 Example 2: Multiple coordinates click")
        extension_coordinates = [
            (150, 150),  # Replace with your actual extension coordinates
            (200, 200),
            (250, 250),
        ]
        if clicker.click_multiple_coordinates(
            extension_coordinates, clicks_per_coord=1
        ):
            print("✅ Multiple clicks successful!")

        # Example: Get current mouse position for debugging
        print("\n📍 Example 3: Get mouse position")
        current_pos = clicker.get_mouse_position()
        print(f"Current position: {current_pos}")

        # Wait a bit before closing
        print("\n⏳ Waiting 3 seconds before closing...")
        await asyncio.sleep(3)

    except KeyboardInterrupt:
        print("\n⏹️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        # Always close the driver
        clicker.close_driver()
        print("✅ Example completed!")


if __name__ == "__main__":
    asyncio.run(main())
