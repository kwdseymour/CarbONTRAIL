import requests
import json
import pandas as pd
import mysql.connector as mariadb
import time
from sqlalchemy import create_engine
import logging
import sys

with open('../config.json', 'r') as config_file:
    config = json.load(config_file)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter1 = logging.Formatter('%(asctime)s - %(name)s - %(process)d - %(levelname)s: %(message)s','%Y-%m-%d %H:%M:%S')
file_handler1 = logging.FileHandler('get_global_positions.log')
file_handler1.setLevel(logging.ERROR)
file_handler1.setFormatter(formatter1)
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)
formatter2 = logging.Formatter('%(asctime)s - %(process)d - %(levelname)s: %(message)s','%Y-%m-%d %H:%M:%S')
stream_handler.setFormatter(formatter2)
logger.addHandler(file_handler1)
logger.addHandler(stream_handler)

headers={'accept-encoding':'gzip'}
headers['api-auth'] = config['adsbexchange_api_v2_auth']

logger.info(f"Query started at {time.strftime('%X')}")
resp = requests.get('https://adsbexchange.com/api/aircraft/v2/all/',headers=headers)
logger.info(f"Query returned at {time.strftime('%X')}")

status = resp.status_code
try:
    response = resp.json()
    if status == 200: # 200 means the request returned a response correctly. all others indicate an error
        json_dump = resp.json()
except Exception as e:
    logger.error(e)
    sys.exit(1)

df = pd.DataFrame(json_dump['ac'])
raw_length = len(df)

df['postime'] = json_dump['now'] - df['seen_pos']*1000
df.postime = pd.to_datetime(df.postime,unit='ms')
df['alt_baro'] = pd.to_numeric(df['alt_baro'],errors='coerce')

# Clean unnecessary data
df.drop(columns=['mlat','tisb','messages','seen','rssi','track_rate','emergency','category','nav_altitude_mcp','nav_altitude_mcp','nav_heading','squawk',
                 'type','seen_pos','version','nic_baro','nac_p','nac_v','sil','sil_type','gva','sda','alert','spi','nic','rc','calc_track','nav_modes',
                 'rr_lat','rr_lon','dbFlags'],inplace=True)
df.dropna(subset=['hex','flight','lat','lon','alt_baro','alt_geom','ias','tas','mach','track','roll','mag_heading'],inplace=True)
df.reset_index(drop=True,inplace=True)

# Rearrange columns
recols = [df.columns[-1]]+list(df.columns[:-1]) 
df = df[recols]

logger.info(f'Dropped {raw_length-len(df):.0f} rows ({(raw_length-len(df))/raw_length*100:.1f}%)')
logger.info(f"Processing ended at {time.strftime('%X')}")

# HOST = '10.0.0.43'
HOST = config['mariadb_host']
PORT = config['mariadb_port']
PASSWORD = config['mariadb_password']
USER = config['mariadb_user']

'''Check for data older than 25 hours'''
try:
    conn = mariadb.connect(
        user=USER,
        password=PASSWORD,
        host=HOST,
        # port=PORT,
        database="aircraft_positions"
    )
except mariadb.Error as e:
    logger.error(f"Error connecting to MariaDB Platform: {e}")
    sys.exit(1)

cur = conn.cursor()

try:
    cur.execute("SELECT flight FROM global_aircraft WHERE postime < (UTC_TIMESTAMP() - INTERVAL 25 HOUR)")
    too_old_flights = cur.fetchall()
    if len(too_old_flights) > 0:
        raise Exception('The global_positions table contains entries older than 25 hours. Ensure the clean_global_aircraft.py script is running to ensure continuous cleansing and allow further database additions.')
except Exception as e:
    logger.error(f'There was a problem deleting old data from the database: {e}')
    sys.exit(1)
finally:
    conn.close()

# Upload df to global_aircraft table in the "aircraft_positions" database
uri = f'mysql+pymysql://{USER}:{PASSWORD}@{HOST}/aircraft_positions'
engine = create_engine(uri)

try:
    df.to_sql('global_aircraft',con=engine,if_exists='append',index=False)
    logger.info('Database upload complete.')
except Exception as e:
    logger.error(f'Problem uploading to database: {e}')
    sys.exit(1)