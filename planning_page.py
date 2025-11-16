import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from planning_engine import PlanningEngine
import os

def render_planning_page(conn):
    """Affiche la page de planification hebdomadaire"""
    
    st.header("📅 Planification Hebdomadaire des Repiquages")
    st.caption("Génération automatique avec regroupement par souche • Matin (8h-12h) / Après-midi (13h-17h)")
    
    # ========== SIDEBAR : OPTIONS ==========
    with st.sidebar:
        st.subheader("⚙️ Options de planification")
        
        # Date de référence
        date_ref = st.date_input(
            "Date de référence",
            value=datetime.now(),
            help="Date utilisée pour calculer l'âge des plants"
        )
        
        # Semaine à planifier
        today = datetime.now()
        default_monday = today - timedelta(days=today.weekday())
        
        week_start = st.date_input(
            "Semaine à planifier (lundi)",
            value=default_monday,
            help="Premier jour (lundi) de la semaine à planifier"
        )
        
        st.markdown("---")
        
        # Ressources
        st.subheader("👥 Ressources")
        
        col1, col2 = st.columns(2)
        with col1:
            nb_workers_gen = st.number_input(
                "Travailleurs généraux",
                min_value=1,
                max_value=50,
                value=17,
                help="Pool général (X, RG, XS, E, E+)"
            )
        
        with col2:
            nb_workers_i = st.number_input(
                "Spécialistes 'i'",
                min_value=1,
                max_value=10,
                value=3,
                help="Pool spécialisé (i, XM)"
            )
        
        jars_per_day = st.number_input(
            "Bocaux/JOUR/travailleur",
            min_value=10,
            max_value=200,
            value=50,
            help="Vitesse de travail (sera divisée en 25/demi-journée)"
        )
        
        st.info(f"💡 Capacité par demi-journée :\n- Général: {int(nb_workers_gen * jars_per_day / 2)} bocaux\n- Pool i: {int(nb_workers_i * jars_per_day / 2)} bocaux")
        
        st.markdown("---")
        
        # Seuils d'éligibilité
        st.subheader("⏱️ Seuils d'éligibilité")
        
        threshold_brahy = st.number_input(
            "BRAHY (X/XM/E/E+) - semaines",
            min_value=1,
            max_value=12,
            value=4,
            help="Périodicité pour BRAHY sur X, XM, E, E+"
        )
        
        threshold_other = st.number_input(
            "Autres - semaines",
            min_value=1,
            max_value=16,
            value=8,
            help="Périodicité pour toutes les autres combinaisons"
        )
        
        st.markdown("---")
        
        # Options avancées
        with st.expander("🔧 Options avancées"):
            jars_per_box = st.number_input(
                "Bocaux par caisse",
                min_value=1,
                max_value=50,
                value=14
            )
    
    # ========== BOUTON PRINCIPAL ==========
    st.markdown("---")
    
    if st.button("🚀 Créer l'agenda de la semaine", type="primary", use_container_width=True):
        
        with st.spinner("Chargement et planification avec regroupement par souche..."):
            
            # Charger les données
            query = """
                SELECT 
                    p.barcode,
                    p.barcode_original,
                    s.code as strain_code,
                    v.name as variety_name,
                    m.code as medium_code,
                    l.chambre,
                    l.emplacement,
                    p.total_jars,
                    p.nb_boxes,
                    p.nb_jars_per_box,
                    p.nb_weeks,
                    p.line,
                    p.date,
                    p.age_category
                FROM plants_v2 p
                LEFT JOIN strains s ON p.strain_id = s.id
                LEFT JOIN varieties v ON p.variety_id = v.id
                LEFT JOIN mediums m ON p.medium_id = m.id
                LEFT JOIN locations l ON p.location_id = l.id
                WHERE p.is_active = 1
            """
            
            df = pd.read_sql(query, conn)
            
            if df.empty:
                st.error("Aucune donnée disponible pour la planification")
                return
            
            # Initialiser le moteur
            engine = PlanningEngine(
                nb_workers_gen=nb_workers_gen,
                nb_workers_i=nb_workers_i,
                jars_per_day_per_worker=jars_per_day,
                jars_per_box=jars_per_box
            )
            
            # Préparer les données
            df_prepared = engine.prepare_data(
                df,
                date_ref=pd.Timestamp(date_ref),
                threshold_brahy=threshold_brahy,
                threshold_other=threshold_other
            )
            
            # Créer le planning
            result = engine.create_weekly_schedule(
                df_prepared,
                monday_date=week_start
            )
            
            # Sauvegarder dans session state
            st.session_state['planning_result'] = result
            st.session_state['df_prepared'] = df_prepared
            st.session_state['planning_engine'] = engine
        
        st.success("✅ Planning généré avec regroupement par souche !")
    
    # ========== AFFICHAGE DES RÉSULTATS ==========
    if 'planning_result' in st.session_state:
        
        result = st.session_state['planning_result']
        df_prepared = st.session_state['df_prepared']
        engine = st.session_state.get('planning_engine')
        
        # Si engine n'existe pas (ancien résultat), le recréer
        if engine is None:
            engine = PlanningEngine(
                nb_workers_gen=nb_workers_gen,
                nb_workers_i=nb_workers_i,
                jars_per_day_per_worker=jars_per_day
            )
        
        st.markdown("---")
        
        # ========== ONGLETS ==========
        tab1, tab2, tab3, tab4 = st.tabs(["📅 Calendrier", "📊 KPI", "📋 Rapports", "🔍 Debug"])
        
        # ========== TAB 1 : CALENDRIER ==========
        with tab1:
            st.subheader(f"📅 Semaine du {result['week_start'].strftime('%d/%m/%Y')}")
            st.caption("🎨 Couleur = Souche différente | 📦 Nombre = Bocaux")
            
            weekdays = result['weekdays']
            slots = result['slots']
            schedule = result['schedule']
            
            # Couleurs par souche (palette simple)
            strain_colors = {}
            colors_palette = [
                '#e3f2fd', '#fff3e0', '#f3e5f5', '#e8f5e9', '#fce4ec',
                '#e0f2f1', '#fff9c4', '#ede7f6', '#e1f5fe', '#f1f8e9'
            ]
            
            # Afficher le calendrier en grille
            for day_idx, day in enumerate(weekdays):
                st.markdown(f"### {day}")
                
                # 2 colonnes : Matin / Après-midi
                col_matin, col_aprem = st.columns(2)
                
                for col, slot in zip([col_matin, col_aprem], slots):
                    with col:
                        st.markdown(f"**{'🌅' if slot == 'Matin' else '🌆'} {slot} (8h-12h)** " if slot == 'Matin' else f"**{'🌆'} {slot} (13h-17h)**")
                        
                        # Pool Général
                        st.markdown("*🔵 Pool Général*")
                        items_gen = schedule['pool_gen'][day][slot]
                        
                        if items_gen:
                            # Grouper par souche pour affichage
                            strains_in_slot = {}
                            for item in items_gen:
                                strain = item['strain_code']
                                if strain not in strains_in_slot:
                                    strains_in_slot[strain] = []
                                strains_in_slot[strain].append(item)
                            
                            # Afficher par souche
                            for strain, items in strains_in_slot.items():
                                # Assigner couleur
                                if strain not in strain_colors:
                                    strain_colors[strain] = colors_palette[len(strain_colors) % len(colors_palette)]
                                
                                color = strain_colors[strain]
                                total_jars = sum(item['jars'] for item in items)
                                nb_items = len(items)
                                avg_age = sum(item['age_weeks'] for item in items) / nb_items
                                
                                st.markdown(f"""
                                <div style="background-color: {color}; padding: 8px; border-radius: 5px; margin-bottom: 5px; border-left: 4px solid #1976d2;">
                                    <strong style="font-size: 1.1em;">{strain}</strong><br/>
                                    📦 {int(total_jars)} bocaux • {nb_items} série(s) • ⏱️ {int(avg_age)} sem.<br/>
                                    <small>Séries: {', '.join([str(item.get('batch_lines', item.get('line', '?'))) for item in items[:3]])}{' ...' if len(items) > 3 else ''}</small>
                                </div>
                                """, unsafe_allow_html=True)
                        else:
                            st.info("—")
                        
                        # Pool i
                        st.markdown("*🟢 Pool 'i'*")
                        items_i = schedule['pool_i'][day][slot]
                        
                        if items_i:
                            # Grouper par souche
                            strains_in_slot = {}
                            for item in items_i:
                                strain = item['strain_code']
                                if strain not in strains_in_slot:
                                    strains_in_slot[strain] = []
                                strains_in_slot[strain].append(item)
                            
                            for strain, items in strains_in_slot.items():
                                if strain not in strain_colors:
                                    strain_colors[strain] = colors_palette[len(strain_colors) % len(colors_palette)]
                                
                                color = strain_colors[strain]
                                total_jars = sum(item['jars'] for item in items)
                                nb_items = len(items)
                                avg_age = sum(item['age_weeks'] for item in items) / nb_items
                                
                                st.markdown(f"""
                                <div style="background-color: {color}; padding: 8px; border-radius: 5px; margin-bottom: 5px; border-left: 4px solid #388e3c;">
                                    <strong style="font-size: 1.1em;">{strain}</strong><br/>
                                    📦 {int(total_jars)} bocaux • {nb_items} série(s) • ⏱️ {int(avg_age)} sem.<br/>
                                    <small>Séries: {', '.join([str(item.get('batch_lines', item.get('line', '?'))) for item in items[:3]])}{' ...' if len(items) > 3 else ''}</small>
                                </div>
                                """, unsafe_allow_html=True)
                        else:
                            st.info("—")
                
                st.markdown("---")
        
        # ========== TAB 2 : KPI ==========
        with tab2:
            st.subheader("📊 Indicateurs de Performance")
            
            stats = result['stats']
            
            # KPI globaux
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Éligibles", stats['total_eligible'])
            
            with col2:
                st.metric("Planifiés", stats['total_planned'])
            
            with col3:
                st.metric("Backlog", stats['total_backlog'])
            
            with col4:
                taux_planif = (stats['total_planned'] / stats['total_eligible'] * 100) if stats['total_eligible'] > 0 else 0
                st.metric("Taux planification", f"{taux_planif:.1f}%")
            
            st.markdown("---")
            
            # Bocaux par pool
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric("Bocaux planifiés (Général)", f"{int(stats['jars_planned_gen']):,}")
            
            with col2:
                st.metric("Bocaux planifiés (i)", f"{int(stats['jars_planned_i']):,}")
            
            st.markdown("---")
            
            # Capacités par créneau
            st.subheader("Utilisation des capacités par créneau")
            
            # Pool Général
            st.markdown("**🔵 Pool Général**")
            
            cap_gen_data = []
            for day in weekdays:
                for slot in slots:
                    key = f"{day}_{slot}"
                    cap_gen_data.append({
                        'Jour': day,
                        'Créneau': slot,
                        'Utilisé': int(stats['capacity_used_gen'][key]),
                        'Disponible': engine.cap_gen_half_day - int(stats['capacity_used_gen'][key]),
                        'Total': engine.cap_gen_half_day,
                        'Utilisation (%)': f"{stats['capacity_pct_gen'][key]:.1f}%"
                    })
            
            df_cap_gen = pd.DataFrame(cap_gen_data)
            st.dataframe(df_cap_gen, use_container_width=True, hide_index=True)
            
            # Pool i
            st.markdown("**🟢 Pool 'i' (Spécialistes)**")
            
            cap_i_data = []
            for day in weekdays:
                for slot in slots:
                    key = f"{day}_{slot}"
                    cap_i_data.append({
                        'Jour': day,
                        'Créneau': slot,
                        'Utilisé': int(stats['capacity_used_i'][key]),
                        'Disponible': engine.cap_i_half_day - int(stats['capacity_used_i'][key]),
                        'Total': engine.cap_i_half_day,
                        'Utilisation (%)': f"{stats['capacity_pct_i'][key]:.1f}%"
                    })
            
            df_cap_i = pd.DataFrame(cap_i_data)
            st.dataframe(df_cap_i, use_container_width=True, hide_index=True)
        
        # ========== TAB 3 : RAPPORTS ==========
        with tab3:
            st.subheader("📋 Rapports d'export")
            
            # Planifié
            st.markdown("### ✅ Items planifiés")
            if not result['planned'].empty:
                cols_display = ['scheduled_day', 'scheduled_slot', 'scheduled_pool', 'barcode', 'strain_code', 
                               'medium_code', 'jars', 'age_weeks', 'chambre']
                st.dataframe(result['planned'][cols_display], use_container_width=True, hide_index=True)
                
                # Export CSV
                csv_planned = result['planned'][cols_display].to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Télécharger les items planifiés (CSV)",
                    data=csv_planned,
                    file_name=f"planning_planifie_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            else:
                st.info("Aucun item planifié")
            
            st.markdown("---")
            
            # Backlog
            st.markdown("### ⏳ Backlog (non planifiés)")
            if not result['backlog'].empty:
                cols_display = ['barcode', 'strain_code', 'medium_code', 'jars', 
                               'age_weeks', 'backlog_reason', 'chambre']
                st.dataframe(result['backlog'][cols_display], use_container_width=True, hide_index=True)
                
                # Export CSV
                csv_backlog = result['backlog'][cols_display].to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Télécharger le backlog (CSV)",
                    data=csv_backlog,
                    file_name=f"planning_backlog_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            else:
                st.success("Aucun item en backlog !")
        
        # ========== TAB 4 : DEBUG ==========
        with tab4:
            st.subheader("🔍 Données sources (debug)")
            
            # Stats d'éligibilité
            st.markdown("### Répartition par éligibilité")
            
            elig_counts = df_prepared['is_eligible'].value_counts()
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Éligibles", elig_counts.get(True, 0))
            with col2:
                st.metric("Non éligibles", elig_counts.get(False, 0))
            
            # Raisons de non-éligibilité
            if not df_prepared[df_prepared['is_eligible'] == False].empty:
                st.markdown("### Raisons de non-éligibilité")
                reason_counts = df_prepared[df_prepared['is_eligible'] == False]['ineligibility_reason'].value_counts()
                st.dataframe(reason_counts.reset_index(), use_container_width=True, hide_index=True)
            
            st.markdown("---")
            
            # Aperçu données brutes
            st.markdown("### Aperçu des données préparées (50 premières lignes)")
            cols_display = ['barcode', 'strain_code', 'medium_code', 'jars', 'age_weeks', 
                           'pool', 'is_eligible', 'ineligibility_reason', 'chambre']
            st.dataframe(df_prepared[cols_display].head(50), use_container_width=True, hide_index=True)