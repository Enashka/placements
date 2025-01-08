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

if not os.getenv("OPENAI_API_KEY"):
    raise ValueError("La clé API OpenAI n'est pas définie dans le fichier .env")

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

def load_prompts():
    """Charge les prompts depuis le fichier YAML."""
    with open("data/renseignement-prompt.yaml", "r") as f:
        return yaml.safe_load(f)

def call_openai_api(text: str, existing_property=None):
    """Appelle l'API OpenAI pour extraire les informations du bien."""
    try:
        # Initialisation du client avec la clé API chargée depuis .env
        client = OpenAI()  # La clé sera automatiquement chargée depuis la variable d'environnement
        prompts = load_prompts()

        # Prépare les messages pour l'API
        messages = [
            {"role": "system", "content": prompts["system"]}
        ]

        if existing_property:
            # Cas de mise à jour
            prompt = prompts["update_prompt"].format(
                existing_details=json.dumps(existing_property, ensure_ascii=False, indent=2),
                user_input=text
            )
        else:
            # Nouveau bien
            prompt = prompts["new_prompt"].format(user_input=text)

        messages.append({"role": "user", "content": prompt})

        # Appel à l'API avec Structured Output
        response = client.chat.completions.create(
            model="gpt-4o-mini",
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
                                    # Copie du schéma de notre properties.json
                                    "adresse": {"type": "string"},
                                    "bien": {
                                        "type": "object",
                                        "properties": {
                                            "type": {"type": "string"},
                                            "surface": {"type": "number"},
                                            "etage": {"type": "string"},
                                            "orientation": {"type": ["string", "null"]},
                                            "pieces": {
                                                "type": "object",
                                                "properties": {
                                                    "sejour_cuisine": {"type": ["number", "null"]},
                                                    "chambre": {"type": ["number", "null"]}
                                                },
                                                "required": ["sejour_cuisine", "chambre"],
                                                "additionalProperties": False
                                            },
                                            "dpe": {"type": ["string", "null"]},
                                            "ges": {"type": ["string", "null"]},
                                            "cave": {"type": "boolean"}
                                        },
                                        "required": ["type", "surface", "etage", "orientation", "pieces", "dpe", "ges", "cave"],
                                        "additionalProperties": False
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
                                                },
                                                "required": ["montant", "pourcentage"],
                                                "additionalProperties": False
                                            },
                                            "negociable": {"type": ["boolean", "null"]},
                                            "frais_agence_acquereur": {"type": "boolean"}
                                        },
                                        "required": ["annonce", "hors_honoraires", "m2", "honoraires", "negociable", "frais_agence_acquereur"],
                                        "additionalProperties": False
                                    },
                                    "metros": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "ligne": {"type": "string"},
                                                "station": {"type": "string"},
                                                "distance": {"type": "number"}
                                            },
                                            "required": ["ligne", "station", "distance"],
                                            "additionalProperties": False
                                        }
                                    },
                                    "charges": {
                                        "type": "object",
                                        "properties": {
                                            "mensuelles": {"type": "number"},
                                            "taxe_fonciere": {"type": ["number", "null"]},
                                            "energie": {"type": ["number", "null"]},
                                            "chauffage": {"type": ["string", "null"]}
                                        },
                                        "required": ["mensuelles", "taxe_fonciere", "energie", "chauffage"],
                                        "additionalProperties": False
                                    },
                                    "copro": {
                                        "type": "object",
                                        "properties": {
                                            "lots": {"type": ["number", "null"]}
                                        },
                                        "required": ["lots"],
                                        "additionalProperties": False
                                    },
                                    "atouts": {
                                        "type": "array",
                                        "items": {"type": "string"}
                                    },
                                    "vigilance": {
                                        "type": "array",
                                        "items": {"type": "string"}
                                    },
                                    "contact": {"type": "string"}
                                },
                                "required": ["adresse", "bien", "prix", "metros", "charges", "copro", "atouts", "vigilance", "contact"],
                                "additionalProperties": False
                            }
                        },
                        "required": ["error", "property"],
                        "additionalProperties": False
                    },
                    "strict": True
                }
            }
        )
        
        return True, response.choices[0].message.content
    except Exception as e:
        return False, f"Erreur lors de l'appel à l'API : {str(e)}"

def update_properties_json(new_property_data: dict, selected_id: str = None):
    """Met à jour le fichier properties.json avec les nouvelles données."""
    try:
        # Charger le fichier properties.json existant
        with open('data/properties.json', 'r') as f:
            data = json.load(f)
        
        if selected_id and selected_id != "nouveau bien":
            # Mise à jour d'un bien existant
            data['properties'][selected_id] = new_property_data
        else:
            # Nouveau bien : générer un nouvel ID
            # Charger tous les biens pour générer un ID unique
            properties = Property.load_properties('data/properties.json')
            existing_ids = list(properties.keys())
            
            # Extraire le code postal pour générer l'ID
            cp_match = re.search(r'(?:75|93|94|92)\d{3}', new_property_data['adresse'])
            if not cp_match:
                raise ValueError("L'adresse doit contenir un code postal valide (75XXX, 93XXX, 94XXX ou 92XXX)")
            
            # Créer un Property temporaire pour utiliser generate_id
            temp_property = Property(
                id="temp",
                adresse=new_property_data['adresse'],
                surface=new_property_data['bien']['surface'],
                prix=new_property_data['prix']['annonce'],
                prix_hors_honoraires=new_property_data['prix']['hors_honoraires'],
                prix_m2=new_property_data['prix']['m2'],
                charges_mensuelles=new_property_data['charges']['mensuelles'],
                taxe_fonciere=new_property_data['charges']['taxe_fonciere'],
                energie=new_property_data['charges']['energie'],
                dpe=new_property_data['bien']['dpe'],
                ges=new_property_data['bien']['ges'],
                metros=[],  # Ces détails ne sont pas nécessaires pour la génération de l'ID
                atouts=[],
                vigilance=[],
                frais_agence_acquereur=new_property_data['prix']['frais_agence_acquereur']
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
    return {
        "adresse": property_obj.adresse,
        "bien": {
            "type": property_obj.type if hasattr(property_obj, 'type') else "T2",  # valeur par défaut
            "surface": property_obj.surface,
            "etage": property_obj.etage if hasattr(property_obj, 'etage') else "0",
            "orientation": property_obj.orientation if hasattr(property_obj, 'orientation') else None,
            "pieces": {
                "sejour_cuisine": 0,  # valeurs par défaut
                "chambre": 0
            },
            "dpe": property_obj.dpe,
            "ges": property_obj.ges,
            "cave": hasattr(property_obj, 'cave') and property_obj.cave
        },
        "prix": {
            "annonce": property_obj.prix,
            "hors_honoraires": property_obj.prix_hors_honoraires,
            "m2": property_obj.prix_m2,
            "honoraires": {
                "montant": property_obj.prix - property_obj.prix_hors_honoraires,
                "pourcentage": ((property_obj.prix - property_obj.prix_hors_honoraires) / property_obj.prix * 100) if property_obj.prix > 0 else 0
            },
            "negociable": None,
            "frais_agence_acquereur": property_obj.frais_agence_acquereur
        },
        "metros": [{
            "ligne": m.ligne,
            "station": m.station,
            "distance": m.distance
        } for m in property_obj.metros],
        "charges": {
            "mensuelles": property_obj.charges_mensuelles,
            "taxe_fonciere": property_obj.taxe_fonciere,
            "energie": property_obj.energie,
            "chauffage": None
        },
        "copro": {
            "lots": 0  # valeur par défaut
        },
        "atouts": property_obj.atouts,
        "vigilance": property_obj.vigilance,
        "contact": "direct propriétaire"  # valeur par défaut
    }

def property_details(properties):
    """Interface pour la gestion des biens."""
    st.header("Gestion des Biens", divider="red")
    
    # Sélection du bien
    selected = st.selectbox(
        "Sélectionner un bien",
        ["nouveau bien"] + list(properties.keys()),
        format_func=lambda x: f"{x} - {properties[x].adresse}" if x in properties else x
    )
    
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
                        st.write("Réponse de l'API:", result_dict)  # Debug: afficher la réponse complète
                        
                        if "error" in result_dict and result_dict["error"]:
                            st.error(f"Erreur retournée par l'API : {result_dict['error']}")
                        elif "property" not in result_dict:
                            st.error("La réponse de l'API ne contient pas les informations du bien")
                        else:
                            # Mettre à jour properties.json avec le résultat
                            success, error = update_properties_json(result_dict["property"], selected)
                            if success:
                                st.success("Informations enregistrées avec succès!")
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
    # Informations générales
    st.markdown(f'<p style="color: gray;">ID:</p> {property_data.id}', unsafe_allow_html=True)
    st.markdown(f'<p style="color: gray;">Adresse:</p> {property_data.adresse}', unsafe_allow_html=True)
    st.markdown(f'<p style="color: gray;">Surface:</p> {property_data.surface} m²', unsafe_allow_html=True)
    
    # Prix et charges
    st.markdown(f'<p style="color: gray;">Prix:</p> {property_data.prix:,.0f}€', unsafe_allow_html=True)
    st.markdown(f'<p style="color: gray;">Prix/m²:</p> {property_data.prix_m2:,.0f}€', unsafe_allow_html=True)
    st.markdown(f'<p style="color: gray;">Charges mensuelles:</p> {property_data.charges_mensuelles:,.0f}€', unsafe_allow_html=True)
    
    # DPE et GES
    st.markdown(f'<p style="color: gray;">DPE:</p> {property_data.dpe if property_data.dpe else "Non spécifié"}', unsafe_allow_html=True)
    st.markdown(f'<p style="color: gray;">GES:</p> {property_data.ges if property_data.ges else "Non spécifié"}', unsafe_allow_html=True)
    
    # Métros
    st.markdown('<p style="color: gray;">Transports:</p>', unsafe_allow_html=True)
    if property_data.metros:
        for metro in property_data.metros:
            st.markdown(f'• Ligne {metro.ligne} station {metro.station} à {metro.distance}m', unsafe_allow_html=True)
    else:
        st.markdown('<p style="color: gray;">Aucun transport renseigné</p>', unsafe_allow_html=True)
    
    # Atouts
    st.markdown('<p style="color: gray;">Points forts:</p>', unsafe_allow_html=True)
    for atout in property_data.atouts:
        st.markdown(f'• {atout}', unsafe_allow_html=True)
    
    # Points de vigilance
    st.markdown('<p style="color: gray;">Points de vigilance:</p>', unsafe_allow_html=True)
    if property_data.vigilance:
        for point in property_data.vigilance:
            st.markdown(f'• {point}', unsafe_allow_html=True)
    else:
        st.markdown('<p style="color: gray;">Aucun point de vigilance signalé</p>', unsafe_allow_html=True)

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