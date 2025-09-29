from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException


def check_for_captcha(driver):
    """Check and handle CAPTCHA if present"""
    try:
        captcha_element = driver.find_element(By.XPATH, "/html/body/div/main/h1")
        if captcha_element:
            print(
                "CAPTCHA detected. Please solve the CAPTCHA and press Enter to continue..."
            )
            input("Press Enter after solving the CAPTCHA...")
    except NoSuchElementException:
        pass
