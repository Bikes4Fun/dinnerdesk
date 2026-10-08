from app.db.database import _postgres_sql


def test_postgres_sql_placeholders_and_date():
    sql, returning = _postgres_sql(
        "INSERT INTO plans (household_id, start_date, days, title, created_at) VALUES (?, date('now'), 7, 'This week', ?)"
    )
    assert "%s" in sql
    assert "?" not in sql
    assert "CURRENT_DATE" in sql
    assert "RETURNING id" in sql
    assert returning is True


def test_postgres_insert_or_ignore():
    sql, _ = _postgres_sql("INSERT OR IGNORE INTO recipe_tags (recipe_id, tag) VALUES (?, ?)")
    assert sql.startswith("INSERT INTO recipe_tags")
    assert "ON CONFLICT DO NOTHING" in sql


def test_postgres_on_conflict_parens():
    sql, returning = _postgres_sql(
        "INSERT INTO household_recipe_edits (household_id, recipe_id, name) VALUES (?, ?, ?) ON CONFLICT(household_id, recipe_id) DO UPDATE SET name = excluded.name"
    )
    assert "ON CONFLICT (" in sql
    assert returning is False
