from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import DATABASE_URL
class Base(DeclarativeBase):
    pass
engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False, 'timeout': 30})
SessionLocal = sessionmaker(bind=engine)


def migrate_legacy_database():
    """Attach pre-auth single-user data to the local demo account."""
    inspector = inspect(engine)
    if 'users' not in inspector.get_table_names():
        return
    with engine.begin() as conn:
        demo_id = conn.execute(text("SELECT id FROM users WHERE email='demo@aquavest.local'")).scalar()
        if demo_id is None:
            return
        for table in ('holdings', 'transactions', 'watchlist'):
            if table not in inspect(conn).get_table_names():
                continue
            cols = {c['name'] for c in inspect(conn).get_columns(table)}
            if 'user_id' not in cols:
                conn.execute(text(f'ALTER TABLE {table} ADD COLUMN user_id INTEGER'))
            conn.execute(text(f'UPDATE {table} SET user_id=:uid WHERE user_id IS NULL'), {'uid': demo_id})
        # Legacy tables used a global UNIQUE(symbol), which would prevent accounts
        # from holding the same stock. Rebuild those two tables with account-scoped keys.
        for table, model in (('holdings', 'holdings'), ('watchlist', 'watchlist')):
            cols = {c['name'] for c in inspect(conn).get_columns(table)} if table in inspect(conn).get_table_names() else set()
            if not cols or 'user_id' not in cols:
                continue
            indexes = inspect(conn).get_unique_constraints(table)
            has_global_unique = any(c.get('column_names') == ['symbol'] for c in indexes)
            if not has_global_unique:
                continue
            old = table + '_legacy'
            conn.execute(text(f'ALTER TABLE {table} RENAME TO {old}'))
            from .models import Holding, WatchlistItem
            target = Holding if model == 'holdings' else WatchlistItem
            target.__table__.create(conn)
            if model == 'holdings':
                conn.execute(text(f'''INSERT INTO holdings (id,user_id,symbol,company_name,sector,quantity,average_price)
                    SELECT id,user_id,symbol,company_name,sector,quantity,average_price FROM {old}'''))
            else:
                conn.execute(text(f'INSERT INTO watchlist (id,user_id,symbol) SELECT id,user_id,symbol FROM {old}'))
            conn.execute(text(f'DROP TABLE {old}'))
        for table in ('holdings', 'transactions', 'watchlist'):
            if table in inspect(conn).get_table_names():
                conn.execute(text(f'CREATE INDEX IF NOT EXISTS ix_{table}_user_id ON {table}(user_id)'))
def get_db():
    with SessionLocal() as db:
        yield db
