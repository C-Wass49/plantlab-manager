import sqlite3
import pandas as pd
from datetime import datetime
import os

class PlantDatabase:
    """Gestion de la base de données SQLite pour le labo de plants in vitro"""
    
    def __init__(self, db_path="plants_lab.db"):
        self.db_path = db_path
        self.conn = None
        
    def connect(self):
        """Ouvre la connexion à la base"""
        self.conn = sqlite3.connect(self.db_path)
        return self.conn
    
    def close(self):
        """Ferme la connexion"""
        if self.conn:
            self.conn.close()
    
    def create_tables(self):
        """Crée la table principale plants"""
        self.connect()
        cursor = self.conn.cursor()
        
        # Table principale : une ligne = une série de plants à un moment donné
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS plants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chambre TEXT,
                emplacement TEXT,
                raw_scan TEXT,
                nb_caisse INTEGER,
                nb_bocaux INTEGER,
                raw_scan_mani_p TEXT,
                strain TEXT,
                line INTEGER,
                date TEXT,
                nb_sem INTEGER,
                age_ams TEXT,
                type TEXT,
                bocaux INTEGER,
                milieu TEXT,
                rang INTEGER,
                x_or_e_or_r_or_i TEXT,
                rang_rang_plus TEXT,
                type_rang TEXT,
                nom_varietes TEXT,
                batch_number TEXT,
                batch_lines TEXT,
                qualite_chf TEXT,
                col_22 TEXT,
                col_23 TEXT,
                notes TEXT,
                import_date TEXT,
                is_active INTEGER DEFAULT 1
            )
        """)
        
        self.conn.commit()
        print("✅ Table 'plants' créée avec succès")
        self.close()
    
    def import_from_csv(self, csv_path):
        """Importe les données depuis le CSV avec gestion robuste des erreurs"""
        
        if not os.path.exists(csv_path):
            print(f"❌ Erreur : le fichier {csv_path} n'existe pas")
            return
        
        print(f"📂 Lecture du fichier {csv_path}...")
        
        # Détecter la version de pandas
        pandas_version = pd.__version__
        print(f"   Version de Pandas : {pandas_version}")
        
        try:
            # Version compatible avec toutes les versions de Pandas
            df = pd.read_csv(
                csv_path,
                encoding='utf-8',
                engine='python'
            )
            print(f"✅ Fichier lu avec succès")
            
        except Exception as e1:
            print(f"⚠️  Tentative avec UTF-8 échouée : {str(e1)[:100]}...")
            
            try:
                # Essai avec encoding latin1
                df = pd.read_csv(
                    csv_path,
                    encoding='latin1',
                    engine='python'
                )
                print(f"✅ Fichier lu avec succès (encodage latin1)")
                
            except Exception as e2:
                print(f"⚠️  Tentative avec latin1 échouée : {str(e2)[:100]}...")
                
                try:
                    # Dernière tentative avec cp1252 (Windows)
                    df = pd.read_csv(
                        csv_path,
                        encoding='cp1252',
                        engine='python'
                    )
                    print(f"✅ Fichier lu avec succès (encodage cp1252)")
                    
                except Exception as e3:
                    print(f"❌ Impossible de lire le fichier CSV")
                    print(f"Erreur : {str(e3)}")
                    print("\n💡 SOLUTION : Utilisez import_from_excel.py à la place")
                    return
        
        # Afficher les infos de base
        print(f"📊 {len(df)} lignes trouvées")
        print(f"📊 {len(df.columns)} colonnes trouvées")
        
        # Afficher les premières colonnes
        print(f"\n📋 Premières colonnes détectées :")
        for i, col in enumerate(list(df.columns)[:10], 1):
            print(f"   {i}. {col}")
        if len(df.columns) > 10:
            print(f"   ... et {len(df.columns) - 10} autres colonnes")
        
        # Nettoyer les données
        print("\n🧹 Nettoyage des données...")
        
        # Supprimer les colonnes complètement vides
        df = df.dropna(axis=1, how='all')
        print(f"   Colonnes après suppression des vides : {len(df.columns)}")
        
        # Supprimer les colonnes Unnamed et numéros
        cols_to_drop = []
        for col in df.columns:
            col_str = str(col)
            if 'Unnamed' in col_str or col_str.isdigit():
                cols_to_drop.append(col)
        
        if cols_to_drop:
            df = df.drop(columns=cols_to_drop, errors='ignore')
            print(f"   Colonnes vides supprimées : {len(cols_to_drop)}")
        
        # Renommer les colonnes pour correspondre à la DB
        column_mapping = {
            'Chambre': 'chambre',
            'Emplacement': 'emplacement',
            'RawScan': 'raw_scan',
            'Nb caisse': 'nb_caisse',
            'Nb bocaux': 'nb_bocaux',
            'RawScan-Mani p': 'raw_scan_mani_p',
            'Strain': 'strain',
            'Line': 'line',
            'Date': 'date',
            'NbSem': 'nb_sem',
            'AgeAMS': 'age_ams',
            'Type': 'type',
            'Bocaux': 'bocaux',
            'Milieu': 'milieu',
            'Rang': 'rang',
            'XorEorRori': 'x_or_e_or_r_or_i',
            'Rang/Rang+': 'rang_rang_plus',
            'Type+Rang': 'type_rang',
            'nom_varietes': 'nom_varietes',
            'Batch#': 'batch_number',
            'BatchLines': 'batch_lines',
            'Qualité CHF': 'qualite_chf',
            '< alt+e': 'notes'
        }
        
        # Renommer uniquement les colonnes qui existent
        cols_to_rename = {k: v for k, v in column_mapping.items() if k in df.columns}
        df = df.rename(columns=cols_to_rename)
        print(f"   Colonnes renommées : {len(cols_to_rename)}")
        
        # Gérer les colonnes restantes
        remaining_cols = [c for c in df.columns if c not in column_mapping.values()]
        if len(remaining_cols) >= 1:
            df = df.rename(columns={remaining_cols[0]: 'col_22'})
        if len(remaining_cols) >= 2:
            df = df.rename(columns={remaining_cols[1]: 'col_23'})
        if len(remaining_cols) >= 3:
            extra_cols = remaining_cols[2:]
            df['notes_extra'] = df[extra_cols].fillna('').agg(' | '.join, axis=1)
            if 'notes' in df.columns:
                df['notes'] = df['notes'].fillna('') + ' ' + df['notes_extra']
            else:
                df['notes'] = df['notes_extra']
            df = df.drop(columns=extra_cols + ['notes_extra'])
        
        # Convertir les dates
        if 'date' in df.columns:
            print("   Conversion des dates...")
            df['date'] = pd.to_datetime(df['date'], errors='coerce', dayfirst=False)
            df['date'] = df['date'].dt.strftime('%Y-%m-%d')
            
            nb_dates_ok = df['date'].notna().sum()
            nb_dates_null = df['date'].isna().sum()
            print(f"   Dates converties : {nb_dates_ok}")
            if nb_dates_null > 0:
                print(f"   ⚠️  Dates non converties : {nb_dates_null}")
        
        # Convertir les colonnes numériques
        numeric_cols = ['nb_caisse', 'nb_bocaux', 'line', 'nb_sem', 'bocaux', 'rang']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Remplacer les NaN par None
        df = df.where(pd.notna(df), None)
        
        # Ajouter les métadonnées
        df['import_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        df['is_active'] = 1
        
        # Liste des colonnes de la DB
        db_columns = [
            'chambre', 'emplacement', 'raw_scan', 'nb_caisse', 'nb_bocaux',
            'raw_scan_mani_p', 'strain', 'line', 'date', 'nb_sem', 'age_ams',
            'type', 'bocaux', 'milieu', 'rang', 'x_or_e_or_r_or_i',
            'rang_rang_plus', 'type_rang', 'nom_varietes', 'batch_number',
            'batch_lines', 'qualite_chf', 'col_22', 'col_23', 'notes',
            'import_date', 'is_active'
        ]
        
        # Ajouter les colonnes manquantes
        for col in db_columns:
            if col not in df.columns:
                df[col] = None
        
        # Ne garder que les colonnes de la DB
        df = df[db_columns]
        
        # Importer dans SQLite
        print("\n💾 Import dans la base de données...")
        self.connect()
        
        try:
            df.to_sql('plants', self.conn, if_exists='append', index=False)
            self.conn.commit()
            print(f"✅ {len(df)} lignes importées avec succès dans la table 'plants'")
            print(f"📊 Base de données sauvegardée : {self.db_path}")
        except Exception as e:
            print(f"❌ Erreur lors de l'import dans SQLite : {str(e)}")
            self.conn.rollback()
        
        self.close()
    
    def import_from_excel_direct(self, excel_path, sheet_name='DatasScan'):
        """Importer directement depuis Excel (MÉTHODE RECOMMANDÉE)"""
        
        if not os.path.exists(excel_path):
            print(f"❌ Erreur : le fichier {excel_path} n'existe pas")
            return
        
        print(f"📂 Lecture directe du fichier Excel...")
        print(f"   Fichier : {os.path.basename(excel_path)}")
        print(f"   Feuille : {sheet_name}")
        
        try:
            # Lire directement depuis Excel
            df = pd.read_excel(
                excel_path,
                sheet_name=sheet_name,
                engine='openpyxl'
            )
            
            print(f"✅ Fichier Excel lu avec succès !")
            print(f"📊 {len(df)} lignes trouvées")
            print(f"📊 {len(df.columns)} colonnes trouvées")
            
            # Créer un CSV temporaire propre
            temp_csv = "data/temp_from_excel.csv"
            os.makedirs("data", exist_ok=True)
            df.to_csv(temp_csv, index=False, encoding='utf-8')
            print(f"💾 CSV temporaire créé : {temp_csv}")
            
            # Importer ce CSV
            self.import_from_csv(temp_csv)
            
        except ImportError:
            print("❌ La bibliothèque 'openpyxl' n'est pas installée")
            print("💡 Installez-la avec : pip install openpyxl")
        except Exception as e:
            print(f"❌ Erreur lors de la lecture d'Excel : {str(e)}")
    
    def get_stats(self):
        """Affiche des statistiques sur la base"""
        self.connect()
        cursor = self.conn.cursor()
        
        # Nombre total de lignes
        cursor.execute("SELECT COUNT(*) FROM plants WHERE is_active = 1")
        total = cursor.fetchone()[0]
        print(f"\n📊 STATISTIQUES")
        print(f"   Total de séries actives : {total}")
        
        if total == 0:
            print("   ⚠️  Aucune donnée dans la base !")
            self.close()
            return
        
        # Par chambre
        cursor.execute("""
            SELECT chambre, COUNT(*) as nb 
            FROM plants 
            WHERE is_active = 1 
            GROUP BY chambre 
            ORDER BY nb DESC
        """)
        print(f"\n   Par chambre :")
        for row in cursor.fetchall():
            print(f"      {row[0]}: {row[1]} séries")
        
        # Par souche
        cursor.execute("""
            SELECT strain, COUNT(*) as nb 
            FROM plants 
            WHERE is_active = 1 AND strain IS NOT NULL
            GROUP BY strain 
            ORDER BY nb DESC 
            LIMIT 10
        """)
        result = cursor.fetchall()
        if result:
            print(f"\n   Top 10 souches :")
            for row in result:
                print(f"      {row[0]}: {row[1]} séries")
        
        # Par type
        cursor.execute("""
            SELECT type, COUNT(*) as nb 
            FROM plants 
            WHERE is_active = 1 AND type IS NOT NULL
            GROUP BY type 
            ORDER BY nb DESC
        """)
        result = cursor.fetchall()
        if result:
            print(f"\n   Par type :")
            for row in result:
                print(f"      {row[0]}: {row[1]} séries")
        
        self.close()
    
    def search_by_barcode(self, barcode):
        """Cherche une série par son code-barres"""
        self.connect()
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT * FROM plants 
            WHERE (raw_scan LIKE ? OR raw_scan_mani_p LIKE ?)
            AND is_active = 1
        """, (f"%{barcode}%", f"%{barcode}%"))
        
        results = cursor.fetchall()
        self.close()
        
        return results