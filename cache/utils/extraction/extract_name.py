def extract_name(profile_text):
    """Extract clean name from profile text"""
    name = profile_text.replace("View ", "").strip()
    suffixes = ["'s profile", "'s verified profile", "' verified profile", "' profile"]
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    return name.strip()
