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
4. Configurer les variables d'environnement :
   - Créer un fichier `.env` à la racine du projet
   - Ajouter votre clé API OpenAI : `OPENAI_API_KEY=votre_clé_api`

## Structure du Projet

```
├── data/
│   ├── properties.json     # Base de données des biens
│   ├── scenarios.yaml      # Configuration des scénarios
│   └── renseignement-prompt.yaml  # Prompts pour l'API OpenAI
├── documentation/
│   ├── doc.md             # Guide d'investissement
│   └── ...                # Autres documents de référence
├── models/
│   ├── property.py        # Classe Property
│   └── scenario.py        # Classe Scenario
├── ui/
│   └── dashboard.py       # Interface Streamlit
└── requirements.txt
```

## Utilisation

1. Configurer les scénarios dans `data/scenarios.yaml`
2. Lancer l'interface :
```bash
streamlit run ui/dashboard.py --server.runOnSave=true
```

## Fonctionnalités

### Gestion des Biens
- Interface de gestion complète des biens immobiliers
- Ajout de nouveaux biens via description en texte libre (utilisation de l'API OpenAI)
- Modification et suppression des biens existants
- Visualisation détaillée des caractéristiques de chaque bien

### Comparaison des Biens
- Tableau comparatif des caractéristiques principales
- Visualisation radar des points clés (prix/m², transport, DPE, atouts)
- Score d'accessibilité des transports
- Analyse des prix au m²

### Simulation Financière
- Paramétrage de l'apport et sa répartition
- Configuration du crédit immobilier
- Gestion de l'épargne (sécurisée et dynamique)
- Calcul des mensualités et charges
- Projection du patrimoine sur l'horizon choisi
- Visualisation de l'évolution patrimoniale

## Configuration

### Format des Biens (properties.json)
Les biens sont stockés au format JSON avec les informations suivantes :
- Informations générales (adresse, surface, étage, etc.)
- Prix et frais associés
- Caractéristiques énergétiques (DPE, GES)
- Transports à proximité
- Charges et taxes
- Points forts et points de vigilance

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
      evolution_immobilier: 1.5
```

## Documentation

Le dossier `documentation/` contient des ressources importantes :
- `doc.md` : Guide complet sur les stratégies d'investissement
- Autres documents de référence sur l'investissement immobilier

## Développement

Pour contribuer :
1. Fork le projet
2. Créer une branche (`git checkout -b feature/AmazingFeature`)
3. Commit les changements (`git commit -m 'Add some AmazingFeature'`)
4. Push vers la branche (`git push origin feature/AmazingFeature`)
5. Ouvrir une Pull Request 