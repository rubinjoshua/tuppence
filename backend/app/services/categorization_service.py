"""AI categorization service with caching"""

from hashlib import sha256

from sqlalchemy.orm import Session
from openai import OpenAI
from pydantic import BaseModel

from app.config import settings
from app.models.settings import Settings as SettingsModel
from app.models.text_category_cache import TextCategoryCache
from app.utils.text_cleaning import clean_text
from app.utils.categories import PREDEFINED_CATEGORIES


# Seed rules used when a household hasn't customised its own. Households edit
# these from the app's Settings screen; the edited text is stored per-household
# and shared with all members (see `get_household_rules`).
DEFAULT_CATEGORIZATION_RULES = (
    "# Spending categorization rules\n"
    "\n"
    "- Categorize anything mentioning \"baby\" or the child's name \"Dileyla\", "
    "\"Dilly\", or \"Dily\" as `Baby`.\n"
    "- Do not categorize snacks as `Groceries`."
)


def get_household_rules(db: Session, household_id) -> str:
    """Return the categorization rules text in effect for a household.

    Falls back to DEFAULT_CATEGORIZATION_RULES when the household has no
    settings row yet or hasn't overridden the rules.
    """
    settings_row = db.query(SettingsModel).filter_by(household_id=household_id).first()
    if settings_row and settings_row.categorization_rules is not None:
        return settings_row.categorization_rules
    return DEFAULT_CATEGORIZATION_RULES


def _rules_version(rules: str) -> str:
    """Short content hash of the rules, used to namespace the cache so a
    rules change can't return classifications made under older rules."""
    return sha256(rules.encode()).hexdigest()[:12]


class CategoryResponse(BaseModel):
    """Pydantic model for OpenAI structured output"""
    category: str


async def get_or_create_category(text: str, db: Session, rules: str) -> str:
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
        rules: Household's categorization rules text (fetched via
            get_household_rules)

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

    # A rules change gets a new cache namespace so stale classifications
    # cannot override rules added later. Keep within the column's 500-char max.
    cache_key = f"{cleaned[:480]}|rules:{_rules_version(rules)}"
    cached = db.query(TextCategoryCache).filter_by(cleaned_text=cache_key).first()
    if cached:
        return cached.category_name

    # Cache miss - call OpenAI API
    category = await categorize_with_openai(text, rules)

    # Cache the result
    cache_entry = TextCategoryCache(
        cleaned_text=cache_key,
        category_name=category
    )
    db.add(cache_entry)
    db.commit()

    return category


async def categorize_with_openai(text: str, rules: str) -> str:
    """
    Categorize spending text using OpenAI gpt-4o-mini.

    Uses structured output (Pydantic BaseModel) to ensure valid category response.

    Args:
        text: Raw spending description text
        rules: Household's categorization rules text injected into the prompt

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
                    "content": (
                        "You are a spending categorization assistant. Categorize the user's "
                        f"spending into exactly one of these categories: {categories_str}. "
                        "Choose the most appropriate category. If unsure, choose 'Miscellaneous'.\n\n"
                        f"Additional categorization rules:\n{rules}"
                    )
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
