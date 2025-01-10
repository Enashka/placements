import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from pathlib import Path
import sys
import yaml
import json
import os
from openai import OpenAI
from dotenv import load_dotenv
import re

# Ajout du répertoire parent au path pour l'import des modules
sys.path.append(str(Path(__file__).parent.parent))

# Chargement des variables d'environnement
load_dotenv()

# Récupération de la clé API depuis .env ou les secrets de Streamlit
openai_key = os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY")

if not openai_key:
    st.error("⚠️ La clé API OpenAI n'est pas configurée. Certaines fonctionnalités ne seront pas disponibles.")
    st.info("Pour configurer la clé API OpenAI :")
    st.markdown("""
    1. Localement : Ajoutez votre clé dans le fichier `.env`
    2. Sur Streamlit Cloud : Configurez la clé dans les paramètres de l'application (Settings > Secrets)
    """)
    if not st.session_state.get("acknowledged_missing_key"):
        st.stop()
    st.session_state.acknowledged_missing_key = True
else:
    os.environ["OPENAI_API_KEY"] = openai_key

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

def scenario_simulation(properties, config):
    """Interface de simulation des scénarios."""
    st.markdown('<p style="color: #ff4b4b; font-size: 1.25rem; font-weight: 600">Simulation des Scénarios</p>', unsafe_allow_html=True)
    
    # Initialisation de la version des widgets si elle n'existe pas
    if "widget_version" not in st.session_state:
        st.session_state.widget_version = 1
    
    # Vérification s'il y a des biens
    if not properties:
        st.warning("Aucun bien n'est enregistré. Veuillez d'abord ajouter un bien dans l'onglet 'Biens'.")
        return
    
    # Création des colonnes principales (1:2 ratio)
    col_gauche, col_droite = st.columns([1, 2])
    
    with col_gauche:
        montant_total = st.number_input("Total à investir (€)", min_value=0, max_value=1000000, value=int(config.apport_total), step=1000, key=f"montant_total_{st.session_state.widget_version}")
        apport_immo = st.number_input("Apport appartement (€)", min_value=0, max_value=1000000, value=int(config.apport_total * config.repartition_immobilier / 100), step=1000, key=f"apport_immo_{st.session_state.widget_version}")
        horizon = st.number_input("Horizon simulation (années)", 5, 30, config.horizon_simulation, step=1, key=f"horizon_{st.session_state.widget_version}")

    with col_droite:
        # Création de colonnes pour le selectbox et l'icône de réinitialisation
        col_select_bien, col_reset = st.columns([0.9, 0.1])
        
        with col_select_bien:
            # Sélection du bien
            selected_property = st.selectbox(
                "Sélectionner un bien",
                options=list(properties.keys()),
                format_func=lambda x: properties[x].adresse,
                key=f"property_select_{st.session_state.widget_version}"
            )
            
        with col_reset:
            if st.button("🔄", help="Réinitialiser tous les paramètres"):
                # Incrémenter la version pour forcer la réinitialisation des widgets
                st.session_state.widget_version += 1
                st.rerun()
        
        # Sous-colonnes pour détails et négociation
        col_details, col_negociation = st.columns(2)
        
        # Calculs communs
        honoraires = properties[selected_property].prix.annonce - (properties[selected_property].prix.hors_honoraires or 0)
        frais_agence_note = "(en direct)" if honoraires == 0 else "(charge vendeur)"
        
        # Affichage dans col_details
        with col_details:
            st.markdown(f"""<small>
<span style="color: #666666">Surface:</span> {properties[selected_property].bien.surface}m² | <span style="color: #666666">Prix initial:</span> {properties[selected_property].prix.annonce:,.0f}€<br>
<span style="color: #666666">Prix/m²:</span> {properties[selected_property].prix.m2:,.0f}€<br>
<span style="color: #666666">Frais d'agence:</span> {honoraires:,.0f}€ {frais_agence_note}
</small>""", unsafe_allow_html=True)

            # Ajout du champ de négociation
            negociation = st.slider(
                "Négociation (%)",
                min_value=0,
                max_value=15,
                value=0,
                step=1,
                help="Pourcentage de remise négociée sur le prix",
                key=f"negociation_{st.session_state.widget_version}"
            )
        
        prix_negocie = properties[selected_property].prix.annonce * (1 - negociation/100)
        
        # Calcul du prix au m² avec vérification de la surface
        if properties[selected_property].bien.surface and properties[selected_property].bien.surface > 0:
            prix_m2_negocie = prix_negocie / properties[selected_property].bien.surface
        else:
            prix_m2_negocie = 0  # ou None, selon ce qui est préférable pour l'affichage
        
        # Calcul des frais de notaire et du coût total
        if properties[selected_property].prix.frais_agence_acquereur:
            # Si frais d'agence à charge acquéreur : base = prix hors honoraires ou prix annoncé si non défini
            base_frais_notaire = (properties[selected_property].prix.hors_honoraires or properties[selected_property].prix.annonce) * (1 - negociation/100)
            frais_notaire = base_frais_notaire * 0.08
            cout_total = prix_negocie + frais_notaire
            frais_agence_note = "(charge acquéreur)"
        else:
            # Si frais d'agence à charge vendeur : base = prix total
            base_frais_notaire = prix_negocie
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
        taux = st.number_input("Taux crédit (%)", 0.0, 10.0, config.taux_credit, step=0.05, format="%.2f", key=f"taux_{st.session_state.widget_version}")
        duree = st.number_input("Durée crédit (années)", 5, 25, config.duree_credit, step=1, key=f"duree_{st.session_state.widget_version}")
        appreciation = st.number_input("Valorisation annuelle (%)", -2.0, 5.0, config.evolution_immobilier, step=0.1, format="%.1f", key=f"appreciation_{st.session_state.widget_version}")

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
                        (properties[selected_property].charges.mensuelles or 0) +
                        (properties[selected_property].charges.energie if properties[selected_property].charges.energie else 0) +
                        (properties[selected_property].charges.taxe_fonciere/12 if properties[selected_property].charges.taxe_fonciere else 0))

        st.metric("Charges totales", f"{total_charges:.2f}€")
        charges_detail = f"""<div style="margin-top: -1rem">
<small>
<span style="color: #666666">Prêt:</span> {montant_pret:,.0f}€<br>
<span style="color: #666666">Mensualités:</span> {mensualite:.2f}€<br>
<span style="color: #666666">Assurance prêt ({config.taux_assurance}%):</span> {assurance_mensuelle:.2f}€<br>
<span style="color: #666666">Copropriété:</span> {'<span style="color: red">' if not properties[selected_property].charges.mensuelles else ''}{properties[selected_property].charges.mensuelles or 0:.2f}€{'</span>' if not properties[selected_property].charges.mensuelles else ''}<br>
<span style="color: #666666">Énergie:</span> {'<span style="color: red">' if not properties[selected_property].charges.energie else ''}{properties[selected_property].charges.energie if properties[selected_property].charges.energie else 0:.2f}€{'</span>' if not properties[selected_property].charges.energie else ''}<br>
<span style="color: #666666">Taxe foncière:</span> {'<span style="color: red">' if not properties[selected_property].charges.taxe_fonciere else ''}{properties[selected_property].charges.taxe_fonciere/12 if properties[selected_property].charges.taxe_fonciere else 0:.2f}€ ({properties[selected_property].charges.taxe_fonciere if properties[selected_property].charges.taxe_fonciere else 0:.0f}€/an){'</span>' if not properties[selected_property].charges.taxe_fonciere else ''}
</small>
</div>"""
        st.markdown(charges_detail, unsafe_allow_html=True)

    with col_epargne:
        st.markdown('<p style="color: #ff4b4b; font-size: 1.25rem; font-weight: 600">Épargne</p>', unsafe_allow_html=True)
        # Calcul des montants
        montant_hors_immo = montant_total - apport_immo
        repartition_epargne = st.number_input("Part sécurisée (%)", 0, 100, 50, step=5, key=f"repartition_{st.session_state.widget_version}")
        
        montant_securise = montant_hors_immo * (repartition_epargne / 100)
        montant_dynamique = montant_hors_immo * (1 - repartition_epargne / 100)
        
        rdt_securise = st.number_input(
            "Taux placement sécurisé (%)", 
            0.0, 5.0, config.rendement_epargne, step=0.1, format="%.1f",
            key=f"rdt_securise_{st.session_state.widget_version}"
        )
        rdt_risque = st.number_input(
            "Taux placement dynamique (%)", 
            2.0, 12.0, config.rendement_investissement, step=0.1, format="%.1f",
            key=f"rdt_risque_{st.session_state.widget_version}"
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
    
    # Affichage des constantes utilisées dans les calculs
    st.markdown("---")  # Ligne de séparation
    col_constantes1, col_constantes2 = st.columns(2)
    
    with col_constantes1:
        st.markdown(f"""
        <div style="color: #666666; font-style: italic;">
        <p style="margin: 0;">Hypothèses économiques :</p>
        • Inflation : {config.inflation}%/an<br>
        <p style="font-size: 0.8em; margin-top: 0.5em; color: #ff4b4b;">Note : Ces hypothèses sont simplifiées et pourraient varier significativement sur la durée de la simulation ({horizon} ans).</p>
        </div>
        """, unsafe_allow_html=True)
        
    with col_constantes2:
        st.markdown(f"""
        <div style="color: #666666; font-style: italic;">
        <p style="margin: 0;">Évolution des charges :</p>
        • Copropriété : {config.evolution_charges['copropriete']}%/an<br>
        • Taxe foncière : {config.evolution_charges['taxe_fonciere']}%/an<br>
        • Énergie : {config.evolution_charges['energie']}%/an<br>
        <p style="font-size: 0.8em; margin-top: 0.5em; color: #ff4b4b;">Note : Ces taux d'évolution sont des moyennes historiques qui pourraient sous-estimer les augmentations futures.</p>
        </div>
        """, unsafe_allow_html=True)

def load_prompts():
    """Charge les prompts depuis le fichier YAML."""
    with open("data/renseignement-prompt.yaml", "r") as f:
        return yaml.safe_load(f)

def call_openai_api(text: str, existing_property=None):
    """Appelle l'API OpenAI pour extraire les informations du bien."""
    try:
        # Initialisation du client avec la clé API chargée depuis .env
        client = OpenAI()
        prompts = load_prompts()

        # Prépare les messages pour l'API
        messages = [
            {"role": "system", "content": prompts["system"]}
        ]

        if existing_property:
            # Cas de mise à jour : on envoie les détails existants et les nouvelles informations
            prompt = f"""Voici les détails actuels du bien immobilier :
{json.dumps(existing_property, ensure_ascii=False, indent=2)}

Voici de nouvelles informations sur ce bien :
{text}

Veuillez extraire les informations pertinentes et mettre à jour les détails du bien.
Si une information dans le nouveau texte est différente des détails existants, utilisez la nouvelle information.
Si une information n'est pas mentionnée dans le nouveau texte, conservez l'information existante."""
        else:
            # Nouveau bien
            prompt = f"""Voici les informations sur un nouveau bien immobilier :
{text}

Veuillez extraire les informations pertinentes pour créer une nouvelle fiche de bien."""

        messages.append({"role": "user", "content": prompt})

        # Appel à l'API avec Structured Output
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            response_format=prompts["response_format"]
        )
        
        result = response.choices[0].message.content
        result_dict = json.loads(result)
        
        # Si c'est une mise à jour et qu'il n'y a pas d'erreur, utiliser les nouvelles données
        if "property" in result_dict and not result_dict.get("error"):
            property_data = result_dict["property"]
        else:
            # Essayer d'utiliser directement le résultat comme données de propriété
            property_data = result_dict
            
        # S'assurer que les objets imbriqués sont présents
        if "bien" not in property_data:
            return False, "La réponse doit contenir au moins les informations de base du bien (surface)"
        if "prix" not in property_data:
            return False, "La réponse doit contenir au moins les informations de prix"
        
        # Si charges n'est pas présent, l'ajouter avec des valeurs par défaut
        if "charges" not in property_data:
            property_data["charges"] = {
                "mensuelles": None,
                "taxe_fonciere": None,
                "energie": None,
                "chauffage": None
            }
            
        # Retourner les données structurées
        return True, json.dumps(property_data)
    except Exception as e:
        return False, f"Erreur lors de l'appel à l'API : {str(e)}"

def update_properties_json(new_property_data: dict, selected_id: str = None):
    """Met à jour le fichier properties.json avec les nouvelles données."""
    try:
        # Charger le fichier properties.json existant
        with open('data/properties.json', 'r') as f:
            data = json.load(f)
        
        # S'assurer que le DPE a une valeur valide
        if 'bien' in new_property_data:
            new_property_data['bien']['dpe'] = new_property_data['bien'].get('dpe') or "NC"
            # Supprimer le champ pieces s'il existe
            if 'pieces' in new_property_data['bien']:
                del new_property_data['bien']['pieces']
        
        if selected_id and selected_id != "nouveau bien":
            # Mise à jour d'un bien existant
            data['properties'][selected_id] = new_property_data
        else:
            # Nouveau bien : générer un nouvel ID
            properties = Property.load_properties('data/properties.json')
            existing_ids = list(properties.keys())
            
            # Créer un Property temporaire pour utiliser generate_id
            temp_property = Property(
                id="temp",
                adresse=new_property_data.get('adresse', 'Adresse inconnue'),
                bien={
                    "surface": new_property_data['bien']['surface'],
                    "etage": new_property_data['bien'].get('etage'),
                    "nb_pieces": new_property_data['bien'].get('nb_pieces'),
                    "exposition": new_property_data['bien'].get('exposition'),
                    "type_chauffage": new_property_data['bien'].get('type_chauffage'),
                    "travaux": new_property_data['bien'].get('travaux'),
                    "etat": new_property_data['bien'].get('etat'),
                    "dpe": new_property_data['bien'].get('dpe', 'NC'),
                    "ges": new_property_data['bien'].get('ges'),
                    "cave": new_property_data['bien'].get('cave', False)
                },
                prix={
                    "annonce": new_property_data['prix']['annonce'],
                    "hors_honoraires": new_property_data['prix'].get('hors_honoraires'),
                    "frais_agence_acquereur": new_property_data['prix'].get('frais_agence_acquereur', False)
                },
                charges={
                    "mensuelles": new_property_data['charges'].get('mensuelles'),
                    "taxe_fonciere": new_property_data['charges'].get('taxe_fonciere'),
                    "energie": new_property_data['charges'].get('energie'),
                    "chauffage": new_property_data['charges'].get('chauffage')
                },
                metros=[],
                atouts=[],
                vigilance=[],
                lien_annonce=new_property_data.get('lien_annonce')
            )
            
            new_id = Property.generate_id(new_property_data['adresse'], existing_ids)
            data['properties'][new_id] = new_property_data
        
        # Sauvegarder les modifications
        with open('data/properties.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return True, None
    except Exception as e:
        return False, str(e)

def property_to_dict(property_obj):
    """Convertit un objet Property en dictionnaire compatible JSON."""
    if not property_obj:
        return None
        
    return {
        "id": property_obj.id,
        "adresse": property_obj.adresse,
        "bien": {
            "surface": property_obj.bien.surface,
            "etage": property_obj.bien.etage,
            "nb_pieces": property_obj.bien.nb_pieces,
            "exposition": property_obj.bien.exposition,
            "dpe": property_obj.bien.dpe,
            "ges": property_obj.bien.ges,
            "cave": property_obj.bien.cave,
            "etat": property_obj.bien.etat,
            "type_chauffage": property_obj.bien.type_chauffage,
            "travaux": property_obj.bien.travaux
        },
        "prix": {
            "annonce": property_obj.prix.annonce,
            "hors_honoraires": property_obj.prix.hors_honoraires,
            "m2": property_obj.prix.m2,
            "frais_agence_acquereur": property_obj.prix.frais_agence_acquereur
        },
        "charges": {
            "mensuelles": property_obj.charges.mensuelles,
            "taxe_fonciere": property_obj.charges.taxe_fonciere,
            "energie": property_obj.charges.energie,
            "chauffage": property_obj.charges.chauffage
        },
        "metros": [{"ligne": m.ligne, "station": m.station, "distance": m.distance} for m in property_obj.metros],
        "atouts": property_obj.atouts,
        "vigilance": property_obj.vigilance,
        "lien_annonce": str(property_obj.lien_annonce) if property_obj.lien_annonce else None
    }

def delete_property(property_id: str):
    """Supprime un bien du fichier properties.json."""
    try:
        with open('data/properties.json', 'r') as f:
            data = json.load(f)
        
        if property_id in data['properties']:
            del data['properties'][property_id]
            
            with open('data/properties.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True, None
        else:
            return False, "Bien non trouvé"
    except Exception as e:
        return False, str(e)

def property_details(properties):
    """Interface pour la gestion des biens."""
    st.header("Gestion des Biens", divider="red")
    
    # Style CSS pour l'icône de suppression
    st.markdown("""
        <style>
        .st-emotion-cache-1lkozj7 {
            margin-top: 27px;
        }
        div[data-testid="column"]:nth-child(2) button {
            color: #ff4b4b;
            cursor: pointer;
            font-size: 1.2rem;
            padding: 0.5rem;
            border-radius: 0.3rem;
        }
        div[data-testid="column"]:nth-child(2) button:hover {
            background-color: rgba(255, 75, 75, 0.1);
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Création de colonnes pour le selectbox et l'icône de suppression
    col_select, col_delete = st.columns([0.9, 0.1])
    
    with col_select:
        # Sélection du bien
        if 'last_added_property' not in st.session_state:
            st.session_state.last_added_property = "nouveau bien"
            
        # Création de la liste des options
        options = ["nouveau bien"] + list(properties.keys())
        
        # Calcul de l'index
        if st.session_state.last_added_property in properties:
            # Si le bien existe, on calcule son index dans la liste complète
            index = 1 + list(properties.keys()).index(st.session_state.last_added_property)
        else:
            # Sinon, on sélectionne "nouveau bien"
            index = 0
            
        selected = st.selectbox(
            "Sélectionner un bien",
            options,
            format_func=lambda x: x if x == "nouveau bien" else f"{x} - {properties[x].adresse}",
            key="property_selector",
            index=index
        )

        # Réinitialiser le champ de texte si la sélection change
        if "last_selection" not in st.session_state:
            st.session_state.last_selection = selected
        if "description_text" not in st.session_state:
            st.session_state.description_text = ""
            
        if st.session_state.last_selection != selected:
            st.session_state.description_text = ""
            st.session_state.last_selection = selected

    with col_delete:
        if selected != "nouveau bien":
            if st.button("🗑️", key=f"delete_button_{selected}", help="Supprimer ce bien"):
                # Création d'une clé unique pour le modal de confirmation
                modal_key = f"delete_confirm_{selected}"
                if modal_key not in st.session_state:
                    st.session_state[modal_key] = False
                
                st.session_state[modal_key] = True
    
    # Affichage du modal de confirmation en dehors des colonnes
    modal_key = f"delete_confirm_{selected}"
    if modal_key in st.session_state and st.session_state[modal_key]:
        st.markdown('<div style="display: flex; align-items: center; gap: 0.5rem; margin-top: 1rem;"><span style="color: #ffd700; font-size: 1.5rem;">⚠️</span><span style="font-size: 1.2rem;">Confirmation de suppression</span></div>', unsafe_allow_html=True)
        st.markdown(f"Êtes-vous sûr de vouloir supprimer le bien **{selected}** ?")
        
        # Affichage des boutons côte à côte sans colonnes
        c1, c2, c3, c4, c5 = st.columns([0.4, 0.1, 0.1, 0.1, 0.3])
        with c2:
            if st.button("Oui", type="primary", key=f"confirm_yes_{selected}"):
                success, error = delete_property(selected)
                if success:
                    st.success("Bien supprimé avec succès!")
                    st.session_state[modal_key] = False
                    st.session_state.last_added_property = "nouveau bien"
                    st.rerun()
                else:
                    st.error(f"Erreur lors de la suppression : {error}")
        
        with c3:
            if st.button("Non", key=f"confirm_no_{selected}"):
                st.session_state[modal_key] = False
                st.rerun()
    
    # Section Renseignements
    st.subheader("Renseignements", divider="red")
    if selected == "nouveau bien":
        st.markdown('<p style="color: gray;">Décrivez le nouveau bien en texte libre.</p>', unsafe_allow_html=True)
    else:
        st.markdown('<p style="color: gray;">Décrivez les modifications à apporter au bien.</p>', unsafe_allow_html=True)
    
    user_input = st.text_area("Description", value=st.session_state.description_text, height=200, key="description_input")
    # Mettre à jour le texte dans le state
    st.session_state.description_text = user_input
    
    if st.button("Enregistrer"):
        if user_input.strip():
            with st.spinner("Traitement en cours..."):
                existing_property = properties.get(selected) if selected != "nouveau bien" else None
                # Convertir l'objet Property en dictionnaire JSON-compatible
                existing_property_dict = property_to_dict(existing_property) if existing_property else None
                success, result = call_openai_api(user_input, existing_property_dict)
                
                if not success:
                    st.error(result)
                else:
                    try:
                        result_dict = json.loads(result)
                        
                        # Vérification de la structure de la réponse
                        if "error" in result_dict and result_dict["error"]:
                            display_error_message(result_dict["error"])
                        elif "property" not in result_dict:
                            # Essayer de traiter directement le résultat comme une propriété
                            try:
                                property_data = result_dict
                                success, error = update_properties_json(property_data, selected)
                                if success:
                                    st.success("Informations enregistrées avec succès!")
                                    if selected == "nouveau bien":
                                        new_properties = Property.load_properties('data/properties.json')
                                        last_id = max(new_properties.keys())
                                        st.session_state.last_added_property = last_id
                                    else:
                                        st.session_state.last_added_property = selected
                                    st.rerun()
                                else:
                                    display_error_message(f"Erreur lors de la sauvegarde : {error}")
                            except Exception as e:
                                display_error_message("La réponse de l'API n'a pas le bon format. Assurez-vous d'inclure au moins le prix et la surface du bien.")
                        else:
                            # Traitement normal si la propriété est dans result_dict["property"]
                            success, error = update_properties_json(result_dict["property"], selected)
                            if success:
                                st.success("Informations enregistrées avec succès!")
                                if selected == "nouveau bien":
                                    new_properties = Property.load_properties('data/properties.json')
                                    last_id = max(new_properties.keys())
                                    st.session_state.last_added_property = last_id
                                else:
                                    st.session_state.last_added_property = selected
                                st.rerun()
                            else:
                                display_error_message(f"Erreur lors de la sauvegarde : {error}")
                    except json.JSONDecodeError as e:
                        display_error_message(f"Erreur : Réponse invalide de l'API\nDétails : {str(e)}\nRéponse reçue : {result}")
                    except Exception as e:
                        display_error_message(str(e))
        else:
            st.warning("Veuillez entrer une description.")
    
    # Section Détails du bien
    if selected != "nouveau bien":
        property_data = properties[selected]
        st.subheader("Détails du bien", divider="red")
        display_property_details(property_data)

def display_property_details(property_data):
    """Affiche les détails d'un bien avec le style approprié."""
    # Style CSS pour le layout
    st.markdown("""
        <style>
        .property-detail {
            line-height: 1.5;
        }
        .property-label {
            color: gray;
            display: inline-block;
            margin-right: 0.5rem;
        }
        .property-value {
            display: inline-block;
        }
        .property-section {
            margin-top: 1.5rem;
        }
        .section-title {
            color: gray;
            margin-bottom: 0.5rem;
        }
        </style>
    """, unsafe_allow_html=True)

    # Création de deux colonnes
    col1, col2 = st.columns(2)

    with col1:
        # Informations générales
        has_general_info = False
        general_info = []

        # ID est toujours présent
        general_info.append(f'<div class="property-detail"><span class="property-label">ID:</span><span class="property-value">{property_data.id}</span></div>')
        
        if property_data.adresse:
            has_general_info = True
            general_info.append(f'<div class="property-detail"><span class="property-label">Adresse:</span><span class="property-value">{property_data.adresse}</span></div>')
        
        if property_data.bien.surface:
            has_general_info = True
            general_info.append(f'<div class="property-detail"><span class="property-label">Surface:</span><span class="property-value">{property_data.bien.surface} m²</span></div>')
        
        if property_data.bien.etage:
            has_general_info = True
            general_info.append(f'<div class="property-detail"><span class="property-label">Étage:</span><span class="property-value">{property_data.bien.etage}</span></div>')
        
        if property_data.bien.nb_pieces and property_data.bien.nb_pieces > 0:
            has_general_info = True
            general_info.append(f'<div class="property-detail"><span class="property-label">Nombre de pièces:</span><span class="property-value">{property_data.bien.nb_pieces}</span></div>')
        
        if property_data.bien.exposition:
            has_general_info = True
            general_info.append(f'<div class="property-detail"><span class="property-label">Orientation:</span><span class="property-value">{property_data.bien.exposition}</span></div>')
        
        if getattr(property_data.bien, 'cave', None) is not None:
            has_general_info = True
            general_info.append(f'<div class="property-detail"><span class="property-label">Cave:</span><span class="property-value">{"Oui" if property_data.bien.cave else "Non"}</span></div>')

        if has_general_info:
            st.markdown('<div class="property-section"><div class="section-title">Informations générales</div>', unsafe_allow_html=True)
            for info in general_info:
                st.markdown(info, unsafe_allow_html=True)

        # Prix et honoraires
        has_price_info = False
        price_info = []

        if property_data.prix:
            has_price_info = True
            price_info.append(f'<div class="property-detail"><span class="property-label">Prix:</span><span class="property-value">{property_data.prix.annonce:,.0f}€</span></div>')
        
        if property_data.prix.hors_honoraires:
            has_price_info = True
            price_info.append(f'<div class="property-detail"><span class="property-label">Prix hors honoraires:</span><span class="property-value">{property_data.prix.hors_honoraires:,.0f}€</span></div>')
        
        if property_data.prix.m2:
            has_price_info = True
            price_info.append(f'<div class="property-detail"><span class="property-label">Prix/m²:</span><span class="property-value">{property_data.prix.m2:,.0f}€</span></div>')

        if property_data.prix and property_data.prix.hors_honoraires:
            honoraires = property_data.prix.annonce - property_data.prix.hors_honoraires
            pourcentage = (honoraires / property_data.prix.annonce) * 100
            if honoraires > 0:
                has_price_info = True
                price_info.append(f'<div class="property-detail"><span class="property-label">Honoraires:</span><span class="property-value">{honoraires:,.0f}€ ({pourcentage:.1f}%)</span></div>')

        if has_price_info:
            st.markdown('<div class="property-section"><div class="section-title">Prix et honoraires</div>', unsafe_allow_html=True)
            for info in price_info:
                st.markdown(info, unsafe_allow_html=True)

        # Charges et énergie
        has_charges_info = False
        charges_info = []

        if property_data.charges.mensuelles:
            has_charges_info = True
            charges_info.append(f'<div class="property-detail"><span class="property-label">Charges mensuelles:</span><span class="property-value">{property_data.charges.mensuelles:,.0f}€</span></div>')
        
        if property_data.charges.energie:
            has_charges_info = True
            charges_info.append(f'<div class="property-detail"><span class="property-label">Électricité:</span><span class="property-value">{property_data.charges.energie:,.0f}€</span></div>')
        
        if property_data.charges.taxe_fonciere:
            has_charges_info = True
            charges_info.append(f'<div class="property-detail"><span class="property-label">Taxe foncière:</span><span class="property-value">{property_data.charges.taxe_fonciere:,.0f}€</span></div>')
        
        if property_data.bien.type_chauffage:
            has_charges_info = True
            charges_info.append(f'<div class="property-detail"><span class="property-label">Type de chauffage:</span><span class="property-value">{property_data.bien.type_chauffage}</span></div>')

        if has_charges_info:
            st.markdown('<div class="property-section"><div class="section-title">Charges et énergie</div>', unsafe_allow_html=True)
            for info in charges_info:
                st.markdown(info, unsafe_allow_html=True)

        # Performance énergétique
        has_energy_info = False
        energy_info = []

        if property_data.bien.dpe:
            has_energy_info = True
            dpe_colors = {
                'A': '#51b849',  # Vert
                'B': '#6fb24b',
                'C': '#b5b949',
                'D': '#ffd500',  # Jaune
                'E': '#ffaa00',  # Orange
                'F': '#ff5a00',
                'G': '#ff0000',  # Rouge
                'NC': '#808080'  # Gris
            }
            dpe_color = dpe_colors.get(property_data.bien.dpe, '#808080')
            energy_info.append(f'<div class="property-detail"><span class="property-label">DPE:</span><span class="property-value" style="background-color: {dpe_color}; color: white; padding: 2px 8px; border-radius: 4px;">{property_data.bien.dpe}</span></div>')
        
        if property_data.bien.ges:
            has_energy_info = True
            ges_colors = {
                'A': '#51b849',
                'B': '#6fb24b',
                'C': '#b5b949',
                'D': '#ffd500',
                'E': '#ffaa00',
                'F': '#ff5a00',
                'G': '#ff0000'
            }
            ges_color = ges_colors.get(property_data.bien.ges, '#808080')
            energy_info.append(f'<div class="property-detail"><span class="property-label">GES:</span><span class="property-value" style="background-color: {ges_color}; color: white; padding: 2px 8px; border-radius: 4px;">{property_data.bien.ges}</span></div>')

        if has_energy_info:
            st.markdown('<div class="property-section"><div class="section-title">Performance énergétique</div>', unsafe_allow_html=True)
            for info in energy_info:
                st.markdown(info, unsafe_allow_html=True)

        # Transports
        if property_data.metros:
            st.markdown('<div class="property-section"><div class="section-title">Transports</div>', unsafe_allow_html=True)
            for metro in property_data.metros:
                if metro.ligne:
                    if metro.distance:
                        st.markdown(f'<div class="property-detail">• Ligne {metro.ligne} station {metro.station} à {metro.distance}m</div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div class="property-detail">• Ligne {metro.ligne} station {metro.station}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="property-detail">• Station {metro.station}</div>', unsafe_allow_html=True)

    with col2:
        # Lien de l'annonce
        if property_data.lien_annonce:
            st.markdown('<div class="property-detail"><a href="{}" target="_blank">Voir l\'annonce</a></div>'.format(property_data.lien_annonce), unsafe_allow_html=True)
            
        # Points forts
        if property_data.atouts:
            st.markdown('<div class="property-section"><div class="section-title">Points forts</div>', unsafe_allow_html=True)
            for atout in property_data.atouts:
                st.markdown(f'<div class="property-detail">• {atout}</div>', unsafe_allow_html=True)
        
        # Points de vigilance
        if property_data.vigilance:
            st.markdown('<div class="property-section"><div class="section-title">Points de vigilance</div>', unsafe_allow_html=True)
            for point in property_data.vigilance:
                st.markdown(f'<div class="property-detail">• {point}</div>', unsafe_allow_html=True)

def format_validation_error(error_msg: str) -> str:
    """Formate le message d'erreur de validation pour un affichage plus clair."""
    # Retire les détails techniques de l'erreur Pydantic
    if "validation error for Property" in error_msg:
        error_msg = error_msg.split("validation error for Property")[-1]
    
    # Nettoie et formate le message
    error_msg = error_msg.replace("value_error.missing", "champ requis")
    error_msg = error_msg.strip()
    
    return error_msg

def display_error_message(error: str):
    """Affiche un message d'erreur formaté avec un style approprié."""
    st.markdown("""
        <style>
        .error-box {
            background-color: #ffebee;
            border-left: 5px solid #ff4b4b;
            padding: 1rem;
            margin: 1rem 0;
            border-radius: 4px;
        }
        .error-title {
            color: #ff4b4b;
            font-weight: bold;
            margin-bottom: 0.5rem;
        }
        .error-message {
            color: #333;
        }
        </style>
    """, unsafe_allow_html=True)
    
    st.markdown(f"""
        <div class="error-box">
            <div class="error-title">Erreur de validation</div>
            <div class="error-message">{format_validation_error(error)}</div>
        </div>
    """, unsafe_allow_html=True)

def main():
    st.title("Immo-Nico | Analyse immobilière")
    
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