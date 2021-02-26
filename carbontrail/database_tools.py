import mysql.connector as mariadb
from sqlalchemy import create_engine
from getpass import getpass
import pandas as pd
import sys
import json

with open('config.json', 'r') as config_file:
    config = json.load(config_file)

# check size of existing table
HOST = config['mariadb_host']
PORT = config['mariadb_port']
PASSWORD = config['mariadb_password']
USER = config['mariadb_user']

def show_databases(user=USER):
    '''Connect to MariaDB Platform and show databases'''
    try:
        conn = mariadb.connect(
            user=user,
            password=PASSWORD,
            host=HOST,
            # port=PORT,
        )
    except mariadb.Error as e:
        print(f"Error connecting to MariaDB Platform: {e}")

    # Get Cursor
    cur = conn.cursor()
    cur.execute("SHOW DATABASES")
    databases = cur.fetchall()
    print('Available databases:')
    for db in databases:
        print('- '+db[0])
    conn.close()

def get_dataframe(statement,user=USER, host=HOST,port=PORT,database='aircraft_positions'):
    uri = f'mysql+pymysql://{user}:{PASSWORD}@{host}/aircraft_positions'
    engine = create_engine(uri)
    df = pd.read_sql_query(statement, engine)
    engine.dispose()
    str_cols = df.select_dtypes(include=['object']).columns
    for col in str_cols:
        df[col] = df[col].str.strip()
    return df

def retrieve(statement,arguments,user=USER, host=HOST,port=PORT,database='aircraft_positions'):
    '''Connect to MariaDB Platform'''
    try:
        conn = mariadb.connect(
            user=user,
            password=PASSWORD,
            host=host,
            port=port,
            database=database
        )
    except mariadb.Error as e:
        print(f"Error connecting to MariaDB Platform: {e}")
        sys.exit(1)
    # Get Cursor
    cur = conn.cursor()
    cur.execute(statement,arguments)
    output = cur.fetchall()
    conn.close()
    return output