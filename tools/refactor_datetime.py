import os
import glob

def refactor_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()
        
    if 'datetime.utcnow()' in content or 'datetime.datetime.utcnow()' in content:
        # Tambahkan import timezone jika belum ada
        if 'from datetime import timezone' not in content and 'import datetime' in content:
            # Jika menggunakan from datetime import datetime
            if 'from datetime import datetime' in content and 'from datetime import datetime, timezone' not in content:
                content = content.replace('from datetime import datetime', 'from datetime import datetime, timezone', 1)
            # Jika file tersebut menggunakan import datetime biasa, kita tidak perlu menambahkan apapun jika kita pakai datetime.timezone.utc
            
        # Lakukan replace
        content = content.replace('datetime.utcnow()', 'datetime.now(timezone.utc)')
        content = content.replace('datetime.datetime.utcnow()', 'datetime.datetime.now(datetime.timezone.utc)')
        
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"Refactored: {filepath}")

for py_file in glob.glob('src/*.py'):
    refactor_file(py_file)
