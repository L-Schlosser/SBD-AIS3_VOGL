import os
import subprocess
import sys
import time
from datetime import datetime, timedelta

import psycopg2

DB_DSN = os.getenv(
    "PG_DSN",
    "dbname=office_db user=postgres password=postgrespw host=localhost port=5432",
)


def fetch_avg_last_10m(conn, ten_minutes_ago):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT AVG(temperature) AS avg_temp
            FROM temperature_readings
            WHERE recorded_at >= %s;
            """,
            (ten_minutes_ago,)
        )
        row = cur.fetchone()
        return row[0]

try:
    while True:
        ten_minutes_ago = datetime.now() - timedelta(minutes=10)
        
        avg_temp = None  # Initialize avg_temp to None
        try:
            with psycopg2.connect(DB_DSN) as conn:
                avg_temp = fetch_avg_last_10m(conn, ten_minutes_ago)
        except Exception as db_exc:
            print(f"{datetime.now()} - DB error: {db_exc}")

        if avg_temp is not None:
            print(f"{datetime.now()} - Average temperature last 10 minutes: {avg_temp:.2f} °C")
        else:
            print(f"{datetime.now()} - No data in last 10 minutes.")
        time.sleep(600)  # every 10 minutes
except KeyboardInterrupt:
    print("Stopped consuming data.")
finally:
    print("Exiting.")
