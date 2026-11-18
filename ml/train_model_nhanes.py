"""
SysLab - Entrainement du modele de risque de diabete sur NHANES 2017-2018.

Pourquoi NHANES plutot que Pima ?
    Pima ne contient que des femmes d'origine Pima de 21 ans et plus, avec 3 variables.
    NHANES (CDC, Etats-Unis, donnees publiques) couvre des hommes et des femmes de tous
    ages, et fournit la glycemie a jeun, l'HbA1c, l'IMC, l'age, le sexe et le diagnostic.

Etiquette (ce que le modele apprend a predire) :
    Diabete = 1 si un medecin a deja dit a la personne qu'elle est diabetique
    (question DIQ010 = "Oui"), 0 si "Non". Les reponses "limite / prediabete",
    "refus" ou "ne sait pas" sont exclues.
    On n'utilise PAS "glycemie >= 126 mg/dL ou HbA1c >= 6,5 %" comme etiquette :
    ces valeurs sont aussi des variables d'entree, le modele apprendrait juste le seuil
    (fuite de l'etiquette) et ses scores seraient artificiellement parfaits.

Deux modeles sont entraines :
    - "base"  : [Glucose, BMI, Age, Sexe]          -> toujours utilisable
    - "hba1c" : [Glucose, HbA1c, BMI, Age, Sexe]   -> si la demande contient une HbA1c
Pour chacun, on compare une regression logistique et un Random Forest
(validation croisee, AUC) et on garde le meilleur.

Sortie : diabetes_model_nhanes.pkl (joblib), lu par Odoo (models/demande_ml.py) :
    {"models": {"base": {"model", "features", "metrics"}, "hba1c": {...}},
     "dataset": ..., "label": ..., "sklearn_version": ...}

Prerequis : pip install pandas scikit-learn==1.8.0 joblib
Usage     : python train_model_nhanes.py
"""
import os
import urllib.request

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, brier_score_loss, confusion_matrix,
                             roc_auc_score)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(BASE_DIR, "nhanes_raw")           # fichiers bruts (non versionnes)
CSV_PATH = os.path.join(BASE_DIR, "nhanes_diabetes.csv")  # jeu nettoye (versionne)
MODEL_PATH = os.path.join(BASE_DIR, "diabetes_model_nhanes.pkl")
PIMA_MODEL_PATH = os.path.join(BASE_DIR, "diabetes_model.pkl")  # ancien modele, pour comparaison

URL = "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/{}.xpt"
FICHIERS = {
    "DEMO_J": ["SEQN", "RIDAGEYR", "RIAGENDR"],  # demographie : age, sexe
    "GLU_J": ["SEQN", "LBXGLU"],                 # glycemie a jeun (mg/dL)
    "GHB_J": ["SEQN", "LBXGH"],                  # HbA1c (%)
    "BMX_J": ["SEQN", "BMXBMI"],                 # IMC
    "DIQ_J": ["SEQN", "DIQ010"],                 # "un medecin vous a-t-il dit que vous etiez diabetique ?"
}
SEUIL_MODERE, SEUIL_ELEVE = 0.30, 0.60  # memes seuils que dans Odoo
RANDOM_STATE = 42


# --- 1. Telechargement (une seule fois) et chargement --------------------------
def charger_nhanes():
    os.makedirs(RAW_DIR, exist_ok=True)
    tables = []
    for nom, colonnes in FICHIERS.items():
        chemin = os.path.join(RAW_DIR, nom + ".xpt")
        if not os.path.isfile(chemin):
            print("Telechargement de", nom, "...")
            urllib.request.urlretrieve(URL.format(nom), chemin)
        tables.append(pd.read_sas(chemin, format="xport")[colonnes])
    # Jointure sur l'identifiant patient. On part de GLU_J : la glycemie a jeun
    # n'est mesuree que sur un sous-echantillon du matin.
    df = tables[1]
    for t in (tables[0], tables[2], tables[3], tables[4]):
        df = df.merge(t, on="SEQN", how="left")
    return df


# --- 2. Nettoyage ---------------------------------------------------------------
def nettoyer(df):
    df = df[df["RIDAGEYR"] >= 20]                 # adultes uniquement
    df = df[df["DIQ010"].isin([1, 2])]            # Oui / Non (exclut limite, refus, ne sait pas)
    df = df.dropna(subset=["LBXGLU", "BMXBMI"])
    return pd.DataFrame({
        "Glucose": df["LBXGLU"],                  # mg/dL (comme Pima)
        "HbA1c": df["LBXGH"],                     # % (peut manquer : 3 cas)
        "BMI": df["BMXBMI"],
        "Age": df["RIDAGEYR"],                    # NHANES plafonne l'age a 80 ans
        "Sexe": (df["RIAGENDR"] == 1).astype(int),  # 1 = homme, 0 = femme
        "Diabete": (df["DIQ010"] == 1).astype(int),
    }).reset_index(drop=True)


# --- 3. Metriques ---------------------------------------------------------------
def metriques(y, proba):
    """AUC, calibration (Brier), et sensibilite / specificite au seuil 'modere' (30 %) :
    part des diabetiques classes au moins 'modere', part des non-diabetiques classes 'faible'."""
    pred = (proba >= SEUIL_MODERE).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred).ravel()
    return {
        "auc": round(roc_auc_score(y, proba), 3),
        "brier": round(brier_score_loss(y, proba), 3),
        "sensibilite": round(tp / (tp + fn), 3),
        "specificite": round(tn / (tn + fp), 3),
        "accuracy_50": round(accuracy_score(y, (proba >= 0.5).astype(int)), 3),
    }


def candidats():
    return {
        "Regression logistique": make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)),
        "Random Forest": RandomForestClassifier(n_estimators=300, max_depth=5, min_samples_leaf=20,
                                                random_state=RANDOM_STATE),
    }


def entrainer(nom, features, train, test):
    print(f"\n=== Modele '{nom}' : {features} ===")
    tr, te = train.dropna(subset=features), test.dropna(subset=features)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    meilleur, meilleur_auc = None, -1
    for libelle, modele in candidats().items():
        auc = cross_val_score(modele, tr[features], tr["Diabete"], cv=cv, scoring="roc_auc").mean()
        print(f"  {libelle:<22} AUC (validation croisee 5 plis) = {auc:.3f}")
        if auc > meilleur_auc:
            meilleur, meilleur_auc, algo = modele, auc, libelle
    meilleur.fit(tr[features], tr["Diabete"])
    m = metriques(te["Diabete"], meilleur.predict_proba(te[features])[:, 1])
    m.update(algorithme=algo, n_train=len(tr), n_test=len(te))
    print(f"  -> retenu : {algo}")
    print(f"  Jeu de test ({len(te)} personnes) : AUC {m['auc']} | Brier {m['brier']} | "
          f"sensibilite {m['sensibilite']:.0%} | specificite {m['specificite']:.0%} "
          f"(seuil {SEUIL_MODERE:.0%}) | accuracy {m['accuracy_50']:.0%} (seuil 50 %)")
    # Modele final : re-entraine sur TOUTES les donnees (les metriques restent celles du test)
    tout = pd.concat([tr, te])
    meilleur.fit(tout[features], tout["Diabete"])
    return {"model": meilleur, "features": features, "metrics": m}


def comparer_pima(test):
    """Applique l'ancien modele Pima au jeu de test NHANES : est-il transposable ?"""
    if not os.path.isfile(PIMA_MODEL_PATH):
        return None
    pima = joblib.load(PIMA_MODEL_PATH)
    X = test[["Glucose", "BMI", "Age"]]
    m = metriques(test["Diabete"], pima["model"].predict_proba(X)[:, 1])
    print(f"\n=== Comparaison : ancien modele Pima applique a NHANES ===\n"
          f"  AUC {m['auc']} | Brier {m['brier']} | sensibilite {m['sensibilite']:.0%} | "
          f"specificite {m['specificite']:.0%}")
    return m


def main():
    df = nettoyer(charger_nhanes())
    df.to_csv(CSV_PATH, index=False)
    print(f"Jeu nettoye : {len(df)} adultes, dont {df['Diabete'].mean():.1%} diabetiques "
          f"diagnostiques ({df['Sexe'].mean():.0%} d'hommes) -> {os.path.basename(CSV_PATH)}")

    train, test = train_test_split(df, test_size=0.2, random_state=RANDOM_STATE,
                                   stratify=df["Diabete"])
    modeles = {
        "base": entrainer("base", ["Glucose", "BMI", "Age", "Sexe"], train, test),
        "hba1c": entrainer("hba1c", ["Glucose", "HbA1c", "BMI", "Age", "Sexe"], train, test),
    }
    pima = comparer_pima(test.dropna(subset=["Glucose", "BMI", "Age"]))

    joblib.dump({
        "models": modeles,
        "dataset": "NHANES 2017-2018 (CDC), adultes de 20 ans et plus",
        "label": "Diabete deja diagnostique par un medecin (DIQ010)",
        "sklearn_version": sklearn.__version__,
        "comparaison_pima": pima,
    }, MODEL_PATH)
    print(f"\nModele sauvegarde : {MODEL_PATH} (scikit-learn {sklearn.__version__})")


if __name__ == "__main__":
    np.random.seed(RANDOM_STATE)
    main()
