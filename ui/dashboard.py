import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from pathlib import Path
import sys

# Ajout du répertoire parent au path pour l'import des modules
sys.path.append(str(Path(__file__).parent.parent))

from models.property import Property
from models.scenario import Scenario, ScenarioConfig

# Constantes pour les plafonds des livrets
LIVRET_A_PLAFOND = 23000
LDD_PLAFOND = 12000

def load_data():
    """Charge les données des biens et la configuration."""
    properties = Property.load_properties('data/properties.json')
    config = ScenarioConfig.from_yaml('data/scenarios.yaml')
    return properties, config

def property_comparison(properties):
    """Affiche la comparaison des biens."""
    st.header("Comparaison des Biens")
    
    # Création du DataFrame pour la comparaison
    data = []
    for p in properties.values():
        data.append({
            'ID': p.id,
            'Adresse': p.adresse,
            'Surface': p.surface,
            'Prix': p.prix,
            'Prix/m²': p.prix_m2,
            'Charges': p.charges_mensuelles,
            'Taxe Foncière': p.taxe_fonciere if p.taxe_fonciere else 0,
            'DPE': p.dpe,
            'Score Transport': p.score_transport()
        })
    
    df = pd.DataFrame(data)
    st.dataframe(df)
    
    # Graphique radar des caractéristiques
    fig = go.Figure()
    
    for p in properties.values():
        fig.add_trace(go.Scatterpolar(
            r=[p.prix_m2/100, p.score_transport(), 
               100 if p.dpe == 'A' else 80 if p.dpe == 'B' else 60 if p.dpe == 'C' else 40 if p.dpe == 'D' else 20,
               len(p.atouts)*10],
            theta=['Prix/m²', 'Transport', 'DPE', 'Atouts'],
            name=p.id
        ))
    
    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])))
    st.plotly_chart(fig)

def scenario_simulation(properties, config):
    """Interface de simulation des scénarios."""
    st.markdown('<p style="color: #ff4b4b; font-size: 1.25rem; font-weight: 600">Simulation des Scénarios</p>', unsafe_allow_html=True)
    
    # Création des colonnes principales (1:2 ratio)
    col_gauche, col_droite = st.columns([1, 2])
    
    with col_gauche:
        montant_total = st.number_input("Total à investir (€)", min_value=0, max_value=1000000, value=int(config.apport_total), step=1000)
        apport_immo = st.number_input("Apport appartement (€)", min_value=0, max_value=1000000, value=int(config.apport_total * config.repartition_immobilier / 100), step=1000)
        horizon = st.number_input("Horizon simulation (années)", 5, 30, config.horizon_simulation, step=1)

    with col_droite:
        # Sélection du bien
        selected_property = st.selectbox(
            "Sélectionner un bien",
            options=list(properties.keys()),
            format_func=lambda x: properties[x].adresse
        )
        
        # Sous-colonnes pour détails et négociation
        col_details, col_negociation = st.columns(2)
        
        # Calculs communs
        honoraires = properties[selected_property].prix - properties[selected_property].prix_hors_honoraires
        frais_agence_note = "(en direct)" if honoraires == 0 else "(charge vendeur)"
        
        # Affichage dans col_details
        with col_details:
            st.markdown(f"""<small>
<span style="color: #666666">Surface:</span> {properties[selected_property].surface}m² | <span style="color: #666666">Prix initial:</span> {properties[selected_property].prix:,.0f}€<br>
<span style="color: #666666">Prix/m²:</span> {properties[selected_property].prix_m2:,.0f}€<br>
<span style="color: #666666">Frais d'agence:</span> {honoraires:,.0f}€ {frais_agence_note}
</small>""", unsafe_allow_html=True)

            # Ajout du champ de négociation
            negociation = st.slider(
                "Négociation (%)",
                min_value=0,
                max_value=15,
                value=0,
                step=1,
                help="Pourcentage de remise négociée sur le prix"
            )
        
        prix_negocie = properties[selected_property].prix * (1 - negociation/100)
        prix_m2_negocie = prix_negocie / properties[selected_property].surface
        
        # Calcul des frais de notaire et du coût total
        if properties[selected_property].frais_agence_acquereur:
            base_frais_notaire = prix_negocie
            frais_notaire = base_frais_notaire * 0.08
            cout_total = prix_negocie + frais_notaire
            frais_agence_note = "(charge acquéreur)"
        else:
            base_frais_notaire = properties[selected_property].prix_hors_honoraires * (1 - negociation/100)
            frais_notaire = base_frais_notaire * 0.08
            cout_total = prix_negocie + frais_notaire

        # Affichage dans col_negociation
        with col_negociation:
            st.markdown(f"""<small>
<span style="color: #666666">Prix négocié:</span> {prix_negocie:,.0f}€ <span style="color: {'#32CD32' if negociation > 0 else '#666666'}">(-{negociation}%)</span><br>
<span style="color: #666666">Prix/m²:</span> {prix_m2_negocie:,.0f}€<br>
<span style="color: #666666">Notaire (8%):</span> {frais_notaire:,.0f}€<br>
<span style="color: #666666">Coût total:</span> <b>{cout_total:,.0f}€</b>
</small>""", unsafe_allow_html=True)

    # Deuxième ligne avec 3 colonnes
    col_credit, col_epargne, col_resultats = st.columns(3)
    
    with col_credit:
        st.markdown('<p style="color: #ff4b4b; font-size: 1.25rem; font-weight: 600">Crédit</p>', unsafe_allow_html=True)
        # Calcul du montant du prêt basé uniquement sur l'apport immobilier et le coût total
        montant_pret = max(0, cout_total - apport_immo)  # Ne peut pas être négatif
        taux = st.number_input("Taux crédit (%)", 0.0, 10.0, config.taux_credit, step=0.05, format="%.2f")
        duree = st.number_input("Durée crédit (années)", 5, 25, config.duree_credit, step=1)
        appreciation = st.number_input("Valorisation annuelle (%)", -2.0, 5.0, config.evolution_immobilier, step=0.1, format="%.1f")

        # Calcul simple des mensualités
        taux_mensuel = taux / 12 / 100
        nombre_mois = duree * 12
        if taux_mensuel > 0:
            mensualite = montant_pret * (taux_mensuel * (1 + taux_mensuel)**nombre_mois) / ((1 + taux_mensuel)**nombre_mois - 1)
        else:
            mensualite = montant_pret / nombre_mois
            
        # Calcul de l'assurance
        assurance_mensuelle = (montant_pret * config.taux_assurance / 100) / 12
        mensualite_totale = mensualite + assurance_mensuelle
        
        # Calcul des charges totales
        total_charges = (mensualite_totale + 
                        properties[selected_property].charges_mensuelles +
                        (properties[selected_property].energie if properties[selected_property].energie else 0) +
                        (properties[selected_property].taxe_fonciere/12 if properties[selected_property].taxe_fonciere else 0))

        st.metric("Charges totales", f"{total_charges:.2f}€")
        charges_detail = f"""<div style="margin-top: -1rem">
<small>
<span style="color: #666666">Prêt:</span> {montant_pret:,.0f}€<br>
<span style="color: #666666">Mensualités:</span> {mensualite:.2f}€<br>
<span style="color: #666666">Assurance prêt ({config.taux_assurance}%):</span> {assurance_mensuelle:.2f}€<br>
<span style="color: #666666">Copropriété:</span> {'<span style="color: red">' if properties[selected_property].charges_mensuelles == 0 else ''}{properties[selected_property].charges_mensuelles:.2f}€{'</span>' if properties[selected_property].charges_mensuelles == 0 else ''}<br>
<span style="color: #666666">Énergie:</span> {'<span style="color: red">' if not properties[selected_property].energie else ''}{properties[selected_property].energie if properties[selected_property].energie else 0:.2f}€{'</span>' if not properties[selected_property].energie else ''}<br>
<span style="color: #666666">Taxe foncière:</span> {'<span style="color: red">' if not properties[selected_property].taxe_fonciere else ''}{properties[selected_property].taxe_fonciere/12 if properties[selected_property].taxe_fonciere else 0:.2f}€ ({properties[selected_property].taxe_fonciere if properties[selected_property].taxe_fonciere else 0:.0f}€/an){'</span>' if not properties[selected_property].taxe_fonciere else ''}
</small>
</div>"""
        st.markdown(charges_detail, unsafe_allow_html=True)

    with col_epargne:
        st.markdown('<p style="color: #ff4b4b; font-size: 1.25rem; font-weight: 600">Épargne</p>', unsafe_allow_html=True)
        # Calcul des montants
        montant_hors_immo = montant_total - apport_immo
        repartition_epargne = st.number_input("Part sécurisée (%)", 0, 100, 50, step=5)
        
        montant_securise = montant_hors_immo * (repartition_epargne / 100)
        montant_dynamique = montant_hors_immo * (1 - repartition_epargne / 100)
        
        rdt_securise = st.number_input(
            "Taux placement sécurisé (%)", 
            0.0, 5.0, config.rendement_epargne, step=0.1, format="%.1f"
        )
        rdt_risque = st.number_input(
            "Taux placement dynamique (%)", 
            2.0, 12.0, config.rendement_investissement, step=0.1, format="%.1f"
        )
    
    # Mise à jour de la configuration avec le coût total
    config.apport_total = montant_total
    config.repartition_immobilier = (apport_immo / montant_total) * 100 if montant_total > 0 else 0
    config.repartition_epargne = (100 - config.repartition_immobilier) * (repartition_epargne / 100)
    config.repartition_investissement = (100 - config.repartition_immobilier) * (1 - repartition_epargne / 100)
    config.taux_credit = taux
    config.duree_credit = duree
    config.horizon_simulation = horizon
    config.evolution_immobilier = appreciation
    config.rendement_epargne = rdt_securise
    config.rendement_investissement = rdt_risque
    
    # Création et exécution du scénario avec le coût total
    scenario = Scenario(properties[selected_property], config, cout_total=cout_total)
    simulation = scenario.simulate_patrimoine()
    metrics = scenario.calculate_metrics()
    
    with col_resultats:
        st.markdown(f'<p style="color: #ff4b4b; font-size: 1.25rem; font-weight: 600; margin: 0; padding: 0">Résultats à {horizon} ans</p>', unsafe_allow_html=True)
        
        # Récupération des valeurs nécessaires
        horizon_mois = horizon * 12
        capital_restant_horizon = simulation['capital_restant'][horizon_mois]
        valeur_bien_horizon = simulation['valeur_bien'][horizon_mois]
        epargne_horizon = simulation['epargne'][horizon_mois] + simulation['investissement'][horizon_mois]
        frais_agence_revente = valeur_bien_horizon * 0.05  # Estimation 5% frais d'agence à la revente
        penalites = capital_restant_horizon * 0.03 if horizon < config.duree_credit else 0

        patrimoine_detail = f"""<small><br>
<b style="color: #ff4b4b">Épargne</b><br>
<span style="font-size: 1.5rem">{epargne_horizon:,.0f}€</span><br>

<b style="color: #ff4b4b">Immobilier</b><br>
<span style="color: #666666">Bien évalué à:</span><br>
<span style="font-size: 1.5rem">{valeur_bien_horizon:,.0f}€</span><br><br>
<span style="color: #666666">Si revente</span><br>
"""
        if horizon < config.duree_credit:
            patrimoine_detail += f"""<i style="color: #ff4b4b">Capital restant dû: -{capital_restant_horizon:,.0f}€<br>
Pénalités (3%): -{penalites:,.0f}€</i><br>
"""
        total_revente = valeur_bien_horizon - capital_restant_horizon - penalites - frais_agence_revente
        plus_value_immo = total_revente - cout_total

        patrimoine_detail += f"""<span style="color: #666666">Frais d'agence (5%):</span> -{frais_agence_revente:,.0f}€<br>
<span style="color: #666666">Total revente:</span><br>
<span style="font-size: 1.5rem">{total_revente:,.0f}€</span><br>
<span style="color: #666666">Plus-value immobilière:</span> {plus_value_immo:+,.0f}€<br><br>

<b style="color: #ff4b4b">Patrimoine final:</b><br>
<span style="font-size: 2.5rem">{total_revente + epargne_horizon:,.0f}€</span></small>"""

        st.markdown(patrimoine_detail, unsafe_allow_html=True)
    
    # Affichage de la répartition dans la colonne de droite
    with col_epargne:
        # Calcul de la répartition de l'épargne sécurisée
        livret_a = min(montant_securise, LIVRET_A_PLAFOND)
        reste_apres_livret_a = montant_securise - livret_a
        ldd = min(reste_apres_livret_a, LDD_PLAFOND)
        compte_terme = max(0, reste_apres_livret_a - ldd)
        
        # Calcul du rendement moyen de l'épargne sécurisée
        rendement_moyen = 0
        montant_total_epargne = montant_securise + montant_dynamique
        if montant_total_epargne > 0:
            rendement_moyen = (
                (livret_a * config.rendement_epargne + 
                 ldd * config.rendement_epargne + 
                 compte_terme * (config.rendement_epargne - 2) +
                 montant_dynamique * config.rendement_investissement) / montant_total_epargne
            )
        
        st.metric("Rendement épargne moyen", f"{rendement_moyen:.2f}%")
        repartition_detail = f"""<div style="margin-top: -1rem">
<small>
<span style="color: #666666">Épargne sécurisée :</span><br>
• <span style="color: #666666">Livret A ({config.rendement_epargne}%) :</span> {livret_a:,.0f}€<br>
• <span style="color: #666666">LDD ({config.rendement_epargne}%) :</span> {ldd:,.0f}€<br>
{f"• <span style='color: #666666'>Compte à terme ({config.rendement_epargne-2}%) :</span> {compte_terme:,.0f}€<br>" if compte_terme > 0 else ""}
<span style="color: #666666">Épargne dynamique :</span><br>
• <span style="color: #666666">PEA ({config.rendement_investissement}%) :</span> {montant_dynamique:,.0f}€
</small>
</div>"""
        st.markdown(repartition_detail, unsafe_allow_html=True)
    
    # Graphique d'évolution du patrimoine
    df_evolution = pd.DataFrame({
        'Années': [i/12 for i in range(len(simulation['patrimoine_total']))],
        'Patrimoine Total': simulation['patrimoine_total'],
        'Valeur Bien': simulation['valeur_bien'],
        'Capital Restant Dû': simulation['capital_restant'],
        'Épargne Sécurisée': simulation['epargne'],
        'Épargne Dynamique': simulation['investissement']
    })
    
    fig = px.line(df_evolution.melt(id_vars=['Années'], 
                                  value_vars=['Patrimoine Total', 'Valeur Bien', 
                                            'Capital Restant Dû', 'Épargne Sécurisée', 'Épargne Dynamique']),
                  x='Années', y='value', color='variable',
                  title="Évolution du Patrimoine",
                  labels={'value': 'Valeur (€)'})
    
    # Formatage des axes
    fig.update_xaxes(tickformat='.0f')  # Pas de décimales pour les années
    fig.update_yaxes(tickformat=',d')   # Format des montants avec séparateur de milliers
    
    st.plotly_chart(fig)

def property_details(properties):
    """Interface de gestion des biens."""
    st.markdown('<p style="color: #ff4b4b; font-size: 2rem; font-weight: 600">Gestion des Biens</p>', unsafe_allow_html=True)
    
    # Menu de sélection avec option "Nouveau bien"
    options = list(properties.keys())
    options.insert(0, "nouveau_bien")  # Ajout de l'option "nouveau bien"
    
    selected_property = st.selectbox(
        "Sélectionner un bien",
        options=options,
        format_func=lambda x: "Nouveau bien" if x == "nouveau_bien" else properties[x].adresse
    )
    
    # Section Renseignements
    st.markdown('<p style="color: #ff4b4b; font-size: 1.25rem; font-weight: 600">Renseignements</p>', unsafe_allow_html=True)
    if selected_property == "nouveau_bien":
        st.write("Entrez ci-dessous, même en vrac, les détails du bien")
    else:
        st.write("Pour modifier des détails, expliquez les changements ci-dessous")
    
    user_input = st.text_area(
        "",
        height=150,
        help="Entrez les détails ou modifications du bien"
    )
    
    # Section Détails du bien
    st.markdown('<p style="color: #ff4b4b; font-size: 1.25rem; font-weight: 600">Détails du bien</p>', unsafe_allow_html=True)
    if selected_property != "nouveau_bien":
        prop = properties[selected_property]
        
        # Informations générales
        col1, col2 = st.columns(2)
        with col1:
            st.markdown('<p style="color: #ff4b4b; font-weight: 600">Informations générales</p>', unsafe_allow_html=True)
            st.markdown(f'<span style="color: #666666">ID:</span> {prop.id}', unsafe_allow_html=True)
            st.markdown(f'<span style="color: #666666">Adresse:</span> {prop.adresse}', unsafe_allow_html=True)
            st.markdown(f'<span style="color: #666666">Surface:</span> {prop.surface}m²', unsafe_allow_html=True)
            st.markdown(f'<span style="color: #666666">Prix:</span> {prop.prix:,.0f}€', unsafe_allow_html=True)
            st.markdown(f'<span style="color: #666666">Prix/m²:</span> {prop.prix_m2:,.0f}€', unsafe_allow_html=True)
            
        with col2:
            st.markdown('<p style="color: #ff4b4b; font-weight: 600">Charges & Taxes</p>', unsafe_allow_html=True)
            st.markdown(f'<span style="color: #666666">Charges mensuelles:</span> {prop.charges_mensuelles:,.0f}€', unsafe_allow_html=True)
            st.markdown(f'<span style="color: #666666">Taxe foncière:</span> {prop.taxe_fonciere if prop.taxe_fonciere else "Non spécifié"}', unsafe_allow_html=True)
            st.markdown(f'<span style="color: #666666">Énergie:</span> {prop.energie if prop.energie else "Non spécifié"}', unsafe_allow_html=True)
            st.markdown(f'<span style="color: #666666">DPE:</span> {prop.dpe if prop.dpe else "Non spécifié"}', unsafe_allow_html=True)
            st.markdown(f'<span style="color: #666666">GES:</span> {prop.ges if prop.ges else "Non spécifié"}', unsafe_allow_html=True)
        
        # Transports
        st.markdown('<p style="color: #ff4b4b; font-weight: 600">Transports</p>', unsafe_allow_html=True)
        if prop.metros:
            for metro in prop.metros:
                st.markdown(f'• Ligne {metro.ligne} station {metro.station} à {metro.distance}m', unsafe_allow_html=True)
        else:
            st.markdown('<span style="color: #666666">Aucun transport renseigné</span>', unsafe_allow_html=True)
        
        # Points forts et vigilance
        col1, col2 = st.columns(2)
        with col1:
            st.markdown('<p style="color: #ff4b4b; font-weight: 600">Points forts</p>', unsafe_allow_html=True)
            for atout in prop.atouts:
                st.markdown(f'• {atout}', unsafe_allow_html=True)
                
        with col2:
            st.markdown('<p style="color: #ff4b4b; font-weight: 600">Points de vigilance</p>', unsafe_allow_html=True)
            if prop.vigilance:
                for point in prop.vigilance:
                    st.markdown(f'• {point}', unsafe_allow_html=True)
            else:
                st.markdown('<span style="color: #666666">Aucun point de vigilance signalé</span>', unsafe_allow_html=True)

def main():
    st.title("Analyse Immobilière")
    
    # Chargement des données
    properties, config = load_data()
    
    # Tabs pour la navigation
    tab1, tab2 = st.tabs(["Simulation", "Biens"])
    
    with tab1:
        scenario_simulation(properties, config)
    
    with tab2:
        property_details(properties)

if __name__ == "__main__":
    main() 