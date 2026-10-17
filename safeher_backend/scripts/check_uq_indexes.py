from app.db.session import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    rows = db.execute(
        text("SELECT indexname FROM pg_indexes WHERE indexname LIKE 'uq_%' ORDER BY 1")
    ).fetchall()
    print("indexes:", [r[0] for r in rows])
finally:
    db.close()
