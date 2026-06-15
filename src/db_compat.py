from __future__ import annotations


def ensure_runtime_compat(storage) -> None:
    """Create compatibility views needed by older method logic.

    Some method code still reads `fvgs`, while the current DB schema stores active
    gaps in `active_fvgs`. This keeps old logic readable without changing live
    tables or deleting data.
    """
    try:
        conn = storage.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view') AND name='active_fvgs'")
        has_active = bool(cur.fetchone())
        cur.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view') AND name='fvgs'")
        has_fvgs = bool(cur.fetchone())
        if has_active and not has_fvgs:
            cur.execute("CREATE VIEW IF NOT EXISTS fvgs AS SELECT * FROM active_fvgs")
        conn.commit()
        conn.close()
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
