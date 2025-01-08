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
    
    # Vérification s'il y a des biens
    if not properties:
        st.warning("Aucun bien n'est enregistré. Veuillez d'abord ajouter un bien dans l'onglet 'Biens'.")
        return
    
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
            model="gpt-4o",
            messages=messages,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "property_schema",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "error": {
                                "type": "string",
                                "description": "Message d'erreur si les informations sont insuffisantes"
                            },
                            "property": {
                                "type": "object",
                                "properties": {
                                    "adresse": {"type": "string"},
                                    "lien_annonce": {"type": ["string", "null"]},
                                    "bien": {
                                        "type": "object",
                                        "properties": {
                                            "type": {"type": "string"},
                                            "surface": {"type": "number"},
                                            "etage": {"type": "string"},
                                            "nb_pieces": {"type": ["integer", "null"]},
                                            "orientation": {"type": ["string", "null"]},
                                            "pieces": {
                                                "type": "object",
                                                "properties": {
                                                    "sejour_cuisine": {"type": ["number", "null"]},
                                                    "chambre": {"type": ["number", "null"]}
                                                }
                                            },
                                            "dpe": {"type": ["string", "null"]},
                                            "ges": {"type": ["string", "null"]},
                                            "cave": {"type": "boolean"}
                                        }
                                    },
                                    "prix": {
                                        "type": "object",
                                        "properties": {
                                            "annonce": {"type": "number"},
                                            "hors_honoraires": {"type": "number"},
                                            "m2": {"type": "number"},
                                            "honoraires": {
                                                "type": "object",
                                                "properties": {
                                                    "montant": {"type": "number"},
                                                    "pourcentage": {"type": "number"}
                                                }
                                            },
                                            "negociable": {"type": ["boolean", "null"]},
                                            "frais_agence_acquereur": {"type": "boolean"}
                                        }
                                    },
                                    "charges": {
                                        "type": "object",
                                        "properties": {
                                            "mensuelles": {"type": "number"},
                                            "taxe_fonciere": {"type": ["number", "null"]},
                                            "energie": {"type": ["number", "null"]},
                                            "chauffage": {"type": ["string", "null"]}
                                        }
                                    },
                                    "metros": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "ligne": {"type": "string"},
                                                "station": {"type": "string"},
                                                "distance": {"type": "number"}
                                            }
                                        }
                                    },
                                    "atouts": {
                                        "type": "array",
                                        "items": {"type": "string"}
                                    },
                                    "vigilance": {
                                        "type": "array",
                                        "items": {"type": "string"}
                                    }
                                }
                            }
                        }
                    }
                }
            }
        )
        
        result = response.choices[0].message.content
        result_dict = json.loads(result)
        
        # Si c'est une mise à jour et qu'il n'y a pas d'erreur, utiliser les nouvelles données
        if existing_property and "property" in result_dict and not result_dict.get("error"):
            # Utiliser directement les nouvelles données, car l'API a déjà fait la fusion
            return True, json.dumps(result_dict)
        elif "property" in result_dict:
            # Nouveau bien ou mise à jour réussie
            return True, json.dumps(result_dict)
        else:
            # Erreur ou données manquantes
            return False, "La réponse de l'API ne contient pas les informations du bien"
            
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
                adresse=new_property_data['adresse'],
                surface=new_property_data['bien']['surface'],
                etage=new_property_data['bien']['etage'],
                nb_pieces=new_property_data['bien'].get('nb_pieces'),
                exposition=new_property_data['bien'].get('exposition'),
                type_chauffage=new_property_data['bien'].get('type_chauffage'),
                travaux=new_property_data['bien'].get('travaux'),
                etat=new_property_data['bien'].get('etat'),
                prix=new_property_data['prix']['annonce'],
                prix_hors_honoraires=new_property_data['prix']['hors_honoraires'],
                prix_m2=new_property_data['prix']['m2'],
                charges_mensuelles=new_property_data['charges']['mensuelles'],
                taxe_fonciere=new_property_data['charges'].get('taxe_fonciere'),
                energie=new_property_data['charges'].get('energie'),
                dpe=new_property_data['bien']['dpe'],  # Déjà validé plus haut
                ges=new_property_data['bien'].get('ges'),
                metros=[],
                atouts=[],
                vigilance=[],
                frais_agence_acquereur=new_property_data['prix']['frais_agence_acquereur'],
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
        "adresse": property_obj.adresse,
        "lien_annonce": property_obj.lien_annonce,
        "bien": {
            "type": getattr(property_obj, 'type', "T2"),
            "surface": property_obj.surface,
            "etage": property_obj.etage,
            "nb_pieces": getattr(property_obj, 'nb_pieces', None),
            "orientation": getattr(property_obj, 'exposition', None),
            "pieces": {
                "sejour_cuisine": None,
                "chambre": None
            },
            "dpe": property_obj.dpe,
            "ges": getattr(property_obj, 'ges', None),
            "cave": getattr(property_obj, 'cave', False)
        },
        "prix": {
            "annonce": property_obj.prix,
            "hors_honoraires": property_obj.prix_hors_honoraires,
            "m2": property_obj.prix_m2,
            "honoraires": {
                "montant": property_obj.prix - property_obj.prix_hors_honoraires if property_obj.prix and property_obj.prix_hors_honoraires else None,
                "pourcentage": ((property_obj.prix - property_obj.prix_hors_honoraires) / property_obj.prix * 100) if property_obj.prix and property_obj.prix_hors_honoraires and property_obj.prix > 0 else None
            },
            "negociable": None,
            "frais_agence_acquereur": property_obj.frais_agence_acquereur
        },
        "charges": {
            "mensuelles": property_obj.charges_mensuelles,
            "taxe_fonciere": getattr(property_obj, 'taxe_fonciere', None),
            "energie": getattr(property_obj, 'energie', None),
            "chauffage": getattr(property_obj, 'type_chauffage', None)
        },
        "metros": [{"ligne": m.ligne, "station": m.station, "distance": m.distance} for m in property_obj.metros],
        "atouts": property_obj.atouts,
        "vigilance": property_obj.vigilance
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
            format_func=lambda x: f"{x} - {properties[x].adresse}" if x in properties else x,
            key="property_selector",
            index=index
        )
    
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
    
    user_input = st.text_area("Description", height=200)
    
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
                        
                        if "error" in result_dict and result_dict["error"]:
                            st.error(f"Erreur retournée par l'API : {result_dict['error']}")
                        elif "property" not in result_dict:
                            st.error("La réponse de l'API ne contient pas les informations du bien")
                        else:
                            # Mettre à jour properties.json avec le résultat
                            success, error = update_properties_json(result_dict["property"], selected)
                            if success:
                                st.success("Informations enregistrées avec succès!")
                                # Stocker l'ID du nouveau bien
                                if selected == "nouveau bien":
                                    # Recharger les propriétés pour obtenir le nouvel ID
                                    new_properties = Property.load_properties('data/properties.json')
                                    # Trouver le dernier bien ajouté
                                    last_id = max(new_properties.keys())
                                    st.session_state.last_added_property = last_id
                                else:
                                    st.session_state.last_added_property = selected
                                # Recharger la page pour afficher les modifications
                                st.rerun()
                            else:
                                st.error(f"Erreur lors de la sauvegarde : {error}")
                    except json.JSONDecodeError as e:
                        st.error(f"Erreur : Réponse invalide de l'API\nDétails : {str(e)}\nRéponse reçue : {result}")
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
        # Champs principaux (toujours affichés)
        st.markdown('<div class="property-detail"><span class="property-label">ID:</span><span class="property-value">{}</span></div>'.format(property_data.id), unsafe_allow_html=True)
        st.markdown('<div class="property-detail"><span class="property-label">Adresse:</span><span class="property-value">{}</span></div>'.format(property_data.adresse or "Non communiqué"), unsafe_allow_html=True)
        st.markdown('<div class="property-detail"><span class="property-label">Surface:</span><span class="property-value">{}</span></div>'.format(f"{property_data.surface} m²" if property_data.surface else "Non communiqué"), unsafe_allow_html=True)
        st.markdown('<div class="property-detail"><span class="property-label">Étage:</span><span class="property-value">{}</span></div>'.format(property_data.etage or "Non communiqué"), unsafe_allow_html=True)
        st.markdown('<div class="property-detail"><span class="property-label">Nombre de pièces:</span><span class="property-value">{}</span></div>'.format(property_data.nb_pieces or "Non communiqué"), unsafe_allow_html=True)
        st.markdown('<div class="property-detail"><span class="property-label">Prix:</span><span class="property-value">{}</span></div>'.format(f"{property_data.prix:,.0f}€" if property_data.prix else "Non communiqué"), unsafe_allow_html=True)
        st.markdown('<div class="property-detail"><span class="property-label">Prix/m²:</span><span class="property-value">{}</span></div>'.format(f"{property_data.prix_m2:,.0f}€" if property_data.prix_m2 else "Non communiqué"), unsafe_allow_html=True)
        st.markdown('<div class="property-detail"><span class="property-label">DPE:</span><span class="property-value">{}</span></div>'.format(property_data.dpe or "Non communiqué"), unsafe_allow_html=True)

    with col2:
        # Points forts (affichés uniquement si présents)
        if property_data.atouts:
            st.markdown('<div class="property-detail"><span class="property-label">Points forts:</span></div>', unsafe_allow_html=True)
            for atout in property_data.atouts:
                st.markdown(f'<div class="property-detail">• {atout}</div>', unsafe_allow_html=True)
        
        # Points de vigilance (affichés uniquement si présents)
        if property_data.vigilance:
            st.markdown('<div class="property-section"><div class="section-title">Points de vigilance:</div>', unsafe_allow_html=True)
            for point in property_data.vigilance:
                st.markdown(f'<div class="property-detail">• {point}</div>', unsafe_allow_html=True)

        # Métros (affichés uniquement si présents)
        if property_data.metros:
            st.markdown('<div class="property-section"><div class="section-title">Transports:</div>', unsafe_allow_html=True)
            for metro in property_data.metros:
                st.markdown(f'<div class="property-detail">• Ligne {metro.ligne} station {metro.station} à {metro.distance}m</div>', unsafe_allow_html=True)

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