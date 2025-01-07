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
        st.subheader("Paramètres Simulation")
        montant_total = st.slider("À investir (€)", 0, 300000, config.apport_total)
        apport_immo = st.slider("Apport appartement (€)", 0, montant_total, int(montant_total * config.repartition_immobilier / 100))
        horizon = st.slider("Horizon simulation (années)", 5, 30, config.horizon_simulation)
        
    with col2:
        st.subheader("Paramètres Crédit")
        taux = st.slider("Taux crédit (%)", 0.0, 10.0, config.taux_credit)
        duree = st.slider("Durée crédit (années)", 5, 25, config.duree_credit)
        appreciation = st.slider("Valorisation annuelle (%)", -2.0, 5.0, config.evolution_immobilier)

    with col3:
        st.subheader("Paramètres Épargne")
        rdt_securise = st.slider("Rendement sécurisé (%)", 0.0, 5.0, config.rendement_epargne)
        rdt_risque = st.slider("Rendement dynamique (%)", 2.0, 12.0, config.rendement_investissement)
        repartition_epargne = st.slider("Part sécurisée (%)", 0, 100, 50)
    
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
    
    # Affichage des métriques
    col1, col2, col3 = st.columns(3)
    col1.metric("Mensualité crédit", f"{metrics['mensualite_credit']:.2f}€")
    
    # Charges totales avec détail
    col2.metric("Charges totales", f"{metrics['charges_totales']:.2f}€")
    charges_detail = f"""
    <small>
    Crédit: {metrics['mensualite_credit']:.2f}€<br>
    Copropriété: {properties[selected_property].charges_mensuelles:.2f}€<br>
    Énergie: {properties[selected_property].energie if properties[selected_property].energie else 0:.2f}€
    </small>
    """
    col2.markdown(charges_detail, unsafe_allow_html=True)
    
    # Rendement avec détail
    col3.metric("Rendement annuel moyen", f"{metrics['rendement_total']:.2f}%")
    rendement_detail = f"""
    <small>
    Patrimoine initial: {metrics['patrimoine_initial']:,.0f}€<br>
    Patrimoine final: {metrics['patrimoine_final']:,.0f}€<br>
    Horizon: {config.horizon_simulation} ans
    </small>
    """
    col3.markdown(rendement_detail, unsafe_allow_html=True)
    
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