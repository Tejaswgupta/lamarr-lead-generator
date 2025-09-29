from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import time


def scroll_to_parent_ul(driver, li_class_name):
    """Scroll to load all list items in a parent container"""
    try:
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, li_class_name)))

        items = driver.find_elements(By.CLASS_NAME, li_class_name)
        prev_count = len(items)

        max_attempts = 10
        attempts = 0

        while attempts < max_attempts:
            if items:
                last_item = items[-1]
                driver.execute_script("arguments[0].scrollIntoView(true);", last_item)
            time.sleep(2)

            items = driver.find_elements(By.CLASS_NAME, li_class_name)
            current_count = len(items)
            print(f"Found {current_count} items after scrolling")

            if current_count == prev_count:
                attempts += 1
            else:
                attempts = 0
            prev_count = current_count

        return items
    except Exception as e:
        print(f"Error scrolling to parent ul: {e}")
        return []
