from pydantic import BaseModel, Field, validator, HttpUrl
from typing import List, Dict, Optional, Any
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

class Bien(BaseModel):
    surface: float = Field(..., ge=9, le=1000)
    etage: Optional[str] = "NC"
    nb_pieces: Optional[int] = None
    exposition: Optional[str] = None
    dpe: Optional[str] = "NC"
    ges: Optional[str] = None
    cave: bool = False
    etat: Optional[str] = None
    travaux: Optional[str] = None
    type_chauffage: Optional[str] = None

class PrixHonoraires(BaseModel):
    montant: float
    pourcentage: float

class Prix(BaseModel):
    annonce: float
    hors_honoraires: Optional[float] = None
    honoraires: Optional[PrixHonoraires] = None
    frais_agence_acquereur: bool = False

    @property
    def m2(self) -> float:
        """Calcule le prix au m² à partir du prix et de la surface."""
        if hasattr(self, '_surface'):
            return round(self.annonce / self._surface, 2)
        return 0

    def set_surface(self, surface: float):
        """Définit la surface pour le calcul du prix au m²."""
        self._surface = surface

class Charges(BaseModel):
    mensuelles: Optional[float] = None
    taxe_fonciere: Optional[float] = None
    energie: Optional[float] = None
    chauffage: Optional[str] = None

class Quartier(BaseModel):
    prix_moyen: Optional[float] = None
    transactions: List[Any] = []
    commentaires: Optional[str] = None

class Property(BaseModel):
    id: str
    adresse: Optional[str] = "Adresse inconnue"
    bien: Bien
    prix: Prix
    charges: Charges = Field(default_factory=Charges)
    metros: List[Metro] = []
    atouts: List[str] = []
    vigilance: List[str] = []
    commentaires: List[str] = []
    quartier: Quartier = Field(default_factory=Quartier)
    lien_annonce: Optional[HttpUrl] = None
    error: Optional[str] = None

    def __init__(self, **data):
        if "charges" not in data:
            data["charges"] = Charges()
        super().__init__(**data)
        # Définit la surface pour le calcul du prix au m²
        self.prix.set_surface(self.bien.surface)

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

                # Construction du bien
                bien_dict = {
                    'surface': prop_data.get('bien', {}).get('surface'),
                    'etage': prop_data.get('bien', {}).get('etage'),
                    'nb_pieces': prop_data.get('bien', {}).get('nb_pieces'),
                    'exposition': prop_data.get('bien', {}).get('exposition'),
                    'dpe': prop_data.get('bien', {}).get('dpe', 'NC'),
                    'ges': prop_data.get('bien', {}).get('ges'),
                    'cave': prop_data.get('bien', {}).get('cave', False),
                    'etat': prop_data.get('bien', {}).get('etat'),
                    'travaux': prop_data.get('bien', {}).get('travaux'),
                    'type_chauffage': prop_data.get('bien', {}).get('type_chauffage')
                }

                # Construction du prix
                prix_dict = {
                    'annonce': prop_data.get('prix', {}).get('annonce'),
                    'hors_honoraires': prop_data.get('prix', {}).get('hors_honoraires'),
                    'frais_agence_acquereur': prop_data.get('prix', {}).get('frais_agence_acquereur', False)
                }

                # Construction des charges
                charges_dict = {
                    'mensuelles': prop_data.get('charges', {}).get('mensuelles', 0),
                    'taxe_fonciere': prop_data.get('charges', {}).get('taxe_fonciere'),
                    'energie': prop_data.get('charges', {}).get('energie'),
                    'chauffage': prop_data.get('charges', {}).get('chauffage')
                }

                # Construction du quartier
                quartier_dict = {
                    'prix_moyen': prop_data.get('quartier', {}).get('prix_moyen'),
                    'transactions': prop_data.get('quartier', {}).get('transactions', []) or [],
                    'commentaires': prop_data.get('quartier', {}).get('commentaires')
                }
                
                # Construction du dictionnaire de propriété
                property_dict = {
                    'id': prop_id,
                    'adresse': prop_data.get('adresse'),
                    'bien': bien_dict,
                    'prix': prix_dict,
                    'charges': charges_dict,
                    'quartier': quartier_dict,
                    'metros': [Metro(**m) for m in metros],
                    'atouts': prop_data.get('atouts', []),
                    'vigilance': prop_data.get('vigilance', []),
                    'commentaires': prop_data.get('commentaires', []),
                    'lien_annonce': prop_data.get('lien_annonce')
                }
                
                # Vérifie que les champs obligatoires sont présents
                if not prix_dict['annonce']:
                    print(f"⚠️ Bien {prop_id} ignoré : prix manquant")
                    continue
                if not bien_dict['surface']:
                    print(f"⚠️ Bien {prop_id} ignoré : surface manquante")
                    continue
                    
                properties[prop_id] = Property(**property_dict)
            except Exception as e:
                print(f"⚠️ Erreur lors du chargement du bien {prop_id} : {str(e)}")
                continue
        
        return properties

    @validator('bien')
    def validate_surface(cls, v):
        """Valide et normalise la surface."""
        if v.surface is None:
            raise ValueError("La surface est obligatoire. Veuillez renseigner la surface du bien.")
            
        # Arrondi à 0.1m² près
        v.surface = round(v.surface, 1)
        
        # Vérification des limites
        if v.surface < 9:
            raise ValueError("La surface ne peut pas être inférieure à 9m² (loi Carrez)")
        if v.surface > 1000:
            raise ValueError("La surface semble anormalement grande (>1000m²)")
            
        return v

    @validator('bien')
    def validate_dpe(cls, v):
        """Valide que le DPE est une valeur autorisée."""
        if not v.dpe:
            v.dpe = "NC"
        valid_dpe = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'NC']
        if v.dpe.upper() not in valid_dpe:
            raise ValueError(f"DPE invalide. Valeurs autorisées : {', '.join(valid_dpe)}")
        v.dpe = v.dpe.upper()
        return v

    @validator('bien')
    def validate_ges(cls, v):
        """Valide que le GES est une valeur autorisée."""
        if v.ges is None:
            return v
        valid_ges = ['A', 'B', 'C', 'D', 'E', 'F', 'G']
        if v.ges.upper() not in valid_ges:
            raise ValueError(f"GES invalide. Valeurs autorisées : {', '.join(valid_ges)}")
        v.ges = v.ges.upper()
        return v

    @validator('prix')
    def validate_prix(cls, v):
        """Valide que le prix est cohérent."""
        if v.annonce is None:
            raise ValueError("Le prix est obligatoire. Veuillez renseigner le prix du bien.")
        if v.annonce <= 0:
            raise ValueError("Le prix doit être supérieur à 0.")
        if v.annonce > 10000000:  # 10 millions d'euros
            raise ValueError("Le prix semble anormalement élevé (>10M€). Veuillez vérifier le montant.")
            
        # Validation du prix hors honoraires
        if v.hors_honoraires is not None:
            if v.hors_honoraires <= 0:
                raise ValueError("Le prix hors honoraires doit être supérieur à 0.")
            if v.hors_honoraires > v.annonce:
                raise ValueError("Le prix hors honoraires ne peut pas être supérieur au prix total.")
            
            # Calcul des honoraires
            honoraires = v.annonce - v.hors_honoraires
            if honoraires > 0:
                pourcentage = (honoraires / v.hors_honoraires) * 100
                if pourcentage > 20:
                    raise ValueError(f"Les honoraires semblent anormalement élevés ({pourcentage:.1f}% du prix hors honoraires).")
                
                # Mise à jour de l'objet honoraires
                v.honoraires = PrixHonoraires(
                    montant=honoraires,
                    pourcentage=pourcentage
                )
                
        return v 