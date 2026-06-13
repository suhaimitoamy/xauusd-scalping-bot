import sqlite3
import json
import os

db_path = "data/xauusd_bot.sqlite"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("""
    SELECT b.pattern_key, b.wins, b.losses, b.partials, b.score, d.rule_json 
    FROM brain_patterns b 
    LEFT JOIN dynamic_rules d ON b.pattern_key = d.pattern_key 
    WHERE b.pattern_key LIKE 'AI_%' 
    ORDER BY b.score DESC;
""")

rows = cur.fetchall()

md_content = "# Analisa Pola Super AI (Januari - Agustus 2025)\n\n"
md_content += "Berikut adalah hasil penguraian dari pola-pola yang diciptakan oleh AI beserta kriteria teknikalnya dan performanya di pasar sungguhan.\n\n"

for row in rows:
    key = row['pattern_key']
    wins = row['wins']
    losses = row['losses']
    partials = row['partials']
    score = row['score']
    rule_str = row['rule_json']
    
    total_trades = wins + losses + partials
    if total_trades == 0: continue
    win_rate = (wins + partials) / total_trades * 100
    
    desc = "Deskripsi tidak tersedia."
    direction = "UNKNOWN"
    conditions = "Tidak ada"
    if rule_str:
        try:
            rule = json.loads(rule_str)
            desc = rule.get('description', desc)
            direction = rule.get('direction', direction)
            cond_list = rule.get('conditions', [])
            if isinstance(cond_list, list):
                conditions = "\n".join([f"- `{c}`" for c in cond_list])
        except:
            pass
            
    md_content += f"## {key} ({direction})\n"
    md_content += f"**Win Rate:** {win_rate:.1f}% | **Score:** {score} | **Trades:** {total_trades} (W:{wins} / L:{losses} / P:{partials})\n\n"
    md_content += f"> {desc}\n\n"
    md_content += f"**Kondisi Entry:**\n{conditions}\n\n"
    md_content += "---\n\n"

out_path = "/data/data/com.termux/files/home/.gemini/antigravity-cli/brain/9ba1e28e-5e86-4e07-87b6-4bde38384c61/analisa_pola.md"
with open(out_path, "w") as f:
    f.write(md_content)

print(f"Artifact generated at {out_path}")
