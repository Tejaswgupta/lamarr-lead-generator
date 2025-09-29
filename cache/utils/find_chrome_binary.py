def find_chrome_binary(is_macos, chrome_binary_paths):
    """Find Chrome binary on macOS"""
    if not is_macos:
        return None

    return chrome_binary_paths
