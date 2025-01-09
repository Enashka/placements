from pydantic import BaseModel, Field, validator, HttpUrl
from typing import List, Dict, Optional
import json
import re
from urllib.parse import urlparse, urlunparse, parse_qs

class Metro(BaseModel):
    ligne: Optional[str] = "NC"
    station: Optional[str] = "NC"
    distance: Optional[int] = None

    def __str__(self):
        if not self.ligne:
            return f"Station {self.station}"
        elif self.distance:
            return f"Ligne {self.ligne} station {self.station} à {self.distance}m"
        else:
            return f"Ligne {self.ligne} station {self.station}"

class Property(BaseModel):
    id: str
    adresse: Optional[str] = "Adresse inconnue"
    surface: Optional[float] = Field(None, ge=9, le=1000)  # Minimum 9m², maximum 1000m²
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
    lien_annonce: Optional[HttpUrl] = None

    @validator('lien_annonce')
    def clean_url(cls, v):
        """Nettoie l'URL en retirant les paramètres de tracking."""
        if not v:
            return None
            
        # Parse l'URL
        parsed = urlparse(str(v))
        
        # Liste des paramètres à conserver (vide pour l'instant, à compléter si besoin)
        params_to_keep = []
        
        # Parse et filtre les paramètres de query
        query_params = parse_qs(parsed.query)
        filtered_params = {k: v for k, v in query_params.items() if k in params_to_keep}
        
        # Reconstruit l'URL sans les paramètres de tracking
        clean_url = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            '&'.join(f"{k}={v[0]}" for k, v in filtered_params.items()) if filtered_params else '',
            ''  # Retire le fragment
        ))
        
        return clean_url

    @validator('adresse')
    def normalize_adresse(cls, v):
        """Normalise l'adresse en appliquant des règles cohérentes."""
        if not v or v == "NC" or v == "Adresse inconnue":
            return "Adresse inconnue"
        
        # Suppression des espaces multiples
        v = ' '.join(v.split())
        
        # Capitalisation de la première lettre de chaque mot significatif
        # Mais on préserve les articles et prépositions en minuscules
        small_words = ['de', 'du', 'des', 'le', 'la', 'les', 'sur', 'en', 'à']
        words = v.split(' ')
        normalized = []
        
        for i, word in enumerate(words):
            if i == 0 or word.lower() not in small_words:
                normalized.append(word.capitalize())
            else:
                normalized.append(word.lower())
        
        return ' '.join(normalized)

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
        
        return f"{base_id}-{next_num:03d}"

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
                'nb_pieces': prop_data['bien'].get('nb_pieces'),
                'prix': prop_data['prix']['annonce'],
                'prix_hors_honoraires': prop_data['prix']['hors_honoraires'],
                'prix_m2': prop_data['prix']['m2'],
                'charges_mensuelles': prop_data['charges']['mensuelles'],
                'dpe': prop_data['bien'].get('dpe', "NC"),
                'frais_agence_acquereur': prop_data['prix'].get('frais_agence_acquereur', False),
                # Champs optionnels
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

    @validator('nb_pieces', pre=True)
    def extract_nb_pieces(cls, v, values):
        """Extrait le nombre de pièces, y compris depuis le type de bien si nécessaire."""
        if v is not None:
            return v
            
        # Si on a un type de bien, on essaie d'en déduire le nombre de pièces
        type_bien = values.get('type_bien', '').upper()
        if type_bien:
            if type_bien == "STUDIO":
                return 1
            # Extraction du nombre depuis T1-T5
            match = re.search(r'[TF](\d+)', type_bien)
            if match:
                return int(match.group(1))
            # Pour T6+
            if type_bien == "T6+" or type_bien.startswith(("T6", "F6")):
                return 6
                
        return None 

    @validator('surface')
    def validate_surface(cls, v):
        """Valide et normalise la surface."""
        if v is None:
            return None
            
        # Arrondi à 0.1m² près
        v = round(v, 1)
        
        # Vérification des limites
        if v < 9:
            raise ValueError("La surface ne peut pas être inférieure à 9m² (loi Carrez)")
        if v > 1000:
            raise ValueError("La surface semble anormalement grande (>1000m²)")
            
        return v 