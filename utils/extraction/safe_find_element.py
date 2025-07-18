def safe_find_element(driver, by, selector):
    """Safely find an element without raising exceptions"""
    try:
        return driver.find_element(by, selector)
    except Exception:
        return None
