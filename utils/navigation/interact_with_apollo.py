from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
import time
from .click_x_y import click_on_x_y


def interact_with_apollo_icon(driver):
    try:
        print("[STEP 1] Locating Apollo icon...")
        apollo_element = driver.find_element(By.CLASS_NAME, "x_IFkFs")

        # Hover over the element
        print("[STEP 2] Hovering over Apollo icon...")
        actions = ActionChains(driver)
        actions.move_to_element(apollo_element).perform()

        # Move and click 10 pixels to the left of the center
        print("[STEP 3] Clicking offset left of Apollo icon...")
        actions.move_to_element_with_offset(apollo_element, -10, 0).click().perform()
        time.sleep(2)  # Wait for sidebar to load

        return True

    except Exception as e:
        print(f"[ERROR] Apollo interaction failed: {e}")
        return False


def interact_with_apollo(driver, linkedin_url):
    try:
        print("[INFO] Opening new tab...")
        driver.execute_script("window.open('');")
        driver.switch_to.window(driver.window_handles[1])
        driver.get(linkedin_url)
        time.sleep(3)
        interact_with_apollo_icon(driver)
        add_to_sequence_success = click_on_x_y(700, 500, 2, True)
        sent_sequence_success = click_on_x_y(700, 550, 1)
        added_sequence_success = click_on_x_y(700, 730, 1)

        time.sleep(1)
        return added_sequence_success

    except Exception as e:
        print(f"[CRITICAL ERROR] Apollo interaction failed: {e}")
        driver.save_screenshot("apollo_click_error.png")
        return False
    finally:
        # Always close the tab and switch back to the original window
        try:
            if len(driver.window_handles) > 1:
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
        except Exception as e:
            print(f"[WARN] Error closing Apollo tab: {e}")
