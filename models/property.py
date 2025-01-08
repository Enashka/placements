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
    adresse: str
    surface: float
    etage: str
    nb_pieces: Optional[int] = None
    exposition: Optional[str] = None
    type_chauffage: Optional[str] = None
    travaux: Optional[str] = None
    etat: Optional[str] = None
    prix: float
    prix_hors_honoraires: float
    prix_m2: float
    charges_mensuelles: float
    taxe_fonciere: Optional[float] = None
    energie: Optional[float] = None
    dpe: str
    ges: Optional[str] = None
    metros: List[Metro] = []
    atouts: List[str] = []
    vigilance: List[str] = []
    frais_agence_acquereur: bool
    lien_annonce: Optional[str] = None

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
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            if not isinstance(data, dict) or 'properties' not in data:
                raise ValueError("Format JSON invalide: 'properties' manquant")
            
            properties = {}
            for prop_id, prop_data in data['properties'].items():
                try:
                    # Vérification des clés requises
                    if 'bien' not in prop_data:
                        print(f"Erreur: 'bien' manquant pour {prop_id}")
                        continue
                    if 'prix' not in prop_data:
                        print(f"Erreur: 'prix' manquant pour {prop_id}")
                        continue
                    if 'charges' not in prop_data:
                        print(f"Erreur: 'charges' manquant pour {prop_id}")
                        continue

                    bien = prop_data['bien']
                    prix = prop_data['prix']
                    charges = prop_data['charges']

                    # Construction du dictionnaire avec vérifications
                    property_dict = {
                        'id': prop_id,
                        'adresse': prop_data.get('adresse', ''),
                        'surface': float(bien.get('surface', 0)),
                        'etage': str(bien.get('etage', '0')),
                        'prix': float(prix.get('annonce', 0)),
                        'prix_hors_honoraires': float(prix.get('hors_honoraires', 0)),
                        'prix_m2': float(prix.get('m2', 0)),
                        'charges_mensuelles': float(charges.get('mensuelles', 0)),
                        'dpe': bien.get('dpe', 'NC'),
                        'frais_agence_acquereur': bool(prix.get('frais_agence_acquereur', False)),
                        # Champs optionnels
                        'nb_pieces': None,
                        'exposition': bien.get('orientation'),
                        'type_chauffage': charges.get('chauffage'),
                        'travaux': None,
                        'etat': None,
                        'taxe_fonciere': float(charges.get('taxe_fonciere', 0)) if charges.get('taxe_fonciere') is not None else None,
                        'energie': float(charges.get('energie', 0)) if charges.get('energie') is not None else None,
                        'ges': bien.get('ges'),
                        'metros': [Metro(**m) for m in prop_data.get('metros', [])],
                        'atouts': prop_data.get('atouts', []),
                        'vigilance': prop_data.get('vigilance', []),
                        'lien_annonce': None
                    }

                    # Debug: afficher les valeurs extraites
                    print(f"\nDébug {prop_id}:")
                    print(f"surface: {property_dict['surface']}")
                    print(f"etage: {property_dict['etage']}")
                    print(f"prix: {property_dict['prix']}")
                    print(f"prix_hors_honoraires: {property_dict['prix_hors_honoraires']}")
                    print(f"prix_m2: {property_dict['prix_m2']}")
                    print(f"charges_mensuelles: {property_dict['charges_mensuelles']}")
                    print(f"dpe: {property_dict['dpe']}")
                    print(f"frais_agence_acquereur: {property_dict['frais_agence_acquereur']}")
                    
                    properties[prop_id] = Property(**property_dict)
                    print(f"Bien {prop_id} chargé avec succès")
                
                except Exception as e:
                    print(f"Erreur lors du chargement du bien {prop_id}: {str(e)}")
                    continue
            
            return properties
            
        except Exception as e:
            print(f"Erreur lors du chargement du fichier JSON: {str(e)}")
            raise 