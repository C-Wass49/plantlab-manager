import sqlite3
import pandas as pd
from datetime import datetime

class DatabaseNormalizer:
    """Normalise la base de données en créant des tables de référence"""
    
    def __init__(self, db_path="plants_lab.db"):
        self.db_path = db_path
        self.conn = None
    
    def connect(self):
        self.conn = sqlite3.connect(self.db_path)
        return self.conn
    
    def close(self):
        if self.conn:
            self.conn.close()
    
    def create_reference_tables(self):
        """Crée les tables de référence (souches, variétés, milieux, etc.)"""
        self.connect()
        cursor = self.conn.cursor()
        
        print("📊 Création des tables de référence...\n")
        
        # Table des souches
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS strains (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                description TEXT,
                origin TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ Table 'strains' créée")
        
        # Table des variétés
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS varieties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                strain_id INTEGER,
                batch_number TEXT,
                description TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (strain_id) REFERENCES strains(id)
            )
        """)
        print("✅ Table 'varieties' créée")
        
        # Table des milieux de culture
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mediums (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                name TEXT,
                composition TEXT,
                preparation_protocol TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ Table 'mediums' créée")
        
        # Table des types de culture
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS culture_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                description TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ Table 'culture_types' créée")
        
        # Table des chambres/localisations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS locations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chambre TEXT NOT NULL,
                emplacement TEXT,
                capacity INTEGER,
                temperature REAL,
                humidity REAL,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(chambre, emplacement)
            )
        """)
        print("✅ Table 'locations' créée")
        
        # Table normalisée des plants (version 2)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS plants_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                barcode TEXT UNIQUE NOT NULL,
                barcode_original TEXT,
                strain_id INTEGER,
                variety_id INTEGER,
                medium_id INTEGER,
                culture_type_id INTEGER,
                location_id INTEGER,
                line INTEGER,
                date TEXT,
                nb_weeks INTEGER,
                age_category TEXT,
                rang INTEGER,
                stage TEXT,
                rang_category TEXT,
                nb_boxes INTEGER,
                nb_jars_per_box INTEGER,
                total_jars INTEGER,
                quality_score TEXT,
                batch_lines TEXT,
                notes TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT,
                FOREIGN KEY (strain_id) REFERENCES strains(id),
                FOREIGN KEY (variety_id) REFERENCES varieties(id),
                FOREIGN KEY (medium_id) REFERENCES mediums(id),
                FOREIGN KEY (culture_type_id) REFERENCES culture_types(id),
                FOREIGN KEY (location_id) REFERENCES locations(id)
            )
        """)
        print("✅ Table 'plants_v2' créée")
        
        # Table d'historique des opérations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS operations_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plant_id INTEGER,
                operation_type TEXT,
                operation_date TEXT,
                operator_name TEXT,
                old_values TEXT,
                new_values TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (plant_id) REFERENCES plants_v2(id)
            )
        """)
        print("✅ Table 'operations_log' créée")
        
        self.conn.commit()
        self.close()
        print("\n✅ Toutes les tables de référence sont créées\n")
    
    def populate_reference_tables(self):
        """Remplit les tables de référence avec les données uniques de plants"""
        self.connect()
        cursor = self.conn.cursor()
        
        print("📥 Remplissage des tables de référence...\n")
        
        # 1. Remplir les souches
        cursor.execute("""
            INSERT OR IGNORE INTO strains (code)
            SELECT DISTINCT strain 
            FROM plants 
            WHERE strain IS NOT NULL AND strain != ''
            ORDER BY strain
        """)
        nb_strains = cursor.rowcount
        print(f"✅ {nb_strains} souches ajoutées")
        
        # 2. Remplir les variétés (avec lien vers souches)
        cursor.execute("""
            INSERT OR IGNORE INTO varieties (name, strain_id, batch_number)
            SELECT DISTINCT 
                p.nom_varietes,
                s.id,
                p.batch_number
            FROM plants p
            LEFT JOIN strains s ON p.strain = s.code
            WHERE p.nom_varietes IS NOT NULL AND p.nom_varietes != ''
            ORDER BY p.nom_varietes
        """)
        nb_varieties = cursor.rowcount
        print(f"✅ {nb_varieties} variétés ajoutées")
        
        # 3. Remplir les milieux
        cursor.execute("""
            INSERT OR IGNORE INTO mediums (code)
            SELECT DISTINCT milieu 
            FROM plants 
            WHERE milieu IS NOT NULL AND milieu != ''
            ORDER BY milieu
        """)
        nb_mediums = cursor.rowcount
        print(f"✅ {nb_mediums} milieux ajoutés")
        
        # 4. Remplir les types de culture
        cursor.execute("""
            INSERT OR IGNORE INTO culture_types (code)
            SELECT DISTINCT type 
            FROM plants 
            WHERE type IS NOT NULL AND type != ''
            ORDER BY type
        """)
        nb_types = cursor.rowcount
        print(f"✅ {nb_types} types de culture ajoutés")
        
        # 5. Remplir les localisations
        cursor.execute("""
            INSERT OR IGNORE INTO locations (chambre, emplacement)
            SELECT DISTINCT chambre, emplacement 
            FROM plants 
            WHERE chambre IS NOT NULL
            ORDER BY chambre, emplacement
        """)
        nb_locations = cursor.rowcount
        print(f"✅ {nb_locations} localisations ajoutées")
        
        self.conn.commit()
        self.close()
        print("\n✅ Tables de référence remplies\n")
    
    def check_duplicates(self):
        """Vérifie s'il y a des doublons dans les codes-barres"""
        self.connect()
        
        print("🔍 Vérification des doublons...\n")
        
        query = """
            SELECT 
                COALESCE(raw_scan_mani_p, raw_scan) as barcode,
                COUNT(*) as count
            FROM plants
            WHERE raw_scan IS NOT NULL
            GROUP BY barcode
            HAVING count > 1
            ORDER BY count DESC
            LIMIT 10
        """
        
        df_duplicates = pd.read_sql(query, self.conn)
        
        if len(df_duplicates) > 0:
            print(f"⚠️  {len(df_duplicates)} codes-barres en double détectés")
            print("\nTop 10 des doublons :")
            print(df_duplicates.to_string(index=False))
            print("\n💡 Les doublons seront gérés en ajoutant un suffixe (_1, _2, etc.)")
        else:
            print("✅ Aucun doublon détecté")
        
        self.close()
        return len(df_duplicates) > 0
    
    def migrate_to_normalized_structure(self):
        """Migre les données de plants vers plants_v2 avec les IDs de référence"""
        self.connect()
        cursor = self.conn.cursor()
        
        print("🔄 Migration vers la structure normalisée...\n")
        
        # Récupérer toutes les données à migrer
        query = """
            SELECT 
                p.id,
                COALESCE(p.raw_scan_mani_p, p.raw_scan) as barcode,
                p.raw_scan as barcode_original,
                s.id as strain_id,
                v.id as variety_id,
                m.id as medium_id,
                ct.id as culture_type_id,
                l.id as location_id,
                p.line,
                p.date,
                p.nb_sem,
                p.age_ams,
                p.rang,
                p.x_or_e_or_r_or_i,
                p.rang_rang_plus,
                p.nb_caisse,
                p.nb_bocaux,
                p.bocaux,
                p.qualite_chf,
                p.batch_lines,
                COALESCE(p.notes, p.col_23) as notes,
                p.is_active,
                p.import_date
            FROM plants p
            LEFT JOIN strains s ON p.strain = s.code
            LEFT JOIN varieties v ON p.nom_varietes = v.name
            LEFT JOIN mediums m ON p.milieu = m.code
            LEFT JOIN culture_types ct ON p.type = ct.code
            LEFT JOIN locations l ON p.chambre = l.chambre 
                AND (p.emplacement = l.emplacement OR (p.emplacement IS NULL AND l.emplacement IS NULL))
            WHERE p.raw_scan IS NOT NULL
            ORDER BY p.id
        """
        
        df = pd.read_sql(query, self.conn)
        
        print(f"📦 {len(df)} lignes à migrer")
        
        # Gérer les doublons en ajoutant un suffixe
        barcode_counts = {}
        unique_barcodes = []
        
        for barcode in df['barcode']:
            if pd.isna(barcode):
                unique_barcodes.append(None)
                continue
                
            if barcode not in barcode_counts:
                barcode_counts[barcode] = 0
                unique_barcodes.append(barcode)
            else:
                barcode_counts[barcode] += 1
                unique_barcodes.append(f"{barcode}_dup{barcode_counts[barcode]}")
        
        df['barcode_unique'] = unique_barcodes
        
        # Compter les doublons traités
        nb_duplicates = sum(1 for bc in unique_barcodes if bc and '_dup' in str(bc))
        if nb_duplicates > 0:
            print(f"⚠️  {nb_duplicates} doublons renommés avec suffixe _dup1, _dup2, etc.")
        
        # Insérer les données
        nb_inserted = 0
        nb_errors = 0
        
        for idx, row in df.iterrows():
            try:
                cursor.execute("""
                    INSERT INTO plants_v2 (
                        barcode,
                        barcode_original,
                        strain_id,
                        variety_id,
                        medium_id,
                        culture_type_id,
                        location_id,
                        line,
                        date,
                        nb_weeks,
                        age_category,
                        rang,
                        stage,
                        rang_category,
                        nb_boxes,
                        nb_jars_per_box,
                        total_jars,
                        quality_score,
                        batch_lines,
                        notes,
                        is_active,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    row['barcode_unique'],
                    row['barcode_original'],
                    row['strain_id'],
                    row['variety_id'],
                    row['medium_id'],
                    row['culture_type_id'],
                    row['location_id'],
                    row['line'],
                    row['date'],
                    row['nb_sem'],
                    row['age_ams'],
                    row['rang'],
                    row['x_or_e_or_r_or_i'],
                    row['rang_rang_plus'],
                    row['nb_caisse'],
                    row['nb_bocaux'],
                    row['bocaux'],
                    row['qualite_chf'],
                    row['batch_lines'],
                    row['notes'],
                    row['is_active'],
                    row['import_date']
                ))
                nb_inserted += 1
            except Exception as e:
                nb_errors += 1
                if nb_errors <= 5:  # Afficher seulement les 5 premières erreurs
                    print(f"⚠️  Erreur ligne {idx}: {str(e)[:100]}")
        
        self.conn.commit()
        self.close()
        
        print(f"✅ {nb_inserted} séries migrées vers plants_v2")
        if nb_errors > 0:
            print(f"⚠️  {nb_errors} erreurs rencontrées\n")
    
    def show_comparison(self):
        """Affiche une comparaison avant/après"""
        self.connect()
        
        print("📊 COMPARAISON AVANT/APRÈS\n")
        print("="*70)
        
        # Taille des tables
        df_old = pd.read_sql("SELECT COUNT(*) as nb FROM plants", self.conn)
        df_new = pd.read_sql("SELECT COUNT(*) as nb FROM plants_v2", self.conn)
        
        print(f"Table 'plants' (ancienne)    : {df_old['nb'][0]:,} lignes")
        print(f"Table 'plants_v2' (nouvelle) : {df_new['nb'][0]:,} lignes")
        
        # Tables de référence
        print("\n📋 Tables de référence créées :")
        for table in ['strains', 'varieties', 'mediums', 'culture_types', 'locations']:
            df = pd.read_sql(f"SELECT COUNT(*) as nb FROM {table}", self.conn)
            print(f"  - {table:20s} : {df['nb'][0]:>4} entrées")
        
        # Exemple de données normalisées
        print("\n📝 Exemple de données normalisées :")
        print("="*70)
        
        query = """
            SELECT 
                p.id,
                p.barcode,
                s.code as souche,
                v.name as variete,
                m.code as milieu,
                ct.code as type,
                l.chambre,
                l.emplacement,
                p.date,
                p.total_jars as bocaux
            FROM plants_v2 p
            LEFT JOIN strains s ON p.strain_id = s.id
            LEFT JOIN varieties v ON p.variety_id = v.id
            LEFT JOIN mediums m ON p.medium_id = m.id
            LEFT JOIN culture_types ct ON p.culture_type_id = ct.id
            LEFT JOIN locations l ON p.location_id = l.id
            LIMIT 5
        """
        
        df_sample = pd.read_sql(query, self.conn)
        print(df_sample.to_string(index=False))
        
        # Gains d'espace
        print("\n💾 Gains estimés :")
        print("="*70)
        
        # Calculer la taille approximative
        cursor = self.conn.cursor()
        
        # Taille ancienne table
        cursor.execute("SELECT COUNT(*) * 28 as size FROM plants")  # 28 colonnes
        old_size = cursor.fetchone()[0]
        
        # Taille nouvelle structure (approximatif)
        cursor.execute("SELECT COUNT(*) * 20 as size FROM plants_v2")  # 20 colonnes
        new_size = cursor.fetchone()[0]
        
        # Tailles des tables de référence (négligeable)
        ref_size = 0
        for table in ['strains', 'varieties', 'mediums', 'culture_types', 'locations']:
            cursor.execute(f"SELECT COUNT(*) * 5 as size FROM {table}")
            ref_size += cursor.fetchone()[0]
        
        total_new = new_size + ref_size
        gain = ((old_size - total_new) / old_size) * 100
        
        print(f"Colonnes ancienne structure : ~{old_size:,} cellules")
        print(f"Colonnes nouvelle structure : ~{total_new:,} cellules")
        print(f"Gain d'espace estimé        : ~{gain:.1f}%")
        
        print("\n✅ Avantages de la normalisation :")
        print("  - Moins de répétition des données")
        print("  - Modification centralisée (changer 'BRAHY' → 1 seule ligne)")
        print("  - Possibilité d'ajouter des infos sur souches/variétés/milieux")
        print("  - Requêtes plus rapides")
        print("  - Cohérence garantie (pas de typos)")
        
        self.close()
        print("\n✅ Normalisation terminée !")
    
    def create_indexes(self):
        """Crée des index pour améliorer les performances"""
        self.connect()
        cursor = self.conn.cursor()
        
        print("\n🚀 Création des index pour optimiser les performances...\n")
        
        # Index sur plants_v2
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_plants_v2_barcode ON plants_v2(barcode)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_plants_v2_strain ON plants_v2(strain_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_plants_v2_variety ON plants_v2(variety_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_plants_v2_location ON plants_v2(location_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_plants_v2_active ON plants_v2(is_active)")
        
        # Index sur operations_log
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_operations_plant ON operations_log(plant_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_operations_date ON operations_log(operation_date)")
        
        print("✅ Index créés")
        
        self.conn.commit()
        self.close()

def main():
    print("🌱 NORMALISATION DE LA BASE DE DONNÉES\n")
    print("Cette opération va créer des tables de référence")
    print("et migrer les données vers une structure normalisée.\n")
    print("="*70)
    print()
    
    normalizer = DatabaseNormalizer("plants_lab.db")
    
    # Étape 1 : Créer les tables
    print("ÉTAPE 1/5 : Création des tables de référence")
    print("-" * 70)
    normalizer.create_reference_tables()
    
    # Étape 2 : Remplir les tables de référence
    print("ÉTAPE 2/5 : Remplissage des tables de référence")
    print("-" * 70)
    normalizer.populate_reference_tables()
    
    # Étape 3 : Migration
    print("ÉTAPE 3/5 : Migration des données")
    print("-" * 70)
    normalizer.migrate_to_normalized_structure()
    
    # Étape 4 : Créer les index
    print("ÉTAPE 4/5 : Optimisation (création des index)")
    print("-" * 70)
    normalizer.create_indexes()
    
    # Étape 5 : Comparaison
    print("ÉTAPE 5/5 : Résultats")
    print("-" * 70)
    normalizer.show_comparison()
    
    print("\n" + "="*70)
    print("🎉 NORMALISATION TERMINÉE AVEC SUCCÈS !")
    print("="*70)
    print("\n💡 Prochaines étapes :")
    print("  1. Vérifier les données dans DB Browser ou Jupyter")
    print("  2. Mettre à jour app.py pour utiliser plants_v2")
    print("  3. L'ancienne table 'plants' est conservée en backup")

if __name__ == "__main__":
    main()