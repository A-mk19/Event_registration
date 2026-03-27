import mysql.connector

# 🔌 Railway MySQL Connection
conn = mysql.connector.connect(
     host="centerbeam.proxy.rlwy.net",
    port=47605,          # ⚠️ VERY IMPORTANT
    user="root",
    password="hfIUFYKTFtQcDOqIBUZChRlqwbPtkkUA",
    database="railway"
)
cursor = conn.cursor()

# 🧱 Create Table Query
create_table_query = """
CREATE TABLE IF NOT EXISTS ST_TABLE (
    REG_ID VARCHAR(10) PRIMARY KEY,
    
    HTNO CHAR(10) UNIQUE,
    Na_ME VARCHAR(255),
    
    PY INT,
    BRANCH VARCHAR(20),
    
    PMBNO BIGINT,
    WTNO BIGINT,
    
    CREATED_AT DATETIME DEFAULT CURRENT_TIMESTAMP,
    STATUS VARCHAR(20) DEFAULT 'PENDING'
);
"""

try:
    cursor.execute(create_table_query)
    print("✅ Table ST_TABLE created successfully!")

except Exception as e:
    print("❌ Error:", e)

finally:
    cursor.close()
    conn.close()