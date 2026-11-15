import sqlalchemy as sa

from mealie.core.config import get_app_settings
from mealie.db import personal_migrations
from mealie.db.models._model_base import SqlAlchemyBase
from tests.utils.alembic_reader import alembic_versions


def table_names() -> set[str]:
    engine = sa.create_engine(get_app_settings().DB_URL)
    try:
        with engine.connect() as connection:
            return set(sa.inspect(connection).get_table_names())
    finally:
        engine.dispose()


def core_version() -> list[str]:
    engine = sa.create_engine(get_app_settings().DB_URL)
    try:
        with engine.connect() as connection:
            return [row[0] for row in connection.execute(sa.text("SELECT version_num FROM alembic_version"))]
    finally:
        engine.dispose()


def test_every_personal_model_has_the_table_prefix():
    import mealie.db.models.personal as personal

    for name in personal.__all__:
        assert getattr(personal, name).__tablename__.startswith(personal_migrations.TABLE_PREFIX)


def test_personal_tables_exist_after_startup():
    expected = {name for name in SqlAlchemyBase.metadata.tables if name.startswith(personal_migrations.TABLE_PREFIX)}
    assert len(expected) == 23
    assert expected <= table_names()
    assert personal_migrations.current_version() == "pe0003"


def test_personal_migrations_leave_the_history_of_mealie_alone():
    # Mealie records its own version only: an unmodified Mealie can read this database.
    assert core_version() == [row["version_num"] for row in alembic_versions()]


def test_downgrade_removes_every_personal_table_and_nothing_else():
    before = table_names()
    core_tables = {name for name in before if not name.startswith(personal_migrations.TABLE_PREFIX)}
    version_before = core_version()

    try:
        personal_migrations.downgrade("base")
        after = table_names()

        assert not any(name.startswith(personal_migrations.TABLE_PREFIX) for name in after)
        assert core_tables <= after
        assert core_version() == version_before
        assert personal_migrations.current_version() is None
    finally:
        personal_migrations.upgrade()

    assert table_names() == before
    assert personal_migrations.current_version() == "pe0003"


def test_restore_hook_ignores_a_backup_of_an_unmodified_mealie():
    personal_migrations.upgrade_for_restore({"alembic_version": [{"version_num": "f3a1ae61d772"}]})
    personal_migrations.upgrade_for_restore({personal_migrations.VERSION_TABLE: []})
    assert personal_migrations.current_version() == "pe0003"
