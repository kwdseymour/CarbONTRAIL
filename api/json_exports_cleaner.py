# coding: utf-8

import pandas as pd
from datetime import datetime, timedelta
import mysql.connector as mariadb
from sqlalchemy import create_engine
import sys
import json

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
    cur.execute("CREATE TABLE IF NOT EXISTS lto_flights (postime DATETIME, hex VARCHAR(6), flight VARCHAR(10), alt_baro FLOAT, alt_geom FLOAT, gs FLOAT, tas FLOAT, track FLOAT, roll FLOAT, baro_rate FLOAT, ias FLOAT, mach FLOAT, mag_heading FLOAT, lat FLOAT, lon FLOAT, geom_rate FLOAT, nav_altitude_fms INT)")
except mariadb.Error as e:
    print(f'Error: {e}')

# Retrieve df from "json_exports" table in the "aircraft_positions" database
uri = f'mysql+pymysql://{USER}:{PASSWORD}@{HOST}/aircraft_positions'
engine = create_engine(uri)
try:
    df = pd.read_sql_query("SELECT * FROM json_exports", engine)
    query_time = datetime.utcnow()
    print('Database retrieval complete.')
except Exception as e:
    print(f'Problem retrieving from database: {e}')

lto_hexes = df[df.alt_geom<=3000].hex.unique()
ltos = df[df.hex.isin(lto_hexes)].sort_values(['hex','postime']).reset_index(drop=True)
# Get list of hex codes for flights seen within ten minutes of the query
recent_ltos_list = ltos.set_index('postime',drop=True).sort_index().loc[query_time-timedelta(minutes=10):,'hex'].unique()
past_ltos = ltos[~ltos.hex.isin(recent_ltos_list)]

# Drop any extra columns
cur.execute("SHOW COLUMNS FROM lto_flights")
columns = cur.fetchall()
if len(columns)>0:
    columns = list(list(zip(*columns))[0])
    past_ltos = past_ltos[columns]

# Drop any flights that are already in the "lto_flights" table
cur.execute("SELECT DISTINCT hex FROM lto_flights")
hex_codes = cur.fetchall()
if len(hex_codes)>0:
    hex_codes = list(list(zip(*hex_codes))[0])
    past_ltos = past_ltos[~past_ltos.hex.isin(hex_codes)]

# Upload df to "lto_flights" table in the "aircraft_positions" database
uri = f'mysql+pymysql://{USER}:{PASSWORD}@{HOST}/aircraft_positions'
engine = create_engine(uri)
try:
    past_ltos.to_sql('lto_flights',con=engine,if_exists='append',index=False)
    print('Database upload complete.')
except Exception as e:
    print(f'Problem uploading to database: {e}')

conn.commit()
cur.execute("SELECT COUNT(*) FROM lto_flights")
row_count = cur.fetchall()[0][0]
print(f'The "lto_flights" table now has {row_count} rows.')
conn.close()