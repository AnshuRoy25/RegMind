from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Every table class inherits from this."""
    pass