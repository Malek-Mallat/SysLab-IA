# 🧪 SysLab — ERP pour laboratoire d'analyses médicales (Odoo 17)

> Module Odoo 17 Community qui gère le flux complet d'un laboratoire d'analyses
> médicales, du patient jusqu'au bulletin PDF, avec une **couche d'IA d'aide à
> l'interprétation** validée par un humain.
> **Le système propose, il ne diagnostique jamais.**

![Odoo](https://img.shields.io/badge/Odoo-17.0%20Community-714B67)
![Python](https://img.shields.io/badge/Python-3.12-3776AB)
![scikit--learn](https://img.shields.io/badge/scikit--learn-1.8-F7931E)
![Licence](https://img.shields.io/badge/licence-LGPL--3-blue)

Mini-projet académique (ERP), réalisé par **Malek Mallat**.

---

## Sommaire
1. [Fonctionnalités](#-fonctionnalités)
2. [Architecture : interprétation en 2 couches](#-architecture--interprétation-en-2-couches)
3. [Modèles de données](#-modèles-de-données)
4. [Structure du module](#-structure-du-module)
5. [Installation](#-installation)
6. [Couche ML : entraînement du modèle](#-couche-ml--entraînement-du-modèle)
7. [Utilisation](#-utilisation)
8. [Captures d'écran](#-captures-décran)
9. [Éthique et limites](#-éthique-et-limites)

---

## ✨ Fonctionnalités

| Domaine | Ce que fait SysLab |
|---|---|
| **Patients** | Fiche patient, âge et IMC calculés automatiquement, badge de corpulence (OMS), historique des demandes (smart button) |
| **Médecins** | Prescripteurs, avec leurs demandes associées |
| **Catalogue** | Analyses par famille (biochimie, hématologie), unités, plages de référence, tarifs |
| **Demandes** | Référence automatique `DEM/ANNÉE/00001`, workflow *Brouillon → En cours → Validé → Facturé*, verrouillage après validation |
| **Résultats** | Saisie des valeurs, **interprétation automatique** (Normal / Bas / Élevé) et commentaire |
| **IA** | **Estimation du risque de diabète** (Random Forest entraîné sur NHANES) à partir de la glycémie, de l'IMC, de l'âge, du sexe et, si elle est demandée, de l'HbA1c |
| **Bulletin PDF** | Bulletin de résultats imprimable, avec le bloc IA et les mentions éthiques |
| **Facturation** | Création de la facture client (module natif `account`) depuis une demande validée |
| **Pilotage** | Tableau de bord (KPI), vues Kanban, graphiques et pivots, filtres et regroupements |

---

## 🧠 Architecture : interprétation en 2 couches

```
                ┌───────────────────────────────────────────────────────────┐
  Saisie d'une  │  COUCHE 1 — Règles (models/resultat.py)                   │
  valeur  ────► │  Compare chaque valeur à la plage de référence            │
                │  → Normal / Bas / Élevé + commentaire                     │
                │  Universelle, déterministe, fiable                        │
                └───────────────────────────────────────────────────────────┘
                                         │
                                         ▼
                ┌───────────────────────────────────────────────────────────┐
  Bouton        │  COUCHE 2 — Machine Learning (models/demande_ml.py)       │
  « Prédire » ► │  Combine : [Glycémie, (HbA1c), IMC, Âge, Sexe]            │
                │  → probabilité de diabète (%) + niveau faible/modéré/élevé│
                │  Random Forest entraîné hors Odoo sur NHANES (ml/)        │
                └───────────────────────────────────────────────────────────┘
                                         │
                                         ▼
                      Validation par le biologiste / médecin
```

* **Couche 1** : elle se déclenche en temps réel, dès la saisie, grâce à un champ calculé et stocké.
* **Couche 2** : elle se déclenche à la demande, avec un bouton visible seulement si la demande contient une glycémie (code `GLY`).
  * La glycémie saisie en **g/L** est convertie en **mg/dL** (× 100), l'unité du dataset. Les valeurs non plausibles (erreur d'unité) sont refusées.
  * Si la demande contient une **HbA1c** (code `HBA1C`), le modèle « HbA1c » est utilisé ; sinon, le modèle « base ».
  * Le modèle est réservé aux **adultes de 20 ans et plus** (population d'entraînement) : pour un patient plus jeune, la prédiction est refusée avec un message clair.
  * Le modèle renvoie `predict_proba`. Le niveau est **faible** sous 30 %, **modéré** de 30 à 60 %, **élevé** au-delà de 60 %.
  * Les données envoyées au modèle sont **enregistrées** (traçabilité).
  * L'estimation est **effacée automatiquement** si les résultats ou le patient changent.
  * Si scikit-learn ou joblib manquent, l'utilisateur reçoit un message clair qui donne la commande d'installation. Il n'y a pas de plantage.

---

## 🗂 Modèles de données

| Modèle | Rôle | Champs principaux |
|---|---|---|
| `syslab.analyse` | Catalogue | `name`, `code`, `famille`, `unite`, `borne_min`, `borne_max`, `prix`, `actif` |
| `syslab.patient` | Patients | `name`, `date_naissance`, `age`*, `sexe`, `poids`, `taille`, `imc`*, `imc_categorie`*, `demande_ids` |
| `syslab.medecin` | Prescripteurs | `name`, `specialite`, `telephone`, `email`, `demande_ids` |
| `syslab.demande` | Demandes d'analyses | `name` (séquence), `patient_id`, `medecin_id`, `date_demande`, `state`, `resultat_ids`, `prix_total`*, `nb_anomalies`*, `facture_id`, `risque_diabete`, `risque_niveau` |
| `syslab.resultat` | Résultats | `demande_id`, `analyse_id`, `valeur`, `interpretation`*, `commentaire`* |
| `syslab.dashboard` | Abstrait (sans table) | `get_data()` : calcule les KPI du tableau de bord |

\* champ calculé

---

## 📁 Structure du module

```
syslab/
├── __manifest__.py
├── models/
│   ├── analyse.py, patient.py, medecin.py
│   ├── demande.py          # workflow, indicateurs, facturation
│   ├── resultat.py         # COUCHE 1 : interprétation par règles
│   ├── demande_ml.py       # COUCHE 2 : prédiction du risque de diabète
│   └── dashboard.py        # KPI du tableau de bord
├── views/                  # liste, formulaire, kanban, graph, pivot, recherche, menus
├── report/demande_report.xml   # bulletin PDF (QWeb)
├── static/src/dashboard/   # tableau de bord (composant OWL : JS + XML + SCSS)
├── data/                   # séquence DEM/ANNÉE/xxxxx + 5 analyses pré-chargées
├── security/ir.model.access.csv
└── ml/
    ├── train_model_nhanes.py       # entraînement du modèle utilisé par Odoo
    ├── nhanes_diabetes.csv         # jeu NHANES nettoyé (2314 adultes)
    ├── diabetes_model_nhanes.pkl   # modèles entraînés (joblib), lus par Odoo
    ├── train_model.py              # ancien modèle Pima (gardé pour comparaison)
    ├── diabetes.csv                # dataset Pima Indians Diabetes
    └── diabetes_model.pkl          # ancien modèle Pima
```

---

## ⚙ Installation

### Prérequis
* **Odoo 17 Community**. Dépendances Odoo : `base` et `account` (facturation).
* Pour la couche IA : **scikit-learn 1.8** et **joblib**, installés **dans le Python utilisé par Odoo**.

### 1. Copier le module
```bash
git clone https://github.com/Malek-Mallat/SysLab-IA.git syslab
```
Le dossier doit s'appeler `syslab` (nom technique du module). Placez-le dans un répertoire déclaré dans `addons_path` (fichier `odoo.conf`), par exemple `C:\odoo_addons`.

### 2. Installer les librairies ML dans le Python d'Odoo
Sous Windows (installeur officiel d'Odoo), dans PowerShell **en administrateur** :
```powershell
& "C:\Program Files\Odoo 17.0.xxxxxxxx\python\python.exe" -s -m pip install scikit-learn==1.8.0 joblib
```
> ⚠️ Le service Odoo tourne sous un compte système (`LocalService`). Des librairies
> installées dans le profil utilisateur (`AppData\Roaming\Python`) ne sont **pas** visibles
> par le service. L'option `-s` fait ignorer ce dossier à pip, qui installe alors les
> librairies dans le Python d'Odoo, même si elles existent déjà dans votre profil.
> La version de scikit-learn doit correspondre à celle qui a servi à créer le `.pkl`.

### 3. Installer ou mettre à jour le module
```powershell
Get-Service *odoo* | Stop-Service
& "C:\Program Files\Odoo 17.0.xxxxxxxx\python\python.exe" "C:\Program Files\Odoo 17.0.xxxxxxxx\server\odoo-bin" -c "C:\Program Files\Odoo 17.0.xxxxxxxx\server\odoo.conf" -d <ma_base> -u syslab --stop-after-init
Get-Service *odoo* | Start-Service
```
Pour une première installation, remplacez `-u syslab` par `-i syslab`, ou passez par *Applications → SysLab → Activer* (mode développeur, après « Mettre à jour la liste des applications »).
Après une mise à jour, faites **Ctrl+Maj+R** dans le navigateur pour recharger le JavaScript du tableau de bord.

### 4. Configurer l'envoi d'emails (Gmail)
Le bouton **« Envoyer le bulletin par email »** génère le PDF du bulletin et l'envoie au
biologiste. **Sans serveur de messagerie sortant, aucun email ne part réellement** : le
message est seulement enregistré dans l'historique de la demande et reste en file d'attente.

> 🔒 Le module ne contient **aucun** mot de passe ni serveur SMTP. Les identifiants se
> saisissent uniquement dans l'interface d'Odoo et sont stockés dans la base de données,
> jamais dans le code (voir `.gitignore`).

**a. Côté Google** (compte qui enverra les emails) :
1. Activer la **validation en 2 étapes** : <https://myaccount.google.com/security>.
2. Créer un **mot de passe d'application** : <https://myaccount.google.com/apppasswords>,
   puis donner un nom (ex. « Odoo SysLab ») et copier le code de 16 caractères affiché.
   Le mot de passe habituel du compte Gmail ne fonctionne pas.

**b. Côté Odoo** :
1. Activer le **mode développeur** (*Paramètres → Activer le mode développeur*).
2. *Paramètres → Technique → Email → Serveurs de messagerie sortants → Nouveau* :

   | Champ | Valeur |
   |---|---|
   | Description | Gmail |
   | Authentifier avec | Nom d'utilisateur |
   | Serveur SMTP | `smtp.gmail.com` |
   | Port SMTP | `587` |
   | Sécurité de la connexion | **TLS (STARTTLS)** |
   | Nom d'utilisateur | votre adresse Gmail |
   | Mot de passe | le **mot de passe d'application** (16 caractères) |
   | Filtre « De » | votre adresse Gmail (facultatif) |

3. Cliquer sur **« Tester la connexion »**, puis enregistrer.
4. *SysLab → Configuration → Laboratoire* : l'**email de la société** doit être la même
   adresse Gmail, car Gmail n'accepte d'envoyer qu'au nom du compte authentifié.
   Renseigner aussi l'**email du biologiste** (destinataire par défaut des bulletins).

**c. Tester** : sur une demande validée, cliquer sur *Envoyer le bulletin par email*, puis
*Envoyer*. L'email doit arriver avec la pièce jointe `Bulletin - DEM-AAAA-xxxxx.pdf`.
En cas d'échec, le motif est visible dans *Paramètres → Technique → Email → Emails*
(mode développeur).

---

## 🤖 Couche ML : entraînement du modèle

### Dataset : NHANES 2017-2018
* **Source** : *National Health and Nutrition Examination Survey* (CDC, États-Unis), données publiques.
  Le script télécharge 5 fichiers (démographie, glycémie à jeun, HbA1c, mesures corporelles,
  questionnaire diabète) et les joint par identifiant patient.
* **Population** : **2314 adultes de 20 ans et plus**, hommes (48 %) et femmes, dont la glycémie à jeun
  a été mesurée ; 17,4 % sont diabétiques.
* **Étiquette** : « un médecin vous a-t-il déjà dit que vous étiez diabétique ? » (`DIQ010`, oui / non).
  Les réponses « limite », « refus » et « ne sait pas » sont exclues.
  > ⚠️ **Pas de fuite de l'étiquette.** On n'utilise volontairement pas « glycémie ≥ 126 mg/dL ou
  > HbA1c ≥ 6,5 % » comme étiquette : ces valeurs sont aussi des variables d'entrée, et le modèle
  > apprendrait simplement le seuil.

### Deux modèles
| Modèle | Variables | Utilisé quand |
|---|---|---|
| `base` | Glycémie (mg/dL), IMC, âge, sexe | toujours |
| `hba1c` | Glycémie, **HbA1c (%)**, IMC, âge, sexe | la demande contient une HbA1c |

Pour chacun, le script compare une **régression logistique** et un **Random Forest** (validation
croisée 5 plis, AUC) et garde le meilleur (Random Forest dans les deux cas). Il évalue ensuite le
modèle sur un jeu de test de 20 %, puis le ré-entraîne sur toutes les données.

### Résultats (jeu de test)
| Modèle | AUC | Sensibilité* | Spécificité* | Brier** |
|---|---|---|---|---|
| `base` (glycémie, IMC, âge, sexe) | **0,92** | 70 % | 91 % | 0,076 |
| `hba1c` (+ HbA1c) | **0,95** | 80 % | 93 % | 0,059 |
| *Ancien modèle Pima, appliqué aux mêmes patients NHANES* | 0,83 | 83 % | 64 % | 0,120 |

\* au seuil de 30 % (« modéré » ou « élevé ») : part des diabétiques détectés / des non-diabétiques classés « faible ».
\** score de Brier : erreur moyenne des probabilités (plus il est bas, plus un « 70 % » veut vraiment dire 70 %).

L'accuracy n'est pas utilisée comme indicateur principal : avec 17 % de diabétiques, un modèle
qui répondrait toujours « non » obtiendrait déjà 83 %. L'ancien modèle Pima se transpose mal :
il génère beaucoup de fausses alertes (spécificité de 64 %).

```bash
cd ml
pip install pandas scikit-learn==1.8.0 joblib
python train_model_nhanes.py
```
Le script enregistre `nhanes_diabetes.csv` et `diabetes_model_nhanes.pkl`. Les fichiers bruts
téléchargés (`ml/nhanes_raw/`) ne sont pas versionnés. Odoo vérifie au chargement que les
variables demandées par chaque modèle sont bien fournies par SysLab.

---

## 🚀 Utilisation

1. **Configuration → Catalogue d'analyses** : vérifier les plages de référence. 6 analyses sont pré-chargées : GLY, CHOL, TRIG, CREA, HB et HBA1C (utilisée par l'IA).
2. **Patients** : créer la fiche. La date de naissance, le sexe, le poids et la taille sont nécessaires à l'IA.
3. **Demandes → Nouveau** : choisir le patient et le médecin, ajouter les analyses, puis **Démarrer**.
4. Saisir les valeurs : l'interprétation (couche 1) s'affiche aussitôt.
5. **Prédire le risque de diabète** (couche 2) : une jauge et un badge coloré apparaissent, avec la mention éthique.
6. **Valider**, puis **Imprimer le bulletin** et **Créer la facture**.
7. Suivre l'activité depuis le **Tableau de bord**, le **Kanban** et le menu **Reporting** (graphiques et pivots).

---

## 📸 Captures d'écran

> À placer dans `docs/screenshots/` avec ces noms de fichiers.

| Écran | Fichier |
|---|---|
| Tableau de bord (KPI) | `docs/screenshots/01_tableau_de_bord.png` |
| Kanban des demandes par statut | `docs/screenshots/02_kanban_demandes.png` |
| Formulaire de demande : résultats colorés + bloc IA | `docs/screenshots/03_demande_prediction_ia.png` |
| Fiche patient (smart button, badge de corpulence) | `docs/screenshots/04_fiche_patient.png` |
| Reporting : graphique des résultats par analyse | `docs/screenshots/05_graph_resultats.png` |
| Reporting : pivot des demandes | `docs/screenshots/06_pivot_demandes.png` |
| Bulletin PDF | `docs/screenshots/07_bulletin_pdf.png` |
| Facture générée | `docs/screenshots/08_facture.png` |

<!-- Exemple d'insertion :
![Tableau de bord](docs/screenshots/01_tableau_de_bord.png)
-->

---

## ⚖ Éthique et limites

* **Aide à la décision, pas de diagnostic.** Chaque estimation porte la mention
  *« Résultat indicatif, à valider par un professionnel »*, à l'écran comme sur le bulletin PDF.
* **Transparence** : le modèle, le dataset, les variables et l'AUC sont affichés. Les valeurs envoyées au modèle sont conservées.
* **Limites connues** :
  * population **américaine** (NHANES) : elle couvre hommes et femmes de 20 ans et plus, mais elle n'est pas tunisienne. Un usage réel exigerait une validation sur des données locales ;
  * **pas d'enfants** : la prédiction est refusée avant 20 ans ;
  * l'étiquette est le diabète **déjà diagnostiqué** : environ 100 personnes du jeu ont une glycémie élevée sans diagnostic et comptent comme « non diabétiques ». De plus, les diabétiques traités ont souvent une glycémie abaissée ;
  * données **transversales** : le modèle estime la probabilité d'un diabète actuel, pas le risque d'en développer un dans les années à venir ;
  * les poids de sondage de NHANES ne sont pas utilisés : les proportions ne représentent pas exactement la population américaine ;
  * il manque encore les antécédents familiaux et la pression artérielle, que SysLab ne collecte pas ;
  * une seule glycémie à jeun ne suffit pas à poser un diagnostic de diabète.
* Les données de santé sont sensibles. Un déploiement réel exigerait des droits d'accès par rôle, une traçabilité complète et la conformité réglementaire (RGPD, hébergement de données de santé).

---

## 👤 Auteur

**Malek Mallat** · [github.com/Malek-Mallat](https://github.com/Malek-Mallat)

Licence **LGPL-3**, comme indiqué dans `__manifest__.py`.
