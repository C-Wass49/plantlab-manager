import streamlit as st
import pandas as pd
import re
import plotly.express as px
import plotly.graph_objects as go

def render_chambers_page(conn):
    """Affiche le plan des chambres avec heatmap + grille par étagère/position."""
    
    st.header("🗄️ Plan des chambres")
    st.caption("Visualisation des emplacements : Chambre → Étagère (A-E, Z) × Position")

    # ========== CHARGEMENT DES DONNÉES ==========
    query = """
        SELECT 
            p.id,
            p.barcode,
            p.batch_lines,
            p.total_jars,
            p.nb_weeks,
            s.code as strain_code,
            v.name as variety_name,
            m.code as medium_code,
            l.chambre,
            l.emplacement
        FROM plants_v2 p
        LEFT JOIN strains s ON p.strain_id = s.id
        LEFT JOIN varieties v ON p.variety_id = v.id
        LEFT JOIN mediums m ON p.medium_id = m.id
        LEFT JOIN locations l ON p.location_id = l.id
        WHERE p.is_active = 1
    """
    df = pd.read_sql(query, conn)

    if df.empty:
        st.info("Aucune série active dans la base.")
        return

    # ========== FONCTION : COMPTER LES SÉRIES (strain_code, batch_lines) ==========
    def count_series(df_subset: pd.DataFrame) -> int:
        """
        Compte le nombre de séries uniques définies comme couples (strain_code, batch_lines).
        """
        if df_subset.empty:
            return 0
        return df_subset[['strain_code', 'batch_lines']].drop_duplicates().shape[0]

    # ========== PARSING DES EMPLACEMENTS ==========
    VALID_SHELVES = "ABCDEZ"

    def parse_location(row):
        """Parse chambre + emplacement pour extraire : chambre, étagère, position"""
        chambre_raw = str(row['chambre']).strip().upper() if pd.notna(row['chambre']) else None
        emplacement_raw = str(row['emplacement']).strip().upper() if pd.notna(row['emplacement']) else None
        
        # Ignorer les chambres froides
        if chambre_raw and ('CHF' in chambre_raw or 'FROID' in chambre_raw):
            return pd.Series({'chambre_num': None, 'etagere': None, 'position': None, 'location_type': 'CHF'})
        
        # Cas 1 : Format "1A20" dans emplacement
        if emplacement_raw:
            m = re.match(rf"^(\d+)([{VALID_SHELVES}])(\d+)$", emplacement_raw)
            if m:
                return pd.Series({
                    'chambre_num': m.group(1),
                    'etagere': m.group(2),
                    'position': int(m.group(3)),
                    'location_type': 'standard'
                })
        
        # Cas 2 : Format "A20" dans emplacement + chambre séparée
        if emplacement_raw and chambre_raw:
            m = re.match(rf"^([{VALID_SHELVES}])(\d+)$", emplacement_raw)
            if m and chambre_raw.isdigit():
                return pd.Series({
                    'chambre_num': chambre_raw,
                    'etagere': m.group(1),
                    'position': int(m.group(2)),
                    'location_type': 'standard'
                })
        
        # Cas 3 : Chambre "1A" + emplacement "20"
        if chambre_raw:
            m = re.match(rf"^(\d+)([{VALID_SHELVES}])$", chambre_raw)
            if m and emplacement_raw and emplacement_raw.isdigit():
                return pd.Series({
                    'chambre_num': m.group(1),
                    'etagere': m.group(2),
                    'position': int(emplacement_raw),
                    'location_type': 'standard'
                })
        
        # Cas 4 : Chambre "1" + emplacement "A20"
        if chambre_raw and chambre_raw.isdigit() and emplacement_raw:
            m = re.match(rf"^([{VALID_SHELVES}])(\d+)$", emplacement_raw)
            if m:
                return pd.Series({
                    'chambre_num': chambre_raw,
                    'etagere': m.group(1),
                    'position': int(m.group(2)),
                    'location_type': 'standard'
                })
        
        return pd.Series({'chambre_num': None, 'etagere': None, 'position': None, 'location_type': 'unknown'})

    parsed = df.apply(parse_location, axis=1)
    df = pd.concat([df, parsed], axis=1)

    # ========== STATISTIQUES GLOBALES (AVEC NOUVELLE DÉFINITION DE SÉRIE) ==========
    total_series = count_series(df)
    parsed_series = count_series(df[df['location_type'] == 'standard'])
    chf_series = count_series(df[df['location_type'] == 'CHF'])
    unknown_series = count_series(df[df['location_type'] == 'unknown'])
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total séries (unique strain+line)", total_series)
    with col2:
        st.metric("Chambres standard", parsed_series)
    with col3:
        st.metric("Chambres froides", chf_series)
    with col4:
        st.metric("Non parsé", unknown_series)
    
    # Debug
    if unknown_series > 0:
        with st.expander(f"⚠️ {unknown_series} séries (strain+line) avec emplacement non parsé"):
            st.dataframe(
                df[df['location_type'] == 'unknown'][['chambre', 'emplacement', 'barcode', 'strain_code']].head(20),
                use_container_width=True,
                hide_index=True
            )
    
    st.markdown("---")
    
    # ========== FILTRER LES DONNÉES STANDARD ==========
    df_standard = df[df['location_type'] == 'standard'].copy()
    
    if df_standard.empty:
        st.warning("Aucune série dans les chambres standard après parsing.")
        return
    
    # ========== SIDEBAR : FILTRES ==========
    with st.sidebar:
        st.subheader("🔍 Filtres")
        
        all_strains = ['Toutes'] + sorted(df_standard['strain_code'].dropna().unique().tolist())
        selected_strain = st.selectbox("Souche", all_strains)
        
        all_mediums = ['Tous'] + sorted(df_standard['medium_code'].dropna().unique().tolist())
        selected_medium = st.selectbox("Milieu", all_mediums)
        
        df_filtered = df_standard.copy()
        if selected_strain != 'Toutes':
            df_filtered = df_filtered[df_filtered['strain_code'] == selected_strain]
        if selected_medium != 'Tous':
            df_filtered = df_filtered[df_filtered['medium_code'] == selected_medium]
        
        # 🔁 ICI : on affiche le nombre de séries uniques (strain_code, batch_lines)
        st.caption(f"**{count_series(df_filtered)}** séries (couples souche+line) après filtres")
    
    # ========== SÉLECTION DE LA CHAMBRE ==========
    chambres = sorted(df_filtered['chambre_num'].dropna().unique())
    
    if not chambres:
        st.info("Aucune chambre disponible avec les filtres actuels.")
        return
    
    selected_chambre = st.selectbox("📦 Chambre à afficher", chambres)
    
    df_room = df_filtered[df_filtered['chambre_num'] == selected_chambre].copy()
    
    if df_room.empty:
        st.info("Aucune série dans cette chambre avec les filtres actuels.")
        return
    
    st.markdown(f"### Chambre {selected_chambre}")
    
    # Stats (avec nouvelle définition)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Séries (strain+line)", count_series(df_room))
    with col2:
        st.metric("Bocaux total", int(df_room['total_jars'].sum()))
    with col3:
        st.metric("Souches différentes", df_room['strain_code'].nunique())
    
    # ========== HEATMAP ==========
    st.subheader("🗺️ Heatmap d'occupation (nombre de bocaux)")
    
    shelves_order = [s for s in 'ABCDEZ' if s in df_room['etagere'].unique()]
    max_pos = int(df_room['position'].max())
    
    # Agréger par SOMME DES BOCAUX (pas nombre de séries)
    agg = df_room.groupby(['etagere', 'position'])['total_jars'].sum().reset_index(name='nb_bocaux')
    matrix = agg.pivot(index='etagere', columns='position', values='nb_bocaux')
    matrix = matrix.reindex(index=shelves_order).fillna(0)
    
    fig = px.imshow(
        matrix,
        aspect='auto',
        color_continuous_scale='Greens',
        labels=dict(x="Position", y="Étagère", color="Bocaux"),
        text_auto=True
    )
    fig.update_layout(
        xaxis_title="Position sur l'étagère",
        yaxis_title="Étagère",
        margin=dict(l=40, r=40, t=40, b=40),
        height=300
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # ========== VUE GRILLE AVEC STREAMLIT NATIF ==========
    st.subheader("📋 Vue grille détaillée")
    
    show_empty = st.checkbox("Afficher les positions vides", value=False)
    
    for shelf in shelves_order:
        shelf_data = df_room[df_room['etagere'] == shelf]
        if shelf_data.empty:
            continue
        
        # 🔁 Compter les séries uniques sur cette étagère
        st.markdown(f"**📚 Étagère {shelf}** ({count_series(shelf_data)} séries)")
        
        occupied_positions = sorted(shelf_data['position'].unique())
        
        if show_empty:
            positions_to_show = list(range(1, max_pos + 1))
        else:
            positions_to_show = occupied_positions
        
        # Créer des colonnes pour affichage en grille (max 10 par ligne)
        cols_per_row = 10
        
        for i in range(0, len(positions_to_show), cols_per_row):
            positions_chunk = positions_to_show[i:i+cols_per_row]
            
            cols = st.columns(cols_per_row)
            
            for col_idx, pos in enumerate(positions_chunk):
                with cols[col_idx]:
                    items = shelf_data[shelf_data['position'] == pos]
                    
                    if not items.empty:
                        # Ici on garde la logique par ligne pour l’affichage détaillé
                        row = items.iloc[0]
                        nb_items = len(items)
                        
                        strain = str(row['strain_code']) if pd.notna(row['strain_code']) else "?"
                        series = str(row['batch_lines']) if pd.notna(row['batch_lines']) else "?"
                        jars = int(row['total_jars']) if pd.notna(row['total_jars']) else 0
                        
                        st.markdown(f"""
                            <div style='background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%); 
                                        padding: 6px; border-radius: 6px; border: 2px solid #66bb6a;
                                        text-align: center; height: 90px; display: flex; flex-direction: column;
                                        justify-content: center;'>
                                <div style='font-weight: 700; color: #424242; font-size: 0.85em;'>
                                    {pos}{f' (+{nb_items-1})' if nb_items > 1 else ''}
                                </div>
                                <div style='font-weight: 600; color: #1565c0; font-size: 0.8em;'>
                                    {strain}
                                </div>
                                <div style='color: #616161; font-size: 0.7em;'>
                                    {series[:8]}
                                </div>
                                <div style='color: #2e7d32; font-weight: 600; font-size: 0.75em;'>
                                    🫙{jars}
                                </div>
                            </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                            <div style='background-color: #fafafa; padding: 6px; 
                                        border-radius: 6px; border: 2px solid #e0e0e0;
                                        text-align: center; height: 90px;
                                        display: flex; align-items: center; justify-content: center;'>
                                <div style='font-weight: 700; color: #9e9e9e; font-size: 0.85em;'>{pos}</div>
                            </div>
                        """, unsafe_allow_html=True)
            
            # Remplir les colonnes vides si le chunk est incomplet
            for empty_idx in range(len(positions_chunk), cols_per_row):
                with cols[empty_idx]:
                    st.markdown("""
                        <div style='height: 90px;'></div>
                    """, unsafe_allow_html=True)
        
        st.markdown("---")
    
    # ========== TABLEAU DÉTAILLÉ ==========
    with st.expander("📊 Tableau détaillé des séries"):
        cols = ['etagere', 'position', 'barcode', 'strain_code', 'variety_name', 
                'batch_lines', 'medium_code', 'total_jars', 'nb_weeks']
        display_df = df_room[cols].sort_values(['etagere', 'position'])
        
        display_df = display_df.rename(columns={
            'etagere': 'Étagère',
            'position': 'Position',
            'barcode': 'Code-barre',
            'strain_code': 'Souche',
            'variety_name': 'Variété',
            'batch_lines': 'Série',
            'medium_code': 'Milieu',
            'total_jars': 'Bocaux',
            'nb_weeks': 'Âge (sem)'
        })
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        csv = display_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Télécharger en CSV",
            data=csv,
            file_name=f"chambre_{selected_chambre}.csv",
            mime="text/csv"
        )
