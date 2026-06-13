import os

yearly_file = "/storage/emulated/0/Download/DAT_MT_XAUUSD_M1_2025.csv"

# Dictionary to hold file handles
file_handles = {}

try:
    with open(yearly_file, 'r') as f:
        for line in f:
            if not line.strip(): continue
            # Line format: 2025.01.02,00:00,...
            date_str = line.split(',')[0]
            parts = date_str.split('.')
            if len(parts) >= 2:
                year = parts[0]
                month = parts[1]
                month_key = f"{year}{month}"
                
                if month_key not in file_handles:
                    out_path = f"/storage/emulated/0/Download/DAT_MT_XAUUSD_M1_{month_key}.csv"
                    file_handles[month_key] = open(out_path, 'w')
                
                file_handles[month_key].write(line)
finally:
    for handle in file_handles.values():
        handle.close()

print(f"Successfully split into {len(file_handles)} monthly files.")
