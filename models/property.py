from dataclasses import dataclass
from typing import List, Dict, Optional
import json
import re

@dataclass
class Metro:
    ligne: str
    station: str
    distance: int  # en mètres

@dataclass
class Property:
    id: str
    adresse: str
    surface: float
    prix: float
    prix_hors_honoraires: float
    prix_m2: float
    charges_mensuelles: float
    taxe_fonciere: Optional[float]
    energie: Optional[float]
    dpe: str
    ges: Optional[str]
    metros: List[Metro]
    atouts: List[str]
    vigilance: List[str]
    frais_agence_acquereur: bool  # True si les frais sont à la charge de l'acquéreur

    @staticmethod
    def generate_id(adresse: str, existing_ids: List[str]) -> str:
        """Génère un ID unique basé sur l'adresse."""
        # Extraction du code postal
        cp_match = re.search(r'(?:75|93|94|92)\d{3}', adresse)
        if not cp_match:
            raise ValueError("L'adresse doit contenir un code postal valide (75XXX, 93XXX, 94XXX ou 92XXX)")
        
        cp = cp_match.group()
        
        # Détermination de la ville/arrondissement
        if cp.startswith('75'):
            ville = f"paris{cp[3:5]}"  # paris18, paris19, etc.
        else:
            # Extraction du nom de la ville avant le code postal
            ville_match = re.search(r'(?:[\w-]+)[,\s]+(?:75|93|94|92)\d{3}', adresse)
            if not ville_match:
                raise ValueError("Impossible d'extraire le nom de la ville de l'adresse")
            ville = ville_match.group().split(',')[0].strip().lower().replace(' ', '-')
        
        # Recherche du dernier numéro pour cette ville
        ville_ids = [id for id in existing_ids if id.startswith(ville)]
        if not ville_ids:
            next_num = 1
        else:
            # Extraction des numéros existants
            nums = [int(id.split('-')[-1]) for id in ville_ids]
            next_num = max(nums) + 1
        
        # Création du nouvel ID
        return f"{ville}-{next_num:03d}"

    @classmethod
    def from_json(cls, property_id: str, data: Dict) -> 'Property':
        """Crée une instance Property à partir des données JSON."""
        metros = [
            Metro(
                ligne=m['ligne'],
                station=m['station'],
                distance=m['distance']
            ) for m in data['metros']
        ]

        return cls(
            id=property_id,
            adresse=data['adresse'],
            surface=data['bien']['surface'],
            prix=data['prix']['annonce'],
            prix_hors_honoraires=data['prix']['hors_honoraires'],
            prix_m2=data['prix']['m2'],
            charges_mensuelles=data['charges']['mensuelles'],
            taxe_fonciere=data['charges'].get('taxe_fonciere'),
            energie=data['charges'].get('energie'),
            dpe=data['bien']['dpe'],
            ges=data['bien'].get('ges'),
            metros=metros,
            atouts=data['atouts'],
            vigilance=data.get('vigilance', []),
            frais_agence_acquereur=data['prix'].get('frais_agence_acquereur', True)  # Par défaut à True
        )

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
            properties[prop_id] = Property.from_json(prop_id, prop_data)
        
        return properties 