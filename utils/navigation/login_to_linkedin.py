from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import time


def login_to_linkedin(driver, linkedin_username, linkedin_password):
    """Login to LinkedIn account"""
    driver.get("https://www.linkedin.com/uas/login")

    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "username"))
        )

        username = driver.find_element(By.ID, "username")
        username.send_keys(linkedin_username)

        password = driver.find_element(By.ID, "password")
        password.send_keys(linkedin_password)

        driver.find_element(By.XPATH, "//button[@type='submit']").click()
        time.sleep(3)

        # Check for CAPTCHA
        check_for_captcha(driver)
    except Exception as e:
        print(f"Error during LinkedIn login: {e}")
        if "username" in str(e).lower():
            print("Already logged in, continuing...")
