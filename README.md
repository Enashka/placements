# Analyse Immobilière

Outil d'analyse et de simulation pour l'investissement immobilier.

## Installation

1. Cloner le repository
2. Créer et activer l'environnement virtuel :
```bash
python -m venv .venv
source .venv/bin/activate  # Unix/MacOS
# ou
.venv\Scripts\activate  # Windows
```
3. Installer les dépendances :
```bash
pip install -r requirements.txt
```

## Structure du Projet

```
├── data/
│   ├── properties.yaml      # Fiches des biens
│   └── scenarios.yaml       # Configuration des scénarios
├── documentation/
│   ├── doc.md              # Guide d'investissement
│   ├── appartements.yaml   # Détails des biens
│   └── ...                 # Autres documents de référence
├── models/
│   ├── property.py         # Classe Property
│   └── scenario.py         # Classe Scenario
├── ui/
│   └── dashboard.py        # Interface Streamlit
└── requirements.txt
```

## Utilisation

1. Ajouter des biens dans `data/properties.yaml`
2. Configurer les scénarios dans `data/scenarios.yaml`
3. Lancer l'interface :
```bash
streamlit run ui/dashboard.py --server.runOnSave=true
```

## Fonctionnalités

### Comparaison des Biens
- Tableau comparatif
- Visualisation radar des caractéristiques
- Score d'accessibilité des transports
- Analyse des prix au m²

### Simulation Financière
- Paramétrage de l'apport et sa répartition
- Configuration du crédit
- Projection du patrimoine
- Calcul des mensualités et charges
- Visualisation de l'évolution patrimoniale

## Configuration

### Format des Biens (properties.yaml)
```yaml
properties:
  id-bien:
    adresse: ...
    bien:
      type: T2
      surface: 47
      etage: "1"
      orientation: "est"
      dpe: "C"
      cave: true
    prix:
      annonce: 332000
      hors_honoraires: 332000
      m2: 7064
    metros:
      - ligne: M12
        station: Station
        distance: 350
```

### Format des Scénarios (scenarios.yaml)
```yaml
scenarios:
  default:
    apport:
      total: 200000
      immobilier: 200000
    credit:
      taux: 3.32
      duree: 20
      assurance: 0.34
    rendements:
      epargne_precaution: 3.0
      investissement_risque: 7.0
```

## Documentation

Le dossier `documentation/` contient des ressources importantes :
- `doc.md` : Guide complet sur les stratégies d'investissement
- `appartements.yaml` : Fiches détaillées des biens
- Autres documents de référence sur l'investissement immobilier

## Tests

Des tests unitaires sont disponibles et peuvent être exécutés avec :
```bash
pytest
```

## Développement

Pour contribuer :
1. Fork le projet
2. Créer une branche (`git checkout -b feature/AmazingFeature`)
3. Commit les changements (`git commit -m 'Add some AmazingFeature'`)
4. Push vers la branche (`git push origin feature/AmazingFeature`)
5. Ouvrir une Pull Request 