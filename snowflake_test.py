import snowflake.connector

conn = snowflake.connector.connect(
    user="RADHIKA",
    password="Radhika56@2006",
    account="TZBNHXF-QN62223",
    warehouse="COMPUTE_WH",
    database="ATMOSYNC_DB",
    schema="PUBLIC"
)

print("Connected Successfully!")
conn.close()