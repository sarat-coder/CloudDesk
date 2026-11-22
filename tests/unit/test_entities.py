from __future__ import annotations

from app.models.entities import Base, TABLES
from app.schemas.common import Category


def test_all_tables_present():
    """All 16 tables from CLAUDE.md §6 are defined in Base.metadata."""
    actual = set(Base.metadata.tables.keys())
    expected = set(TABLES)
    assert expected == actual, f"Missing tables: {expected - actual}"


def test_table_count():
    """Exactly 16 tables are defined (§6 authority)."""
    assert len(Base.metadata.tables) == 16


def test_category_enum_has_ten_values():
    """Category enum has exactly 10 values as specified in CLAUDE.md §5."""
    assert len(Category) == 10


def test_category_enum_values():
    expected = {
        "login_issue", "billing", "api_failure", "workspace_permissions",
        "storage_quota", "integration", "feature_request", "account",
        "security", "other",
    }
    actual = {c.value for c in Category}
    assert expected == actual


def test_tables_constant_matches_metadata():
    """TABLES list and Base.metadata are consistent."""
    assert sorted(TABLES) == sorted(Base.metadata.tables.keys())
