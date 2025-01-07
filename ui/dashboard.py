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
    properties = Property.load_properties('data/properties.yaml')
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
    st.header("Simulation des Scénarios")
    
    # Sélection du bien
    selected_property = st.selectbox(
        "Sélectionner un bien",
        options=list(properties.keys()),
        format_func=lambda x: properties[x].adresse
    )
    
    # Paramètres de simulation
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <style>
        div[data-testid="stHorizontalBlock"] > div:nth-child(1) {
            background-color: rgb(38, 39, 48);
            padding: 1rem;
            border-radius: 0.5rem;
        }
        </style>
        """, unsafe_allow_html=True)
        
        st.subheader("Simulation")
        montant_total = st.slider("À investir (€)", 0, 300000, config.apport_total)
        apport_immo = st.slider("Apport appartement (€)", 0, montant_total, int(montant_total * config.repartition_immobilier / 100))
        horizon = st.slider("Horizon simulation (années)", 5, 30, config.horizon_simulation)

    with col2:
        st.subheader("Crédit")
        taux = st.slider("Taux crédit (%)", 0.0, 10.0, config.taux_credit)
        duree = st.slider("Durée crédit (années)", 5, 25, config.duree_credit)
        appreciation = st.slider("Valorisation annuelle (%)", -2.0, 5.0, config.evolution_immobilier)

    with col3:
        st.subheader("Épargne")
        # Calcul des montants
        montant_hors_immo = montant_total - apport_immo
        repartition_epargne = st.slider("Part sécurisée (%)", 0, 100, 50)
        
        montant_securise = montant_hors_immo * (repartition_epargne / 100)
        montant_dynamique = montant_hors_immo * (1 - repartition_epargne / 100)
        
        rdt_securise = st.slider(
            "Rendement sécurisé (%)", 
            0.0, 5.0, config.rendement_epargne
        )
        rdt_risque = st.slider(
            f"Rendement dynamique (%) - {montant_dynamique:,.0f}€", 
            2.0, 12.0, config.rendement_investissement
        )
    
    # Mise à jour de la configuration
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
    
    # Création et exécution du scénario
    scenario = Scenario(properties[selected_property], config)
    simulation = scenario.simulate_patrimoine()
    metrics = scenario.calculate_metrics()
    
    # Affichage des métriques dans la colonne de gauche
    with col1:
        st.metric("Rendement annuel moyen", f"{metrics['rendement_total']:.2f}%")
        rendement_detail = f"""
        <small>
        Patrimoine initial: {metrics['patrimoine_initial']:,.0f}€<br>
        Patrimoine final: {metrics['patrimoine_final']:,.0f}€<br>
        Horizon: {config.horizon_simulation} ans
        </small>
        """
        st.markdown(rendement_detail, unsafe_allow_html=True)
    
    # Affichage des charges dans la colonne du milieu
    with col2:
        # Calcul de vérification du total
        total_charges = (metrics['mensualite_credit'] + 
                        properties[selected_property].charges_mensuelles +
                        (properties[selected_property].energie if properties[selected_property].energie else 0) +
                        (properties[selected_property].taxe_fonciere/12 if properties[selected_property].taxe_fonciere else 0))
        
        st.metric("Charges totales", f"{total_charges:.2f}€")
        charges_detail = f"""
        <small>
        Crédit: {metrics['mensualite_credit']:.2f}€<br>
        Copropriété: {properties[selected_property].charges_mensuelles:.2f}€<br>
        Énergie: {properties[selected_property].energie if properties[selected_property].energie else 0:.2f}€<br>
        Taxe foncière: {properties[selected_property].taxe_fonciere/12 if properties[selected_property].taxe_fonciere else 0:.2f}€ ({properties[selected_property].taxe_fonciere if properties[selected_property].taxe_fonciere else 0:.0f}€/an)
        </small>
        """
        st.markdown(charges_detail, unsafe_allow_html=True)
    
    # Affichage de la répartition dans la colonne de droite
    with col3:
        # Calcul de la répartition de l'épargne sécurisée
        livret_a = min(montant_securise, LIVRET_A_PLAFOND)
        reste_apres_livret_a = montant_securise - livret_a
        ldd = min(reste_apres_livret_a, LDD_PLAFOND)
        compte_terme = max(0, reste_apres_livret_a - ldd)
        
        # Calcul du rendement moyen de l'épargne sécurisée
        rendement_moyen = 0
        if montant_securise > 0:
            rendement_moyen = (
                (livret_a * config.rendement_epargne + 
                 ldd * config.rendement_epargne + 
                 compte_terme * (config.rendement_epargne - 2)) / montant_securise
            )
        
        st.metric("Rendement épargne moyen", f"{rendement_moyen:.2f}%")
        repartition_detail = f"""
        <small>
        Épargne sécurisée :<br>
        • Livret A ({config.rendement_epargne}%) : {livret_a:,.0f}€<br>
        • LDD ({config.rendement_epargne}%) : {ldd:,.0f}€<br>
        {f"• Compte à terme ({config.rendement_epargne-2}%) : {compte_terme:,.0f}€<br>" if compte_terme > 0 else ""}
        <br>
        Épargne dynamique :<br>
        • PEA ({config.rendement_investissement}%) : {montant_dynamique:,.0f}€
        </small>
        """
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

def main():
    st.title("Analyse Immobilière")
    
    # Chargement des données
    properties, config = load_data()
    
    # Tabs pour la navigation
    tab1, tab2 = st.tabs(["Simulation", "Comparaison des Biens"])
    
    with tab1:
        scenario_simulation(properties, config)
    
    with tab2:
        property_comparison(properties)

if __name__ == "__main__":
    main() 