from database import PlantDatabase
import os

def main():
    print("🌱 IMPORT DEPUIS EXCEL - VERSION DIRECTE\n")
    print("Cette méthode lit directement le fichier Excel")
    print("C'est la méthode la plus fiable !\n")
    print("="*60)
    
    # Chemin du fichier Excel
    excel_path = "data/20250929 Inventaire septembre 2025 - final.xlsm"
    
    # Vérifier que le fichier existe
    if not os.path.exists(excel_path):
        print(f"❌ ERREUR : Le fichier n'existe pas !")
        print(f"   Chemin recherché : {os.path.abspath(excel_path)}")
        print("\n💡 SOLUTION :")
        print("   1. Copiez votre fichier Excel dans le dossier 'data/'")
        print("   2. Ou modifiez la ligne 'excel_path' dans ce script")
        return
    
    print(f"✅ Fichier trouvé : {excel_path}\n")
    
    # Créer l'instance de la base
    db = PlantDatabase("plants_lab.db")
    
    # Étape 1 : Créer la table
    print("ÉTAPE 1/3 : Création de la table")
    print("-" * 60)
    db.create_tables()
    
    # Étape 2 : Importer depuis Excel
    print("\nÉTAPE 2/3 : Import depuis Excel")
    print("-" * 60)
    db.import_from_excel_direct(excel_path, sheet_name='DatasScan')
    
    # Étape 3 : Afficher les stats
    print("\nÉTAPE 3/3 : Statistiques")
    print("-" * 60)
    db.get_stats()
    
    print("\n" + "="*60)
    print("✅ TERMINÉ ! La base de données est prête.")
    print(f"📁 Fichier créé : plants_lab.db")
    print("\n💡 Prochaines étapes :")
    print("   - Ouvrez plants_lab.db avec DB Browser for SQLite")
    print("   - Ou utilisez Jupyter pour explorer les données")
    print("   - Ou lancez l'application Streamlit (à venir)")

if __name__ == "__main__":
    main()