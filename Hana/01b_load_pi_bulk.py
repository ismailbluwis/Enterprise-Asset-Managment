import os
import pandas as pd
import numpy as np
from hdbcli import dbapi
from dotenv import load_dotenv # Recommended: pip install python-dotenv

# Load credentials from .env file or environment variables
load_dotenv()
HANA_HOST = os.getenv("HANA_HOST", "61ad8950-40ce-44d8-a7f2-eede38bf52b5.hana.prod-ap21.hanacloud.ondemand.com")
HANA_PORT = int(os.getenv("HANA_PORT", 443))
HANA_USER = os.getenv("HANA_USER", "DBADMIN")
HANA_PASSWORD = os.getenv("HANA_PASSWORD", "Ismail@123") 
HANA_SCHEMA = "DATA_HIGHWAY"

DATA_DIR = "./sample_data"

def get_hana_connection():
    try:
        conn = dbapi.connect(
            address=HANA_HOST,
            port=HANA_PORT,
            user=HANA_USER,
            password=HANA_PASSWORD,
            encrypt=True,
            sslValidateCertificate=True
        )
        return conn
    except Exception as e:
        print(f"Error connecting to HANA: {e}")
        exit(1)

def main():
    csv_path = os.path.join(DATA_DIR, "pi_sensor_readings.csv")
    if not os.path.exists(csv_path):
        print(f"Error: File {csv_path} not found.")
        return

    # 1. Load and Clean Data
    df = pd.read_csv(csv_path)
    
    # Convert timestamp to string format HANA expects
    df['timestamp'] = pd.to_datetime(df['timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
    
    # Replace NaN with None so hdbcli inserts them as SQL NULL
    df = df.replace({np.nan: None})

    print(f"Connecting to HANA Cloud...")
    conn = get_hana_connection()
    cursor = conn.cursor()

    try:
        # 2. Clear existing data
        print("Clearing existing data...")
        cursor.execute(f'DELETE FROM "{HANA_SCHEMA}"."PI_SENSOR_READINGS"')
        
        # 3. Batch Insert
        insert_sql = f'''
            INSERT INTO "{HANA_SCHEMA}"."PI_SENSOR_READINGS" 
            ("TIMESTAMP_UTC", "TAG_NAME", "ASSET_ID", "VALUE", "UNIT", "QUALITY")
            VALUES (?, ?, ?, ?, ?, ?)
        '''

        batch_size = 5000 # Increased batch size for better performance
        total_rows = len(df)
        
        for start in range(0, total_rows, batch_size):
            batch = df.iloc[start : start + batch_size]
            # Convert dataframe chunk directly to list of tuples (much faster than iterrows)
            batch_data = list(batch.itertuples(index=False, name=None))
            
            cursor.executemany(insert_sql, batch_data)
            conn.commit()
            print(f"  → Loaded {min(start + batch_size, total_rows)} / {total_rows}")

    except Exception as e:
        print(f"Database Error: {e}")
    finally:
        cursor.close()
        conn.close()
        print("Connection closed.")

if __name__ == "__main__":
    main()