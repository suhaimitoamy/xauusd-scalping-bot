import argparse
import sys
import os

# Add project root to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.storage import Storage

def main():
    parser = argparse.ArgumentParser(description="Boost AI Pattern Confidence (Reset Trauma)")
    parser.add_argument("--pattern", required=True, help="Pattern key (or 'ALL' to reset all negative patterns)")
    parser.add_argument("--score", type=float, default=0.0, help="Score to set (e.g. 0 to reset trauma, 20 to boost)")
    args = parser.parse_args()

    storage = Storage()
    conn = storage.get_connection()
    cur = conn.cursor()

    if args.pattern.upper() == 'ALL':
        cur.execute("UPDATE brain_patterns SET score = ? WHERE score < ?", (args.score, args.score))
        count = cur.rowcount
        conn.commit()
        print(f"✅ Berhasil me-reset {count} pattern yang trauma menjadi skor {args.score}.")
    else:
        cur.execute("SELECT * FROM brain_patterns WHERE pattern_key=?", (args.pattern,))
        row = cur.fetchone()
        if not row:
            print(f"❌ Pattern '{args.pattern}' tidak ditemukan di memori bot.")
            print("💡 Cek nama pattern dari log simulator atau pesan Telegram.")
        else:
            cur.execute("UPDATE brain_patterns SET score = ? WHERE pattern_key = ?", (args.score, args.pattern))
            conn.commit()
            print(f"✅ Berhasil menyuntikkan skor {args.score} ke pattern '{args.pattern}'.")
            
    conn.close()

if __name__ == "__main__":
    main()
