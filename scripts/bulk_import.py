import os
import sys
# Add root to path
sys.path.append(os.getcwd())

from utils.parser import KiteParser
from utils.database import KiteDatabase

def load_all():
    KiteDatabase.initialize_db()
    files_dir = "Files"
    files = [f for f in os.listdir(files_dir) if f.endswith('.csv')]
    
    for filename in files:
        path = os.path.join(files_dir, filename)
        print(f"Loading {filename}...")
        df = KiteParser.parse(path)
        KiteDatabase.save_report(df, filename)
    
    print("Pre-loading complete.")

if __name__ == "__main__":
    load_all()
