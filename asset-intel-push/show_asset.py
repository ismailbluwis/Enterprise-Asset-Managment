from hdbcli import dbapi

conn = dbapi.connect(
    address="48e539b6-6ba6-4891-9538-727dd496988b.hna1.prod-us10.hanacloud.ondemand.com",
    port=443, user="DBADMIN", password="Admin123",
    encrypt=True, sslValidateCertificate=True
)
cur = conn.cursor()

AID = "P-101"

# Master
cur.execute(f'SELECT * FROM "ASSET_MASTER"."ASSETS" WHERE ASSET_ID=?', [AID])
cols = [d[0] for d in cur.description]
row = cur.fetchone()
print(f"\n{'='*55}")
print(f"  ASSET_MASTER.ASSETS  ({AID})")
print(f"{'='*55}")
for c, v in zip(cols, row):
    print(f"  {c:<30} {v}")

# Health score
cur.execute(f'SELECT * FROM "ASSET_MASTER"."ASSET_HEALTH_SCORES" WHERE ASSET_ID=?', [AID])
cols = [d[0] for d in cur.description]
row = cur.fetchone()
print(f"\n{'='*55}")
print(f"  ASSET_HEALTH_SCORES  ({AID})")
print(f"{'='*55}")
for c, v in zip(cols, row):
    print(f"  {c:<30} {v}")

# Financials
cur.execute(f'SELECT * FROM "ASSET_MASTER"."ASSET_FINANCIALS" WHERE ASSET_ID=?', [AID])
cols = [d[0] for d in cur.description]
row = cur.fetchone()
if row:
    print(f"\n{'='*55}")
    print(f"  ASSET_FINANCIALS  ({AID})")
    print(f"{'='*55}")
    for c, v in zip(cols, row):
        print(f"  {c:<30} {v}")

# Latest sensor readings
cur.execute(f'''
    SELECT TAG_NAME, TAG_VALUE, UOM, READING_TS, QUALITY
    FROM "IOT_SENSOR"."SENSOR_READINGS"
    WHERE ASSET_ID=?
    ORDER BY READING_TS DESC
    LIMIT 8
''', [AID])
print(f"\n{'='*55}")
print(f"  IOT_SENSOR.SENSOR_READINGS  ({AID}, latest 8)")
print(f"{'='*55}")
for r in cur.fetchall():
    print(f"  {str(r[0]):<30} {str(r[1]):<12} {str(r[2]):<8}  {str(r[3])[:16]}  {r[4]}")

# Work orders
cur.execute(f'''
    SELECT WO_ID, WO_TYPE, PRIORITY, STATUS, DESCRIPTION, CREATED_DATE, COST
    FROM "EAM_PM"."WORK_ORDERS"
    WHERE ASSET_ID=?
    ORDER BY CREATED_DATE DESC
    LIMIT 5
''', [AID])
print(f"\n{'='*55}")
print(f"  EAM_PM.WORK_ORDERS  ({AID})")
print(f"{'='*55}")
for r in cur.fetchall():
    cost = f"${float(r[6]):,.0f}" if r[6] else "$0"
    print(f"  {r[0]}  {r[1]}  P{r[2]}  {str(r[3]):<12}  {str(r[4])[:35]:<35}  {str(r[5])[:10]}  {cost}")

cur.close()
conn.close()
