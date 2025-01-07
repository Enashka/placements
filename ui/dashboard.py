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
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Apport et Répartition")
        apport = st.slider("Apport total (€)", 0, 300000, config.apport_total)
        repartition_immo = st.slider("% Immobilier", 0, 100, int(config.repartition_immobilier))
        
    with col2:
        st.subheader("Paramètres Crédit")
        taux = st.slider("Taux crédit (%)", 0.0, 10.0, config.taux_credit)
        duree = st.slider("Durée (années)", 5, 30, config.duree_credit)
    
    # Mise à jour de la configuration
    config.apport_total = apport
    config.repartition_immobilier = repartition_immo
    config.repartition_epargne = (100 - repartition_immo) / 2
    config.repartition_investissement = (100 - repartition_immo) / 2
    config.taux_credit = taux
    config.duree_credit = duree
    
    # Création et exécution du scénario
    scenario = Scenario(properties[selected_property], config)
    simulation = scenario.simulate_patrimoine()
    metrics = scenario.calculate_metrics()
    
    # Affichage des métriques
    col1, col2, col3 = st.columns(3)
    col1.metric("Mensualité crédit", f"{metrics['mensualite_credit']:.2f}€")
    col2.metric("Charges totales", f"{metrics['charges_totales']:.2f}€")
    col3.metric("Rendement total", f"{metrics['rendement_total']:.2f}%")
    
    # Graphique d'évolution du patrimoine
    df_evolution = pd.DataFrame({
        'Mois': range(len(simulation['patrimoine_total'])),
        'Patrimoine Total': simulation['patrimoine_total'],
        'Valeur Bien': simulation['valeur_bien'],
        'Capital Restant': simulation['capital_restant'],
        'Épargne': simulation['epargne'],
        'Investissement': simulation['investissement']
    })
    
    fig = px.line(df_evolution.melt(id_vars=['Mois'], 
                                  value_vars=['Patrimoine Total', 'Valeur Bien', 
                                            'Capital Restant', 'Épargne', 'Investissement']),
                  x='Mois', y='value', color='variable',
                  title="Évolution du Patrimoine")
    st.plotly_chart(fig)

def main():
    st.title("Analyse Immobilière")
    
    # Chargement des données
    properties, config = load_data()
    
    # Tabs pour la navigation
    tab1, tab2 = st.tabs(["Comparaison des Biens", "Simulation"])
    
    with tab1:
        property_comparison(properties)
    
    with tab2:
        scenario_simulation(properties, config)

if __name__ == "__main__":
    main() 