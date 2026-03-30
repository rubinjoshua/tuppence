"""AI categorization service with caching"""

from sqlalchemy.orm import Session
from openai import OpenAI
from pydantic import BaseModel

from app.config import settings
from app.models.text_category_cache import TextCategoryCache
from app.utils.text_cleaning import clean_text
from app.utils.categories import PREDEFINED_CATEGORIES


class CategoryResponse(BaseModel):
    """Pydantic model for OpenAI structured output"""
    category: str


async def get_or_create_category(text: str, db: Session) -> str:
    """
    Get category for spending text, using cache or OpenAI API.

    Process:
    1. Return "Miscellaneous" if text is empty
    2. Clean text (lowercase, no punctuation)
    3. Check cache for exact match
    4. If cache miss, call OpenAI gpt-4o-mini
    5. Cache result for future lookups
    6. Return category name

    Args:
        text: Raw spending description text from user
        db: Database session

    Returns:
        Category name (one of PREDEFINED_CATEGORIES)

    Note:
        Caching dramatically reduces OpenAI API costs for repeated spending patterns.
    """
    # Handle empty text
    if not text or not text.strip():
        return "Miscellaneous"

    # Clean text for cache lookup
    cleaned = clean_text(text)

    if not cleaned:
        return "Miscellaneous"

    # Check cache first
    cached = db.query(TextCategoryCache).filter_by(cleaned_text=cleaned).first()
    if cached:
        return cached.category_name

    # Cache miss - call OpenAI API
    category = await categorize_with_openai(text)

    # Cache the result
    cache_entry = TextCategoryCache(
        cleaned_text=cleaned,
        category_name=category
    )
    db.add(cache_entry)
    db.commit()

    return category


async def categorize_with_openai(text: str) -> str:
    """
    Categorize spending text using OpenAI gpt-4o-mini.

    Uses structured output (Pydantic BaseModel) to ensure valid category response.

    Args:
        text: Raw spending description text

    Returns:
        Category name from PREDEFINED_CATEGORIES

    Note:
        Uses gpt-4o-mini for cost efficiency (~$0.00015 per categorization).
    """
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    # Create category list string for prompt
    categories_str = ", ".join(PREDEFINED_CATEGORIES)

    try:
        completion = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": f"You are a spending categorization assistant. Categorize the user's spending into exactly one of these categories: {categories_str}. Choose the most appropriate category. If unsure, choose 'Miscellaneous'."
                },
                {
                    "role": "user",
                    "content": f"Categorize this spending: {text}"
                }
            ],
            response_format=CategoryResponse
        )

        category = completion.choices[0].message.parsed.category

        # Validate category is in predefined list
        if category not in PREDEFINED_CATEGORIES:
            return "Miscellaneous"

        return category

    except Exception as e:
        # Fallback to Miscellaneous on API errors
        print(f"OpenAI API error: {e}")
        return "Miscellaneous"
