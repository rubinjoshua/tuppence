"""Text cleaning utilities for categorization caching"""

import re


def clean_text(text: str) -> str:
    """
    Clean text for categorization cache lookup.

    Process:
    1. Convert to lowercase
    2. Remove punctuation
    3. Collapse multiple spaces
    4. Strip leading/trailing spaces

    Args:
        text: Raw text from user spending description

    Returns:
        Cleaned text for cache matching

    Examples:
        "Whole Foods, milk & eggs!" -> "whole foods milk eggs"
        "Coffee @ Starbucks..." -> "coffee starbucks"
    """
    if not text:
        return ""

    # Convert to lowercase
    text = text.lower()

    # Remove all punctuation (keep only alphanumeric and spaces)
    text = re.sub(r'[^\w\s]', '', text)

    # Collapse multiple spaces into one
    text = re.sub(r'\s+', ' ', text)

    # Strip leading/trailing spaces
    return text.strip()
