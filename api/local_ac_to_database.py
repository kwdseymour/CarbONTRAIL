# coding: utf-8

import requests
import json
import pandas as pd
from datetime import datetime, timedelta
import mysql.connector as mariadb
import time
from sqlalchemy import create_engine
import sys

with open('../config.json', 'r') as config_file:
    config = json.load(config_file)

# check size of existing table
HOST = config['mariadb_host']
PORT = config['mariadb_port']
PASSWORD = config['mariadb_password']
USER = config['mariadb_user']

try:
    conn = mariadb.connect(
        user=USER,
        password=PASSWORD,
        host=HOST,
        port=PORT,
        database='aircraft_positions'
    )
except mariadb.Error as e:
    print(f"Error connecting to MariaDB Platform: {e}")
    sys.exit(1)

# Get Cursor
cur = conn.cursor()

# Create a table if it does not exist
try:
    cur.execute("CREATE TABLE IF NOT EXISTS json_exports (postime DATETIME, hex VARCHAR(6), flight VARCHAR(10), alt_baro FLOAT, alt_geom FLOAT, gs FLOAT, tas FLOAT, track FLOAT, roll FLOAT, baro_rate FLOAT, ias FLOAT, mach FLOAT, mag_heading FLOAT, lat FLOAT, lon FLOAT, geom_rate FLOAT, nav_altitude_fms INT)")
except mariadb.Error as e:
    print(f'Error: {e}')

cur.execute("SELECT COUNT(*) FROM json_exports")
row_count = cur.fetchall()[0][0]
if row_count > 1e6:
    print('Row count too high. Exiting script now.')
    sys.exit()

# get json data
JSON_HOST = '10.0.0.43'
JSON_PORT = '8080'
json_dump = requests.get("http://{}:{}/data/aircraft.json".format(JSON_HOST,JSON_PORT)).json()

df = pd.json_normalize(json_dump['aircraft'])
raw_length = len(df)
df['postime'] = json_dump['now'] - df['seen_pos']
df.postime = pd.to_datetime(df.postime,unit='s')
df['alt_baro'] = pd.to_numeric(df['alt_baro'],errors='coerce')
drop_cols = ['mlat','tisb','messages','seen','rssi','track_rate','emergency','category','nav_altitude_mcp','nav_altitude_mcp','nav_qnh','nav_heading','squawk',
             'seen_pos','version','nic_baro','nac_p','nac_v','sil','sil_type','gva','sda','nic','rc','nav_modes','true_heading','type']
drop_cols = [x for x in drop_cols if x in df.columns]
df.drop(columns=drop_cols,inplace=True)
df.dropna(subset=['hex','flight','lat','lon','alt_baro','alt_geom','ias','tas','mach','track','roll','mag_heading'],inplace=True)
df.reset_index(drop=True,inplace=True)
recols = [df.columns[-1]]+list(df.columns[:-1])
df = df[recols]
print(f'Dropped {raw_length-len(df):.0f} rows ({(raw_length-len(df))/raw_length*100:.1f}%)')
print(f"Processing ended at {time.strftime('%X')}")


# Upload df to "json_exports" table in the "aircraft_positions" database
uri = f'mysql+pymysql://{USER}:{PASSWORD}@{HOST}/aircraft_positions'
engine = create_engine(uri)
try:
    df.to_sql('json_exports',con=engine,if_exists='append',index=False)
    print('Database upload complete.')
except Exception as e:
    print(f'Problem uploading to database: {e}')

cur.execute("SELECT COUNT(*) FROM json_exports")
row_count = cur.fetchall()[0][0]
print(f'The "json_exports" table now has {row_count} rows.')
conn.close()