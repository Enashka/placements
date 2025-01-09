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
    surface: float = Field(..., ge=9, le=1000)
    etage: Optional[str] = "NC"
    nb_pieces: Optional[int] = None
    exposition: Optional[str] = None
    prix: float
    prix_hors_honoraires: Optional[float] = None
    charges_mensuelles: Optional[float] = None
    taxe_fonciere: Optional[float] = None
    frais_agence_acquereur: bool = False
    energie: Optional[float] = None
    type_chauffage: Optional[str] = None
    dpe: str = "NC"
    ges: Optional[str] = None
    etat: Optional[str] = None
    travaux: Optional[str] = None
    metros: List[Metro] = []
    atouts: List[str] = []
    vigilance: List[str] = []
    lien_annonce: Optional[HttpUrl] = None
    error: Optional[str] = None
    cave: bool = False

    @property
    def prix_m2(self) -> float:
        """Calcule le prix au m² à partir du prix et de la surface."""
        return round(self.prix / self.surface, 2)

    @property
    def prix_hors_honoraires_effectif(self) -> float:
        """Retourne le prix hors honoraires effectif (égal au prix si non spécifié)."""
        return self.prix_hors_honoraires if self.prix_hors_honoraires is not None else self.prix

    @property
    def honoraires(self) -> float:
        """Calcule le montant des honoraires."""
        return round(self.prix - self.prix_hors_honoraires_effectif, 2)

    @property
    def pourcentage_honoraires(self) -> float:
        """Calcule le pourcentage des honoraires par rapport au prix hors honoraires."""
        if self.honoraires == 0:
            return 0
        return round((self.honoraires / self.prix_hors_honoraires_effectif) * 100, 2)

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

    @staticmethod
    def load_properties(json_file: str) -> Dict[str, 'Property']:
        """Charge tous les biens depuis un fichier JSON."""
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        properties = {}
        for prop_id, prop_data in data['properties'].items():
            try:
                # Conversion des distances en mètres pour les métros
                metros = []
                for m in prop_data.get('metros', []):
                    distance = m.get('distance')
                    if isinstance(distance, (int, float)) and distance < 1:
                        distance = int(distance * 1000)  # Conversion en mètres
                    metros.append({
                        'ligne': m.get('ligne'),
                        'station': m.get('station'),
                        'distance': distance
                    })
                
                # Construction du dictionnaire de propriété
                property_dict = {
                    'id': prop_id,
                    'adresse': prop_data.get('adresse'),
                    'surface': prop_data.get('surface'),
                    'etage': prop_data.get('etage'),
                    'nb_pieces': prop_data.get('nb_pieces'),
                    'exposition': prop_data.get('exposition'),
                    'prix': prop_data.get('prix'),
                    'prix_hors_honoraires': prop_data.get('prix_hors_honoraires'),
                    'charges_mensuelles': prop_data.get('charges_mensuelles'),
                    'taxe_fonciere': prop_data.get('taxe_fonciere'),
                    'frais_agence_acquereur': prop_data.get('frais_agence_acquereur', False),
                    'energie': prop_data.get('energie'),
                    'type_chauffage': prop_data.get('type_chauffage'),
                    'dpe': prop_data.get('dpe', 'NC'),
                    'ges': prop_data.get('ges'),
                    'etat': prop_data.get('etat'),
                    'travaux': prop_data.get('travaux'),
                    'metros': [Metro(**m) for m in metros],
                    'atouts': prop_data.get('atouts', []),
                    'vigilance': prop_data.get('vigilance', []),
                    'lien_annonce': prop_data.get('lien_annonce'),
                    'cave': prop_data.get('bien', {}).get('cave', False)
                }
                
                # Vérifie que les champs obligatoires sont présents
                if property_dict['prix'] is None:
                    print(f"⚠️ Bien {prop_id} ignoré : prix manquant")
                    continue
                if property_dict['surface'] is None:
                    print(f"⚠️ Bien {prop_id} ignoré : surface manquante")
                    continue
                    
                properties[prop_id] = Property(**property_dict)
            except Exception as e:
                print(f"⚠️ Erreur lors du chargement du bien {prop_id} : {str(e)}")
                continue
        
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
            raise ValueError("La surface est obligatoire. Veuillez renseigner la surface du bien.")
            
        # Arrondi à 0.1m² près
        v = round(v, 1)
        
        # Vérification des limites
        if v < 9:
            raise ValueError("La surface ne peut pas être inférieure à 9m² (loi Carrez)")
        if v > 1000:
            raise ValueError("La surface semble anormalement grande (>1000m²)")
            
        return v

    @validator('dpe')
    def validate_dpe(cls, v):
        """Valide que le DPE est une valeur autorisée."""
        if not v:
            return "NC"
        valid_dpe = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'NC']
        if v.upper() not in valid_dpe:
            raise ValueError(f"DPE invalide. Valeurs autorisées : {', '.join(valid_dpe)}")
        return v.upper()

    @validator('ges')
    def validate_ges(cls, v):
        """Valide que le GES est une valeur autorisée."""
        if v is None:
            return v
        valid_ges = ['A', 'B', 'C', 'D', 'E', 'F', 'G']
        if v.upper() not in valid_ges:
            raise ValueError(f"GES invalide. Valeurs autorisées : {', '.join(valid_ges)}")
        return v.upper()

    @validator('prix_hors_honoraires')
    def validate_prix_hors_honoraires(cls, v, values):
        """Valide que le prix hors honoraires est cohérent avec le prix total."""
        if v is None:
            return None
            
        # Vérifie que le prix total est disponible
        if 'prix' not in values:
            raise ValueError("Le prix total doit être défini avant le prix hors honoraires.")
            
        prix = values['prix']
        
        # Vérifie que le prix hors honoraires est positif
        if v <= 0:
            raise ValueError("Le prix hors honoraires doit être supérieur à 0.")
            
        # Vérifie que le prix hors honoraires n'est pas supérieur au prix total
        if v > prix:
            raise ValueError("Le prix hors honoraires ne peut pas être supérieur au prix total.")
            
        # Vérifie que les honoraires ne sont pas excessifs (>20% du prix hors honoraires)
        honoraires = prix - v
        if honoraires > 0:
            pourcentage = (honoraires / v) * 100
            if pourcentage > 20:
                raise ValueError(f"Les honoraires semblent anormalement élevés ({pourcentage:.1f}% du prix hors honoraires).")
                
        return v

    @validator('prix')
    def validate_prix(cls, v):
        """Valide que le prix est renseigné et cohérent."""
        if v is None:
            raise ValueError("Le prix est obligatoire. Veuillez renseigner le prix du bien.")
        if v <= 0:
            raise ValueError("Le prix doit être supérieur à 0.")
        if v > 10000000:  # 10 millions d'euros
            raise ValueError("Le prix semble anormalement élevé (>10M€). Veuillez vérifier le montant.")
        return v 