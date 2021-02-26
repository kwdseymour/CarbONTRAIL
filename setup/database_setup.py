import mysql.connector as mariadb
import sys
import json

with open('config.json', 'r') as config_file:
    config = json.load(config_file)

# check size of existing table
HOST = config['mariadb_host']
PORT = config['mariadb_port']
PASSWORD = config['mariadb_password']
USER = config['mariadb_user']

# Connect to MariaDB Platform and create database
try:
    conn = mariadb.connect(
        user=USER,
        password=PASSWORD,
        host=HOST,
    )
    # Get Cursor
    cur = conn.cursor()
    cur.execute("CREATE DATABASE IF NOT EXISTS aircraft_positions")
    conn.commit()
    cur.execute("SHOW DATABASES")
    databases = cur.fetchall()
except mariadb.Error as e:
    print(f'Error: {e}')
    sys.exit(1)
finally:
    if conn is not None:
        conn.close()

print('Available databases:')
for db in databases:
    print('- '+db[0])

# Connect to MariaDB Platform and create table
try:
    conn = mariadb.connect(
        user=USER,
        password=PASSWORD,
        host=HOST,
        database='aircraft_positions'
    )
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS global_aircraft (postime DATETIME, hex VARCHAR(255), flight VARCHAR(255), r VARCHAR(255), t VARCHAR(255), alt_baro FLOAT, alt_geom FLOAT, gs FLOAT, ias FLOAT, tas FLOAT, mach FLOAT, wd FLOAT, ws FLOAT, oat FLOAT, tat FLOAT, track FLOAT, roll FLOAT, mag_heading FLOAT, true_heading FLOAT, baro_rate FLOAT, geom_rate FLOAT, nav_qnh FLOAT, nav_altitude_fms FLOAT, lat FLOAT, lon FLOAT )")
    conn.commit()
    cur.execute("SELECT * FROM global_aircraft LIMIT 0")
    print('global_aircraft table successfully created')
except mariadb.Error as e:
    print(f'Error: {e}')
    sys.exit(1)
finally:
    if conn is not None:
        conn.close()

print('global_aircraft columns:')
for col in cur.description:
    print(col[0],'--',col[1])
conn.close()
