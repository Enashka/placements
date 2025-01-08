from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import json
import re

class Metro(BaseModel):
    ligne: str
    station: str
    distance: int = Field(description="Distance en mètres")

class Property(BaseModel):
    id: str
    adresse: Optional[str] = "NC"
    surface: Optional[float] = None
    etage: Optional[str] = "NC"
    nb_pieces: Optional[int] = None
    prix: Optional[float] = None
    prix_hors_honoraires: Optional[float] = None
    prix_m2: Optional[float] = None
    charges_mensuelles: Optional[float] = None
    dpe: str = "NC"
    
    # Champs optionnels qui ne seront affichés que si présents
    exposition: Optional[str] = None
    type_chauffage: Optional[str] = None
    travaux: Optional[str] = None
    etat: Optional[str] = None
    taxe_fonciere: Optional[float] = None
    energie: Optional[float] = None
    ges: Optional[str] = None
    metros: List[Metro] = []
    atouts: List[str] = []
    vigilance: List[str] = []
    frais_agence_acquereur: bool = False
    lien_annonce: Optional[str] = None

    @staticmethod
    def generate_id(adresse: str, existing_ids: List[str]) -> str:
        """Génère un ID unique basé sur l'adresse."""
        # Simplification : utiliser les premiers caractères de l'adresse
        base_id = "bien"
        
        # Recherche du dernier numéro pour cette base
        matching_ids = [id for id in existing_ids if id.startswith(base_id)]
        if not matching_ids:
            next_num = 1
        else:
            # Extraction des numéros existants
            nums = [int(id.split('-')[-1]) for id in matching_ids]
            next_num = max(nums) + 1
        
        # Création du nouvel ID
        return f"{base_id}-{next_num:03d}"

    def cout_mensuel(self, montant_pret: float, taux: float, duree_annees: int) -> float:
        """Calcule le coût mensuel total (crédit + charges)."""
        # Calcul de la mensualité du prêt
        taux_mensuel = taux / 12 / 100
        nombre_mois = duree_annees * 12
        mensualite = montant_pret * (taux_mensuel * (1 + taux_mensuel)**nombre_mois) / ((1 + taux_mensuel)**nombre_mois - 1)
        
        # Ajout des charges
        cout_total = mensualite + self.charges_mensuelles
        if self.energie:
            cout_total += self.energie
        if self.taxe_fonciere:
            cout_total += self.taxe_fonciere / 12
            
        return round(cout_total, 2)

    def rentabilite_locative(self, loyer_potentiel: float) -> float:
        """Calcule la rentabilité locative brute annuelle."""
        return round((loyer_potentiel * 12 / self.prix) * 100, 2)

    def score_transport(self) -> float:
        """Calcule un score d'accessibilité des transports (0-100)."""
        if not self.metros:
            return 0
        
        scores = []
        for metro in self.metros:
            # Score basé sur la distance (100 pour 0m, 0 pour 1000m ou plus)
            distance_score = max(0, 100 - (metro.distance / 10))
            scores.append(distance_score)
        
        return round(sum(scores) / len(scores), 2)

    @staticmethod
    def load_properties(json_file: str) -> Dict[str, 'Property']:
        """Charge tous les biens depuis un fichier JSON."""
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        properties = {}
        for prop_id, prop_data in data['properties'].items():
            # Conversion des distances en mètres
            metros = []
            for m in prop_data.get('metros', []):
                # Si la distance est inférieure à 1, on considère que c'est en kilomètres
                distance = m['distance']
                if isinstance(distance, (int, float)) and distance < 1:
                    distance = int(distance * 1000)  # Conversion en mètres
                metros.append({
                    'ligne': m['ligne'],
                    'station': m['station'],
                    'distance': distance
                })
            
            # Extraction des champs imbriqués
            property_dict = {
                'id': prop_id,
                'adresse': prop_data['adresse'],
                'surface': prop_data['bien']['surface'],
                'etage': prop_data['bien']['etage'],
                'prix': prop_data['prix']['annonce'],
                'prix_hors_honoraires': prop_data['prix']['hors_honoraires'],
                'prix_m2': prop_data['prix']['m2'],
                'charges_mensuelles': prop_data['charges']['mensuelles'],
                'dpe': prop_data['bien'].get('dpe', "NC"),
                'frais_agence_acquereur': prop_data['prix'].get('frais_agence_acquereur', False),
                # Champs optionnels
                'nb_pieces': None,  # À calculer si nécessaire
                'exposition': prop_data['bien'].get('orientation'),
                'type_chauffage': prop_data['charges'].get('chauffage'),
                'travaux': None,  # Non présent dans le JSON
                'etat': None,  # Non présent dans le JSON
                'taxe_fonciere': prop_data['charges'].get('taxe_fonciere'),
                'energie': prop_data['charges'].get('energie'),
                'ges': prop_data['bien'].get('ges'),
                'metros': [Metro(**m) for m in metros],
                'atouts': prop_data.get('atouts', []),
                'vigilance': prop_data.get('vigilance', []),
                'lien_annonce': prop_data.get('lien_annonce')
            }
            properties[prop_id] = Property(**property_dict)
        
        return properties 