"""Category table - Predefined spending categories"""

from sqlalchemy import Column, Integer, String

from app.database import Base


class Category(Base):
    """
    Category table storing predefined spending categories.

    150 categories seeded on database initialization with Wes Anderson-inspired colors.

    Schema:
        - id: Primary key (autoincrement)
        - category_name: Category display name (e.g., "Groceries", "Transportation")
        - hex_color: Wes Anderson pastel color code (e.g., "#D9CA94")

    Note:
        This table is read-only after initial seeding.
        Categories are used for AI categorization and pie chart visualization.
    """

    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category_name = Column(String(100), nullable=False, unique=True, index=True)
    hex_color = Column(String(7), nullable=False)  # Format: #RRGGBB

    def __repr__(self):
        return f"<Category(name={self.category_name}, color={self.hex_color})>"
