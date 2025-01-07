from dataclasses import dataclass
from typing import Dict, List
import yaml
import numpy as np
from .property import Property

@dataclass
class ScenarioConfig:
    apport_total: float
    repartition_immobilier: float
    repartition_epargne: float
    repartition_investissement: float
    taux_credit: float
    duree_credit: int
    taux_assurance: float
    rendement_epargne: float
    rendement_investissement: float
    evolution_immobilier: float
    horizon_simulation: int
    inflation: float
    evolution_charges: Dict[str, float]

    @classmethod
    def from_yaml(cls, yaml_file: str) -> 'ScenarioConfig':
        """Charge la configuration depuis un fichier YAML."""
        with open(yaml_file, 'r') as f:
            data = yaml.safe_load(f)['scenarios']['default']
        
        return cls(
            apport_total=data['apport']['total'],
            repartition_immobilier=data['apport']['repartition']['immobilier'],
            repartition_epargne=data['apport']['repartition']['epargne_precaution'],
            repartition_investissement=data['apport']['repartition']['investissement_risque'],
            taux_credit=data['credit']['taux'],
            duree_credit=data['credit']['duree'],
            taux_assurance=data['credit']['assurance'],
            rendement_epargne=data['rendements']['epargne_precaution'],
            rendement_investissement=data['rendements']['investissement_risque'],
            evolution_immobilier=data['rendements']['evolution_immobilier'],
            horizon_simulation=data['parametres_simulation']['horizon'],
            inflation=data['parametres_simulation']['inflation'],
            evolution_charges=data['charges_evolution']
        )

class Scenario:
    LIVRET_A_PLAFOND = 23000
    LDD_PLAFOND = 12000
    
    def __init__(self, property: Property, config: ScenarioConfig, cout_total: float = None):
        self.property = property
        self.config = config
        self.cout_total = cout_total if cout_total is not None else property.prix
        
    def calculate_monthly_payment(self) -> float:
        """Calcule la mensualité totale (crédit + assurance)."""
        apport_immo = self.config.apport_total * (self.config.repartition_immobilier / 100)
        montant_pret = self.cout_total - apport_immo
        
        # Mensualité crédit
        taux_mensuel = self.config.taux_credit / 12 / 100
        nombre_mois = self.config.duree_credit * 12
        mensualite = montant_pret * (taux_mensuel * (1 + taux_mensuel)**nombre_mois) / ((1 + taux_mensuel)**nombre_mois - 1)
        
        # Ajout assurance
        mensualite_assurance = (montant_pret * self.config.taux_assurance / 100) / 12
        
        return round(mensualite + mensualite_assurance, 2)

    def simulate_epargne_securisee(self, montant_initial, mois):
        """Simule l'évolution de l'épargne sécurisée en tenant compte des plafonds"""
        # Répartition initiale
        livret_a = min(montant_initial, self.LIVRET_A_PLAFOND)
        reste_apres_livret_a = montant_initial - livret_a
        
        ldd = min(reste_apres_livret_a, self.LDD_PLAFOND)
        reste_apres_ldd = reste_apres_livret_a - ldd
        
        # Le reste va sur un compte à terme ou livret bancaire avec une performance moindre
        compte_terme = reste_apres_ldd
        
        evolution = np.zeros(mois)
        for m in range(mois):
            if m == 0:
                evolution[m] = montant_initial
            else:
                # Livret A et LDD à taux plein
                livret_a *= (1 + self.config.rendement_epargne/12/100)
                livret_a = min(livret_a, self.LIVRET_A_PLAFOND)
                
                ldd *= (1 + self.config.rendement_epargne/12/100)
                ldd = min(ldd, self.LDD_PLAFOND)
                
                # Compte à terme avec rendement réduit (environ 2% de moins)
                if compte_terme > 0:
                    compte_terme *= (1 + (self.config.rendement_epargne-2)/12/100)
                
                evolution[m] = livret_a + ldd + compte_terme
        
        return evolution

    def simulate_patrimoine(self) -> Dict[str, List[float]]:
        """Simule l'évolution du patrimoine sur l'horizon défini."""
        nb_mois = self.config.horizon_simulation * 12
        
        # Initialisation des composantes du patrimoine
        apport_immo = self.config.apport_total * (self.config.repartition_immobilier / 100)
        epargne = self.config.apport_total * (self.config.repartition_epargne / 100)
        investissement = self.config.apport_total * (self.config.repartition_investissement / 100)
        
        # Calcul du prêt
        montant_pret = self.cout_total - apport_immo
        # On ne prend que la mensualité du prêt, pas les autres charges
        mensualite = self.calculate_monthly_payment()
        
        # Arrays pour stocker l'évolution
        valeur_bien = np.zeros(nb_mois + 1)
        capital_restant = np.zeros(nb_mois + 1)
        epargne_evolution = np.zeros(nb_mois + 1)
        investissement_evolution = np.zeros(nb_mois + 1)
        patrimoine_total = np.zeros(nb_mois + 1)
        
        # Valeurs initiales
        valeur_bien[0] = self.cout_total
        capital_restant[0] = montant_pret
        epargne_evolution[0] = epargne
        investissement_evolution[0] = investissement
        patrimoine_total[0] = valeur_bien[0] - capital_restant[0] + epargne + investissement
        
        # Simulation mois par mois
        for mois in range(1, nb_mois + 1):
            # Évolution du bien
            valeur_bien[mois] = valeur_bien[mois-1] * (1 + self.config.evolution_immobilier/12/100)
            
            # Évolution du prêt (uniquement le remboursement, pas les charges)
            taux_mensuel = self.config.taux_credit / 12 / 100
            interet = capital_restant[mois-1] * taux_mensuel
            capital_amorti = mensualite - interet
            capital_restant[mois] = max(0, capital_restant[mois-1] - capital_amorti)
            
            # Évolution épargne et investissements
            epargne_evolution[mois] = self.simulate_epargne_securisee(epargne, mois)[mois-1]
            investissement_evolution[mois] = investissement_evolution[mois-1] * (1 + self.config.rendement_investissement/12/100)
            
            # Patrimoine total (valeur bien - capital restant + épargne + investissements)
            patrimoine_total[mois] = (valeur_bien[mois] - capital_restant[mois] + 
                                    epargne_evolution[mois] + investissement_evolution[mois])
        
        return {
            'valeur_bien': valeur_bien.tolist(),
            'capital_restant': capital_restant.tolist(),
            'epargne': epargne_evolution.tolist(),
            'investissement': investissement_evolution.tolist(),
            'patrimoine_total': patrimoine_total.tolist()
        }

    def calculate_metrics(self) -> Dict:
        """Calcule les métriques clés du scénario."""
        mensualite = self.calculate_monthly_payment()
        charges_totales = mensualite + self.property.charges_mensuelles
        if self.property.energie:
            charges_totales += self.property.energie
        if self.property.taxe_fonciere:
            charges_totales += self.property.taxe_fonciere / 12
            
        simulation = self.simulate_patrimoine()
        patrimoine_initial = simulation['patrimoine_total'][0]
        patrimoine_final = simulation['patrimoine_total'][-1]
        
        return {
            'mensualite_credit': mensualite,
            'charges_totales': charges_totales,
            'patrimoine_initial': patrimoine_initial,
            'patrimoine_final': patrimoine_final,
            'rendement_total': ((patrimoine_final/patrimoine_initial)**(1/self.config.horizon_simulation) - 1) * 100
        } 