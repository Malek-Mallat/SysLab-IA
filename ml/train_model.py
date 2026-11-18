"""
SysLab - Entrainement du modele de prediction du risque de diabete.

Couche 2 (ML) du projet. On entraine un modele CLASSIQUE (RandomForest)
sur le dataset public Pima Indians Diabetes, en utilisant UNIQUEMENT les
3 variables que SysLab sait collecter :
    - Glucose (glycemie, en mg/dL)
    - BMI     (IMC du patient)
    - Age     (age du patient)

Le modele entraine est sauvegarde en 'diabetes_model.pkl' (joblib),
pret a etre charge dans Odoo.

Prerequis :
    pip install pandas scikit-learn joblib

Usage :
    python train_model.py
"""

import os
import joblib
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report

# --- 1. Charger le dataset -------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "diabetes.csv")
MODEL_PATH = os.path.join(BASE_DIR, "diabetes_model.pkl")

df = pd.read_csv(CSV_PATH)
print("Dataset charge :", df.shape[0], "patients")

# --- 2. Nettoyage ----------------------------------------------------------
# Dans Pima, un 0 pour Glucose ou BMI est en realite une valeur manquante.
for col in ["Glucose", "BMI"]:
    df[col] = df[col].replace(0, df[col].median())

# --- 3. Selection des 3 variables (celles que SysLab collecte) -------------
FEATURES = ["Glucose", "BMI", "Age"]
X = df[FEATURES]
y = df["Outcome"]

# --- 4. Separation entrainement / test -------------------------------------
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# --- 5. Entrainement -------------------------------------------------------
model = RandomForestClassifier(n_estimators=200, max_depth=6, random_state=42)
model.fit(X_train, y_train)

# --- 6. Evaluation ---------------------------------------------------------
y_pred = model.predict(X_test)
acc = accuracy_score(y_test, y_pred)
print("\n=== Resultats ===")
print(f"Accuracy : {acc:.2%}")
print("\nFeatures utilisees :", FEATURES)
print("\nRapport detaille :")
print(classification_report(y_test, y_pred, target_names=["Non diabetique", "Diabetique"]))

# --- 7. Sauvegarde ---------------------------------------------------------
# On sauvegarde le modele ET l'ordre des features (important pour Odoo).
joblib.dump({"model": model, "features": FEATURES}, MODEL_PATH)
print(f"\nModele sauvegarde : {MODEL_PATH}")
