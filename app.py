import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import datetime
import os
from planning_page import render_planning_page
from chambers_page import render_chambers_page

# =========================
# CONFIGURATION DE LA PAGE
# =========================
st.set_page_config(
    page_title="PlantLab Manager",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================
# CONNEXION & CHARGEMENT
# =========================
@st.cache_resource
def get_connection():
    # Obtenir le dossier où se trouve app.py
    current_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(current_dir, 'plants_lab.db')
    return sqlite3.connect(db_path, check_same_thread=False)


@st.cache_data(ttl=60)
def load_data():
    conn = get_connection()
    query = "SELECT * FROM plants WHERE is_active = 1"
    df = pd.read_sql(query, conn)
    return df


def get_stats():
    conn = get_connection()
    stats = {}
    
    # ✅ Total séries = nombre de couples (strain, line) distincts
    query = """
        SELECT COUNT(*) as total
        FROM (
            SELECT strain, line
            FROM plants
            WHERE is_active = 1
            GROUP BY strain, line
        ) AS sub
    """
    stats['total_series'] = pd.read_sql(query, conn)['total'][0]
    
    # Total bocaux
    query = """
        SELECT SUM(bocaux) as total 
        FROM plants 
        WHERE is_active = 1 AND bocaux IS NOT NULL
    """
    result = pd.read_sql(query, conn)['total'][0]
    stats['total_bocaux'] = int(result) if result else 0
    
    # Nombre de souches
    query = """
        SELECT COUNT(DISTINCT strain) as total 
        FROM plants 
        WHERE is_active = 1 AND strain IS NOT NULL
    """
    stats['nb_souches'] = pd.read_sql(query, conn)['total'][0]
    
    # Nombre de chambres
    query = """
        SELECT COUNT(DISTINCT chambre) as total 
        FROM plants 
        WHERE is_active = 1 AND chambre IS NOT NULL
    """
    stats['nb_chambres'] = pd.read_sql(query, conn)['total'][0]
    
    return stats


# =========================
# TITRE & NAVIGATION
# =========================
st.title("🌱 PlantLab Manager")
st.markdown("### Gestion des plants in vitro de palmier")

page = st.sidebar.radio(
    "Aller à",
    [
        "🏠 Tableau de bord",
        "🔍 Recherche",
        "📅 Planning hebdomadaire",
        "🗄️ Plan des chambres",
        "📊 Statistiques",
        "📋 Tables de référence",
        "📋 Données brutes",
    ]
)

# =========================
# PAGE : TABLEAU DE BORD
# =========================
if page == "🏠 Tableau de bord":
    st.header("Tableau de bord")
    
    # Obtenir les stats
    stats = get_stats()
    
    # KPIs
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total de séries", f"{stats['total_series']:,}")
    with col2:
        st.metric("Total de bocaux", f"{stats['total_bocaux']:,}")
    with col3:
        st.metric("Nombre de souches", stats['nb_souches'])
    with col4:
        st.metric("Nombre de chambres", stats['nb_chambres'])
    
    st.markdown("---")
    
    # Graphiques
    col1, col2 = st.columns(2)
    
    # -------- Répartition par chambre --------
    with col1:
        st.subheader("📦 Répartition par chambre")
        conn = get_connection()
        query = """
            SELECT chambre, COUNT(*) as nb_series, SUM(bocaux) as total_bocaux
            FROM plants
            WHERE is_active = 1
            GROUP BY chambre
            ORDER BY total_bocaux DESC
        """
        df_chambres = pd.read_sql(query, conn)
        
        if not df_chambres.empty:
            fig = px.bar(
                df_chambres,
                x='chambre',
                y='total_bocaux',
                title='Nombre de bocaux par chambre',
                labels={'total_bocaux': 'Nombre de bocaux', 'chambre': 'Chambre'},
                color='total_bocaux',
                color_continuous_scale='Viridis'
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Aucune donnée disponible")
    
    # -------- Top 10 souches --------
    with col2:
        st.subheader("🌱 Top 10 souches")
        query = """
            SELECT strain, COUNT(*) as nb_series, SUM(bocaux) as total_bocaux
            FROM plants
            WHERE is_active = 1 AND strain IS NOT NULL
            GROUP BY strain
            ORDER BY total_bocaux DESC
            LIMIT 10
        """
        df_souches = pd.read_sql(query, conn)
        
        if not df_souches.empty:
            fig = px.pie(
                df_souches,
                values='total_bocaux',
                names='strain',
                title='Répartition des bocaux par souche'
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Aucune donnée disponible")
    
    # -------- Répartition par type de culture --------
    st.subheader("🔬 Répartition par type de culture")

    # Une série = couple (strain, line)
    query = """
        SELECT 
            type,
            COUNT(DISTINCT strain || '|' || line) AS nb_series,
            SUM(bocaux) AS total_bocaux
        FROM plants
        WHERE is_active = 1 
          AND type IS NOT NULL
        GROUP BY type
        ORDER BY total_bocaux DESC
    """
    conn = get_connection()
    df_types = pd.read_sql(query, conn)

    if not df_types.empty:
        fig = px.bar(
            df_types,
            x='type',
            y='total_bocaux',
            title='Nombre de bocaux par type de culture',
            labels={'total_bocaux': 'Nombre de bocaux', 'type': 'Type'},
            color='nb_series',
            color_continuous_scale='YlOrRd'  # dégradé jaune -> orange -> rouge
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Aucune donnée disponible pour les types de culture.")

# =========================
# PAGE : RECHERCHE
# =========================
elif page == "🔍 Recherche":
    st.header("Recherche de séries")
    
    conn = get_connection()
    
    # Champ de recherche
    search_term = st.text_input(
        "🔍 Scanner ou taper une valeur",
        placeholder="Ex: 735820250912AW2, STRAIN1, STRAIN1 L05...",
        help="Tapez ou scannez une valeur à rechercher"
    )
    
    # Choix du champ où chercher
    search_mode = st.selectbox(
        "Chercher dans",
        [
            "Tous les champs",
            "Série (souche + line)",
            "Code-barres",
            "Souche",
            "Variété",
            "Line",
            "Chambre",
            "Milieu",
            "Type",
        ]
    )
    
    if search_term:
        term = f"%{search_term}%"
        
        # Construction dynamique de la requête en fonction du mode
        if search_mode == "Tous les champs":
            query = """
                SELECT * FROM plants
                WHERE is_active = 1
                  AND (
                    raw_scan LIKE ?
                    OR raw_scan_mani_p LIKE ?
                    OR strain LIKE ?
                    OR nom_varietes LIKE ?
                    OR line LIKE ?
                    OR chambre LIKE ?
                    OR emplacement LIKE ?
                    OR milieu LIKE ?
                    OR type LIKE ?
                  )
            """
            params = [term] * 9
        
        elif search_mode == "Série (souche + line)":
            # 🔴 Ici on ne cherche PAS dans raw_scan / raw_scan_mani_p,
            # mais dans le couple (strain, line)
            query = """
                SELECT * FROM plants
                WHERE is_active = 1
                  AND strain IS NOT NULL
                  AND line IS NOT NULL
                  AND (
                    (strain || ' ' || line) LIKE ?
                    OR (strain || '-' || line) LIKE ?
                    OR (strain || '_' || line) LIKE ?
                  )
            """
            params = [term, term, term]
        
        elif search_mode == "Code-barres":
            query = """
                SELECT * FROM plants
                WHERE is_active = 1
                  AND (
                    raw_scan LIKE ?
                    OR raw_scan_mani_p LIKE ?
                  )
            """
            params = [term, term]
        
        elif search_mode == "Souche":
            query = """
                SELECT * FROM plants
                WHERE is_active = 1
                  AND strain LIKE ?
            """
            params = [term]
        
        elif search_mode == "Variété":
            query = """
                SELECT * FROM plants
                WHERE is_active = 1
                  AND nom_varietes LIKE ?
            """
            params = [term]
        
        elif search_mode == "Line":
            query = """
                SELECT * FROM plants
                WHERE is_active = 1
                  AND line LIKE ?
            """
            params = [term]
        
        elif search_mode == "Chambre":
            query = """
                SELECT * FROM plants
                WHERE is_active = 1
                  AND chambre LIKE ?
            """
            params = [term]
        
        elif search_mode == "Milieu":
            query = """
                SELECT * FROM plants
                WHERE is_active = 1
                  AND milieu LIKE ?
            """
            params = [term]
        
        elif search_mode == "Type":
            query = """
                SELECT * FROM plants
                WHERE is_active = 1
                  AND type LIKE ?
            """
            params = [term]
        
        else:
            # fallback sécurité
            query = """
                SELECT * FROM plants
                WHERE is_active = 1
                  AND (
                    raw_scan LIKE ?
                    OR raw_scan_mani_p LIKE ?
                    OR strain LIKE ?
                    OR nom_varietes LIKE ?
                  )
            """
            params = [term, term, term, term]
        
        # Exécution de la requête
        df_results = pd.read_sql(query, conn, params=params)
        
        if not df_results.empty:
            st.success(f"✅ {len(df_results)} résultat(s) trouvé(s)")
            
            # Afficher chaque résultat en détail
            for idx, row in df_results.iterrows():
                with st.expander(f"📦 {row['raw_scan']} - {row['strain']} - {row['chambre']}"):
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.write("**Identification**")
                        st.write(f"Code-barre : `{row['raw_scan']}`")
                        st.write(f"Souche : {row['strain']}")
                        st.write(f"Variété : {row['nom_varietes']}")
                        st.write(f"Line : {row['line']}")
                    
                    with col2:
                        st.write("**Localisation**")
                        st.write(f"Chambre : {row['chambre']}")
                        st.write(f"Emplacement : {row['emplacement']}")
                        st.write(f"Milieu : {row['milieu']}")
                        st.write(f"Type : {row['type']}")
                    
                    with col3:
                        st.write("**Quantités**")
                        st.write(f"Bocaux : {row['bocaux']}")
                        st.write(f"Caisses : {row['nb_caisse']}")
                        st.write(f"Date : {row['date']}")
                        st.write(f"Âge : {row['age_ams']}")
            
            # Tableau complet
            st.subheader("📋 Vue tableau")
            st.dataframe(df_results, use_container_width=True, hide_index=True)
        else:
            st.warning("❌ Aucun résultat trouvé")
    else:
        st.info("👆 Entrez une valeur et choisissez où chercher")

# =========================
# PAGE : STATISTIQUES
# =========================
elif page == "📊 Statistiques":
    st.header("Statistiques détaillées")
    
    conn = get_connection()
    
    # Filtres
    st.sidebar.subheader("Filtres")
    
    # Filtre par chambre
    query = "SELECT DISTINCT chambre FROM plants WHERE chambre IS NOT NULL ORDER BY chambre"
    chambres = pd.read_sql(query, conn)['chambre'].tolist()
    selected_chambres = st.sidebar.multiselect("Chambres", chambres, default=chambres)
    
    # Filtre par souche
    query = "SELECT DISTINCT strain FROM plants WHERE strain IS NOT NULL ORDER BY strain"
    strains = pd.read_sql(query, conn)['strain'].tolist()
    selected_strains = st.sidebar.multiselect("Souches", strains)
    
    # Construction du WHERE
    where_clauses = ["is_active = 1"]
    if selected_chambres:
        chambres_str = "','".join(selected_chambres)
        where_clauses.append(f"chambre IN ('{chambres_str}')")
    if selected_strains:
        strains_str = "','".join(selected_strains)
        where_clauses.append(f"strain IN ('{strains_str}')")
    
    where_clause = " AND ".join(where_clauses)
    
    # Stats avec filtres
    col1, col2, col3 = st.columns(3)
    
    with col1:
        query = f"SELECT COUNT(*) as total FROM plants WHERE {where_clause}"
        total = pd.read_sql(query, conn)['total'][0]
        st.metric("Séries filtrées (lignes)", total)
    
    with col2:
        query = f"""
            SELECT SUM(bocaux) as total 
            FROM plants 
            WHERE {where_clause} AND bocaux IS NOT NULL
        """
        result = pd.read_sql(query, conn)['total'][0]
        total_bocaux = int(result) if result else 0
        st.metric("Bocaux filtrés", total_bocaux)
    
    with col3:
        query = f"""
            SELECT COUNT(DISTINCT strain) as total 
            FROM plants 
            WHERE {where_clause} AND strain IS NOT NULL
        """
        nb_souches = pd.read_sql(query, conn)['total'][0]
        st.metric("Souches distinctes", nb_souches)
    
    st.markdown("---")
    
    # Tableaux détaillés
    tab1, tab2, tab3 = st.tabs(["Par souche", "Par milieu", "Par âge"])
    
    with tab1:
        query = f"""
            SELECT 
                strain,
                COUNT(*) as nb_series,
                SUM(bocaux) as total_bocaux,
                AVG(bocaux) as moy_bocaux
            FROM plants
            WHERE {where_clause} AND strain IS NOT NULL
            GROUP BY strain
            ORDER BY total_bocaux DESC
        """
        df_strains = pd.read_sql(query, conn)
        df_strains['moy_bocaux'] = df_strains['moy_bocaux'].round(1)
        st.dataframe(df_strains, use_container_width=True, hide_index=True)
    
    with tab2:
        query = f"""
            SELECT 
                milieu,
                COUNT(*) as nb_series,
                SUM(bocaux) as total_bocaux
            FROM plants
            WHERE {where_clause} AND milieu IS NOT NULL
            GROUP BY milieu
            ORDER BY total_bocaux DESC
        """
        df_milieux = pd.read_sql(query, conn)
        st.dataframe(df_milieux, use_container_width=True, hide_index=True)
    
    with tab3:
        query = f"""
            SELECT 
                age_ams,
                COUNT(*) as nb_series,
                SUM(bocaux) as total_bocaux
            FROM plants
            WHERE {where_clause} AND age_ams IS NOT NULL
            GROUP BY age_ams
            ORDER BY nb_series DESC
        """
        df_age = pd.read_sql(query, conn)
        st.dataframe(df_age, use_container_width=True, hide_index=True)

# =========================
# PAGE : DONNÉES BRUTES
# =========================
elif page == "📋 Données brutes":
    st.header("Données brutes")
    
    df = load_data()
    
    st.write(f"**Total : {len(df)} lignes (enregistrements)**")
    
    all_columns = df.columns.tolist()
    default_cols = [
        'raw_scan', 'strain', 'nom_varietes', 'chambre', 'emplacement',
        'milieu', 'type', 'bocaux', 'date', 'age_ams'
    ]
    
    selected_cols = st.multiselect(
        "Colonnes à afficher",
        all_columns,
        default=[col for col in default_cols if col in all_columns]
    )
    
    if selected_cols:
        st.dataframe(df[selected_cols], use_container_width=True, hide_index=True)
    else:
        st.warning("Sélectionnez au moins une colonne")
    
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Télécharger en CSV",
        data=csv,
        file_name=f"plants_export_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv"
    )

# =========================
# PAGE : PLANNING
# =========================
elif page == "📅 Planning hebdomadaire":
    conn = get_connection()
    render_planning_page(conn)

# =========================
# PAGE : PLAN DES CHAMBRES
# =========================
elif page == "🗄️ Plan des chambres":
    conn = get_connection()
    render_chambers_page(conn)

# =========================
# FOOTER
# =========================
st.sidebar.markdown("---")
st.sidebar.info("🌱 PlantLab Manager v1.0")
