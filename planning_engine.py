import pandas as pd
from datetime import datetime, timedelta
import re

class PlanningEngine:
    """Moteur de planification des repiquages hebdomadaires avec regroupement par souche"""
    
    # Milieux éligibles pour le planning
    ELIGIBLE_MEDIUMS = {'X', 'XM', 'RG', 'XS', 'E', 'E+', 'i'}
    
    # Milieux pour le pool spécialisé "i"
    POOL_I_MEDIUMS = {'XM', 'i'}
    
    # Milieux pour le pool général
    POOL_GEN_MEDIUMS = {'X', 'RG', 'XS', 'E', 'E+'}
    
    def __init__(self, 
                 nb_workers_gen=17,
                 nb_workers_i=3,
                 jars_per_day_per_worker=50,
                 jars_per_box=14):
        """
        Initialise le moteur de planification
        
        Args:
            nb_workers_gen: Nombre de travailleurs généraux (défaut: 17)
            nb_workers_i: Nombre de spécialistes "i" (défaut: 3)
            jars_per_day_per_worker: Vitesse en bocaux/JOUR/travailleur (défaut: 50)
            jars_per_box: Nombre de bocaux par caisse (défaut: 14)
        """
        self.nb_workers_gen = nb_workers_gen
        self.nb_workers_i = nb_workers_i
        self.jars_per_day_per_worker = jars_per_day_per_worker
        self.jars_per_box = jars_per_box
        
        # Capacités par DEMI-JOURNÉE (matin OU après-midi)
        # 50 bocaux/jour = 25 bocaux par demi-journée
        jars_per_half_day = jars_per_day_per_worker / 2
        
        self.cap_gen_half_day = int(nb_workers_gen * jars_per_half_day)
        self.cap_i_half_day = int(nb_workers_i * jars_per_half_day)
        
        # Pour info : bocaux par heure (7h effectives par jour)
        self.jars_per_hour_per_worker = jars_per_day_per_worker / 7
    
    def extract_date_from_barcode(self, barcode):
        """
        Extrait la date depuis le code-barre (format: YYYYMMDD)
        Ex: 735820250912AW2 → 2025-09-12
        """
        if pd.isna(barcode):
            return None
        
        # Chercher une séquence de 8 chiffres (YYYYMMDD)
        match = re.search(r'(\d{8})', str(barcode))
        if match:
            date_str = match.group(1)
            try:
                return pd.to_datetime(date_str, format='%Y%m%d')
            except:
                return None
        return None
    
    def calculate_age_weeks(self, date_plant, date_ref):
        """Calcule l'âge en semaines"""
        if pd.isna(date_plant) or pd.isna(date_ref):
            return None
        
        delta = date_ref - date_plant
        return int(delta.days / 7)
    
    def is_eligible(self, row, date_ref, threshold_brahy=4, threshold_other=8):
        """
        Vérifie si une série est éligible pour repiquage
        
        Règles:
        - BRAHY sur X, XM, E, E+ : toutes les 4 semaines
        - Autres : toutes les 8 semaines
        - Ignorer les chambres froides
        - Milieux éligibles uniquement
        """
        # Ignorer chambre froide
        chambre = str(row.get('chambre', '')).upper()
        if 'CHF' in chambre or 'FROID' in chambre:
            return False, "Chambre froide"
        
        # Vérifier milieu éligible
        milieu = str(row.get('medium_code', row.get('milieu', ''))).upper()
        if milieu not in self.ELIGIBLE_MEDIUMS:
            return False, "Milieu non éligible"
        
        # Calculer âge
        age_weeks = row.get('age_weeks')
        if pd.isna(age_weeks):
            return False, "Âge inconnu"
        
        # Déterminer seuil selon souche et milieu
        strain = str(row.get('strain_code', row.get('strain', ''))).upper()
        
        if strain == 'BRAHY' and milieu in {'X', 'XM', 'E', 'E+'}:
            threshold = threshold_brahy
        else:
            threshold = threshold_other
        
        if age_weeks >= threshold:
            return True, None
        else:
            return False, f"Trop jeune ({age_weeks}sem < {threshold}sem)"
    
    def assign_pool(self, milieu):
        """Assigne un pool selon le milieu"""
        milieu = str(milieu).upper()
        
        if milieu in self.POOL_I_MEDIUMS:
            return 'pool_i'
        elif milieu in self.POOL_GEN_MEDIUMS:
            return 'pool_gen'
        else:
            return None
    
    def prepare_data(self, df, date_ref=None, threshold_brahy=4, threshold_other=8):
        """
        Prépare les données pour la planification
        
        Args:
            df: DataFrame avec colonnes: barcode, strain_code, medium_code, 
                total_jars, nb_boxes, nb_jars_per_box, chambre, nb_weeks
            date_ref: Date de référence (défaut: aujourd'hui)
            
        Returns:
            DataFrame enrichi avec: age_weeks, pool, is_eligible, ineligibility_reason
        """
        if date_ref is None:
            date_ref = pd.Timestamp.now()
        
        df = df.copy()
        
        # OPTION 1 : Utiliser nb_weeks si disponible
        if 'nb_weeks' in df.columns:
            df['age_weeks'] = df['nb_weeks']
        else:
            # OPTION 2 : Extraire dates depuis barcode (fallback)
            df['date_plant'] = df['barcode'].apply(self.extract_date_from_barcode)
            
            # Calculer âge en semaines
            df['age_weeks'] = df['date_plant'].apply(
                lambda x: self.calculate_age_weeks(x, date_ref) if pd.notna(x) else None
            )
        
        # Normaliser bocaux (si pas fourni, calculer depuis caisses)
        if 'total_jars' in df.columns:
            df['jars'] = df['total_jars'].fillna(0)
        else:
            df['jars'] = (
                df.get('nb_boxes', 0).fillna(0) * self.jars_per_box +
                df.get('nb_jars_per_box', 0).fillna(0)
            )
        
        # Vérifier éligibilité
        eligibility_results = df.apply(
            lambda row: self.is_eligible(row, date_ref, threshold_brahy, threshold_other),
            axis=1
        )
        
        df['is_eligible'] = eligibility_results.apply(lambda x: x[0])
        df['ineligibility_reason'] = eligibility_results.apply(lambda x: x[1])
        
        # Assigner pool
        df['pool'] = df.apply(
            lambda row: self.assign_pool(row.get('medium_code', row.get('milieu', ''))),
            axis=1
        )
        
        return df
    
    def create_weekly_schedule(self, df, monday_date=None, allow_split=False):
        """
        Crée l'agenda hebdomadaire avec regroupement par souche
        
        Args:
            df: DataFrame préparé (sortie de prepare_data)
            monday_date: Date du lundi (défaut: lundi de la semaine courante)
            allow_split: Autoriser le split d'items sur plusieurs jours (défaut: False)
            
        Returns:
            dict avec:
                - 'schedule': Dict avec structure [pool][day][slot] = items
                - 'planned': DataFrame des items planifiés
                - 'backlog': DataFrame des items non planifiés
                - 'stats': Dict des statistiques
        """
        if monday_date is None:
            # Trouver le lundi de la semaine courante
            today = datetime.now()
            monday_date = today - timedelta(days=today.weekday())
        
        # Jours de la semaine
        weekdays = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi']
        slots = ['Matin', 'Après-midi']
        
        # Filtrer éligibles
        eligible = df[df['is_eligible'] == True].copy()
        
        # Séparer par pool
        pool_gen_items = eligible[eligible['pool'] == 'pool_gen'].copy()
        pool_i_items = eligible[eligible['pool'] == 'pool_i'].copy()
        
        # REGROUPER PAR SOUCHE et trier par âge moyen décroissant
        def group_by_strain(items_df):
            if items_df.empty:
                return []
            
            strain_groups = items_df.groupby('strain_code').agg({
                'age_weeks': 'mean',
                'jars': 'sum'
            }).reset_index()
            
            # Trier par âge moyen décroissant (plus vieux d'abord)
            strain_groups = strain_groups.sort_values('age_weeks', ascending=False)
            
            # Créer une liste ordonnée de souches
            strain_order = []
            for _, row in strain_groups.iterrows():
                strain_code = row['strain_code']
                strain_items = items_df[items_df['strain_code'] == strain_code].copy()
                # Trier les items de cette souche par âge décroissant
                strain_items = strain_items.sort_values('age_weeks', ascending=False)
                strain_order.append({
                    'strain': strain_code,
                    'avg_age': row['age_weeks'],
                    'total_jars': row['jars'],
                    'items': strain_items
                })
            
            return strain_order
        
        strains_gen = group_by_strain(pool_gen_items)
        strains_i = group_by_strain(pool_i_items)
        
        # Initialiser capacités par créneau (jour × slot)
        capacities = {
            'pool_gen': {day: {slot: self.cap_gen_half_day for slot in slots} for day in weekdays},
            'pool_i': {day: {slot: self.cap_i_half_day for slot in slots} for day in weekdays}
        }
        
        # Initialiser agenda
        schedule = {
            'pool_gen': {day: {slot: [] for slot in slots} for day in weekdays},
            'pool_i': {day: {slot: [] for slot in slots} for day in weekdays}
        }
        
        planned = []
        backlog = []
        
        # Créer une liste ordonnée des créneaux (lundi matin, lundi aprem, mardi matin, etc.)
        time_slots = []
        for day in weekdays:
            for slot in slots:
                time_slots.append((day, slot))
        
        # Fonction pour placer un groupe de souches
        def place_strain_group(strain_group, pool_name, pool_capacities, pool_schedule):
            strain_code = strain_group['strain']
            items_df = strain_group['items']
            
            # Pour chaque item de cette souche
            for idx, item in items_df.iterrows():
                jars = item['jars']
                placed = False
                
                # Chercher le premier créneau avec assez de capacité
                for day, slot in time_slots:
                    if pool_capacities[day][slot] >= jars:
                        # Placer l'item
                        pool_capacities[day][slot] -= jars
                        pool_schedule[day][slot].append(item)
                        
                        item_planned = item.copy()
                        item_planned['scheduled_day'] = day
                        item_planned['scheduled_slot'] = slot
                        item_planned['scheduled_pool'] = pool_name
                        planned.append(item_planned)
                        placed = True
                        break
                
                if not placed:
                    # Pas de place trouvée
                    item_backlog = item.copy()
                    item_backlog['backlog_reason'] = 'Capacité insuffisante'
                    backlog.append(item_backlog)
        
        # Placer les souches du pool général (par ordre d'âge moyen décroissant)
        for strain_group in strains_gen:
            place_strain_group(strain_group, 'pool_gen', capacities['pool_gen'], schedule['pool_gen'])
        
        # Placer les souches du pool i
        for strain_group in strains_i:
            place_strain_group(strain_group, 'pool_i', capacities['pool_i'], schedule['pool_i'])
        
        # Convertir en DataFrames
        planned_df = pd.DataFrame(planned) if planned else pd.DataFrame()
        backlog_df = pd.DataFrame(backlog) if backlog else pd.DataFrame()
        
        # Calculer statistiques
        stats = {
            'total_eligible': len(eligible),
            'total_planned': len(planned),
            'total_backlog': len(backlog),
            'jars_planned_gen': planned_df[planned_df['scheduled_pool'] == 'pool_gen']['jars'].sum() if not planned_df.empty else 0,
            'jars_planned_i': planned_df[planned_df['scheduled_pool'] == 'pool_i']['jars'].sum() if not planned_df.empty else 0,
            'capacity_used_gen': {},
            'capacity_used_i': {},
            'capacity_pct_gen': {},
            'capacity_pct_i': {},
        }
        
        # Calculer utilisation par créneau
        for day in weekdays:
            for slot in slots:
                key = f"{day}_{slot}"
                
                stats['capacity_used_gen'][key] = self.cap_gen_half_day - capacities['pool_gen'][day][slot]
                stats['capacity_used_i'][key] = self.cap_i_half_day - capacities['pool_i'][day][slot]
                
                stats['capacity_pct_gen'][key] = (stats['capacity_used_gen'][key] / self.cap_gen_half_day * 100)
                stats['capacity_pct_i'][key] = (stats['capacity_used_i'][key] / self.cap_i_half_day * 100)
        
        return {
            'schedule': schedule,
            'planned': planned_df,
            'backlog': backlog_df,
            'stats': stats,
            'week_start': monday_date,
            'weekdays': weekdays,
            'slots': slots
        }
    
    def export_report(self, result, filename_prefix='planning'):
        """
        Exporte le rapport en CSV
        
        Args:
            result: Résultat de create_weekly_schedule
            filename_prefix: Préfixe du nom de fichier
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Export planifié
        if not result['planned'].empty:
            planned_file = f"{filename_prefix}_planifie_{timestamp}.csv"
            cols_export = ['scheduled_day', 'scheduled_slot', 'scheduled_pool', 'barcode', 
                          'strain_code', 'medium_code', 'jars', 'age_weeks', 'chambre', 'emplacement']
            result['planned'][cols_export].to_csv(planned_file, index=False, encoding='utf-8')
        
        # Export backlog
        if not result['backlog'].empty:
            backlog_file = f"{filename_prefix}_backlog_{timestamp}.csv"
            cols_export = ['barcode', 'strain_code', 'medium_code', 'jars', 
                          'age_weeks', 'backlog_reason']
            result['backlog'][cols_export].to_csv(backlog_file, index=False, encoding='utf-8')
        
        return planned_file if not result['planned'].empty else None, \
               backlog_file if not result['backlog'].empty else None