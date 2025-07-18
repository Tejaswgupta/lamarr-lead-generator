from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import json


def extract_company_details(driver):
    """Extract company details from LinkedIn company page"""
    try:
        wait = WebDriverWait(driver, 10)
        section = wait.until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    "//section[@class='artdeco-card org-page-details-module__card-spacing artdeco-card org-about-module__margin-bottom']",
                )
            )
        )
        company_details = {}
        dt_elements = section.find_elements(By.XPATH, ".//dt")
        for dt in dt_elements:
            dt_text = dt.text.strip()
            dd = dt.find_element(By.XPATH, "./following-sibling::dd[1]")
            dd_text = dd.text.strip()
            company_details[dt_text] = dd_text
        return json.dumps(company_details, indent=4)
    except Exception as e:
        print(f"Error extracting company details: {e}")
        return json.dumps({})
