import sqlite3

conn = sqlite3.connect('plants_lab.db')
cursor = conn.cursor()

print("🗑️  Suppression des tables normalisées...")

tables = ['plants_v2', 'strains', 'varieties', 'mediums', 'culture_types', 'locations', 'operations_log']

for table in tables:
    try:
        cursor.execute(f"DROP TABLE IF EXISTS {table}")
        print(f"✅ Table '{table}' supprimée")
    except Exception as e:
        print(f"⚠️  Erreur sur '{table}': {e}")

conn.commit()
conn.close()

print("\n✅ Tables normalisées supprimées. Vous pouvez relancer normalize_database.py")