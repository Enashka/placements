source .venv/bin/activate
# Analyse Immobilière

Outil d'analyse et de simulation pour l'investissement immobilier.

## Installation

1. Cloner le repository
2. Installer les dépendances :
```bash
pip install -r requirements.txt
```


## Structure du Projet

```
├── data/
│   ├── properties.yaml      # Fiches des biens
│   └── scenarios.yaml       # Configuration des scénarios
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
      ...
```

### Format des Scénarios (scenarios.yaml)
```yaml
scenarios:
  default:
    apport:
      total: 200000
      repartition:
        immobilier: 70
        ...
```

## Développement

Pour contribuer :
1. Fork le projet
2. Créer une branche (`git checkout -b feature/AmazingFeature`)
3. Commit les changements (`git commit -m 'Add some AmazingFeature'`)
4. Push vers la branche (`git push origin feature/AmazingFeature`)
5. Ouvrir une Pull Request 