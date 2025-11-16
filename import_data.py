from database import PlantDatabase

def main():
    print("🌱 IMPORT DES DONNÉES PLANTS IN VITRO\n")
    
    # Créer l'instance de la base
    db = PlantDatabase("plants_lab.db")
    
    # Étape 1 : Créer la table
    print("Étape 1/3 : Création de la table...")
    db.create_tables()
    
    # Étape 2 : Importer les données
    print("\nÉtape 2/3 : Import des données...")
    csv_path = "data/DatasScan_export.csv"
    db.import_from_csv(csv_path)
    
    # Étape 3 : Afficher les stats
    print("\nÉtape 3/3 : Statistiques...")
    db.get_stats()
    
    print("\n✅ TERMINÉ ! La base de données est prête.")
    print(f"📁 Fichier créé : plants_lab.db")

if __name__ == "__main__":
    main()