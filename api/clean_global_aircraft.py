import mysql.connector as mariadb
import logging
import sys
import json

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

# HOST = '10.0.0.43'
HOST = config['mariadb_host']
PORT = config['mariadb_port']
PASSWORD = config['mariadb_password']
USER = config['mariadb_user']

'''Delete data older than 24 hours'''
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
    if len(sys.argv) > 1:
        if sys.argv[1] != '--truncate':
            logger.error('Script argument error.')
            raise Exception('Script argument not recognized.')
        cur.execute("SELECT flight FROM global_aircraft WHERE postime > (UTC_TIMESTAMP() - INTERVAL 24 HOUR)")
        results = cur.fetchall()
        if len(results) == 0:
            cur.execute("TRUNCATE TABLE global_aircraft")
            logger.info("No entires from the last 24 hours were found. The table is being truncated.")
    else:
        cur.execute("DELETE FROM global_aircraft WHERE postime < (UTC_TIMESTAMP() - INTERVAL 24 HOUR)")
    conn.commit()
    logger.info("Entries older than 24 hours deleted successfully")
except Exception as e:
    logger.error(f'There was a problem deleting old data from the database: {e}')
    sys.exit(1)
finally:
    conn.close()
