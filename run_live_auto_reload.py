import os
import sys
import time
import subprocess

def get_file_mtimes(directory):
    mtimes = {}
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py') or file.endswith('.yaml'):
                path = os.path.join(root, file)
                try:
                    mtimes[path] = os.path.getmtime(path)
                except OSError:
                    pass
    # Also track main.py
    try:
        mtimes['main.py'] = os.path.getmtime('main.py')
    except OSError:
        pass
    return mtimes

def main():
    print("==================================================")
    print("🔄 ANTIGRAVITY AUTO-RELOADER ACTIVE")
    print("Bot will restart automatically if any .py or .yaml file changes.")
    print("==================================================")

    current_mtimes = get_file_mtimes('src')
    process = subprocess.Popen([sys.executable, 'main.py'])

    try:
        while True:
            time.sleep(1.5)
            new_mtimes = get_file_mtimes('src')
            changed = False
            for path, mtime in new_mtimes.items():
                if path not in current_mtimes or current_mtimes[path] != mtime:
                    print(f"\n[AUTO-RELOAD] File changed: {path}")
                    changed = True
                    break
            
            if changed:
                print("[AUTO-RELOAD] Restarting bot...")
                process.terminate()
                process.wait()
                current_mtimes = new_mtimes
                process = subprocess.Popen([sys.executable, 'main.py'])
                
            # If the bot crashed or exited naturally, restart it after 5 seconds
            if process.poll() is not None:
                print("[AUTO-RELOAD] Bot process died. Restarting in 5 seconds...")
                time.sleep(5)
                current_mtimes = get_file_mtimes('src')
                process = subprocess.Popen([sys.executable, 'main.py'])

    except KeyboardInterrupt:
        print("\n[AUTO-RELOAD] Shutting down...")
        process.terminate()
        process.wait()

if __name__ == '__main__':
    main()
