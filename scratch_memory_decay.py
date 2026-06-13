import sqlite3
import os

DB_PATH = "data/xauusd_bot.sqlite"

def apply_memory_decay():
    if not os.path.exists(DB_PATH):
        print("Database tidak ditemukan.")
        return
        
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Ambil semua pattern
    cur.execute("SELECT pattern_key, wins, losses FROM brain_patterns")
    patterns = cur.fetchall()
    
    decay_factor = 0.9  # Kurangi 10% setiap hari
    
    for row in patterns:
        pattern_key = row[0]
        wins = int(row[1])
        losses = int(row[2])
        
        # Terapkan decay
        new_wins = int(wins * decay_factor)
        new_losses = int(losses * decay_factor)
        
        cur.execute('''
            UPDATE brain_patterns 
            SET wins = ?, losses = ?
            WHERE pattern_key = ?
        ''', (new_wins, new_losses, pattern_key))
        
    conn.commit()
    conn.close()
    print(f"Memory Decay diterapkan pada {len(patterns)} metode. Otak bot telah 'melupakan' sedikit kegagalan masa lalu agar tidak stuck.")

if __name__ == "__main__":
    apply_memory_decay()
