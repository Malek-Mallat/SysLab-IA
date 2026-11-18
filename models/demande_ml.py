"""
SysLab - COUCHE 2 : estimation du risque de diabete par Machine Learning.

    Couche 1 (resultat.py) : regles -> interprete CHAQUE resultat (bas / normal / eleve).
    Couche 2 (ce fichier)  : modele ML -> estime un risque GLOBAL a partir de
                             plusieurs donnees combinees (glycemie + IMC + age).

Le modele (RandomForest, scikit-learn) est entraine HORS d'Odoo par ml/train_model.py
sur le dataset public Pima Indians Diabetes, puis sauvegarde avec joblib dans
ml/diabetes_model.pkl sous la forme : {"model": <RandomForest>, "features": [...]}.

Ethique : le resultat est une AIDE a la decision, jamais un diagnostic.
Il doit etre valide par un professionnel de sante.
"""
import logging
import os
import warnings

from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Chemin du modele : <module>/ml/diabetes_model.pkl
MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          'ml', 'diabetes_model.pkl')

# Ordre des variables attendu par le modele (verifie au chargement)
FEATURES = ['Glucose', 'BMI', 'Age']

# Seuils du niveau de risque (en %)
SEUIL_MODERE = 30.0
SEUIL_ELEVE = 60.0

# Cache memoire : le .pkl n'est lu qu'une fois (rechargé si le fichier change)
_MODEL_CACHE = {'mtime': None, 'model': None}

MSG_INSTALL = (
    "Les librairies de Machine Learning ne sont pas installees dans le Python d'Odoo.\n\n"
    "Ouvrez PowerShell en administrateur et executez :\n"
    "& \"C:\\Program Files\\Odoo 17.0.20260930\\python\\python.exe\" -s -m pip install "
    "scikit-learn==1.8.0 joblib\n\n"
    "(l'option -s force l'installation dans le Python d'Odoo, et non dans le profil "
    "utilisateur, invisible pour le service)\n\n"
    "puis redemarrez le service Odoo.\n(Detail technique : %s)"
)


def _charger_modele():
    """Charge le modele depuis ml/diabetes_model.pkl (avec cache).

    Leve UserError avec un message clair si les librairies ou le fichier manquent.
    """
    try:
        import joblib  # noqa: F401 - import local : le module Odoo reste installable sans joblib
    except ImportError as e:
        raise UserError(MSG_INSTALL % e)

    if not os.path.isfile(MODEL_PATH):
        raise UserError(
            "Fichier du modele introuvable :\n%s\n\n"
            "Lancez d'abord l'entrainement : python ml/train_model.py" % MODEL_PATH)

    mtime = os.path.getmtime(MODEL_PATH)
    if _MODEL_CACHE['model'] is not None and _MODEL_CACHE['mtime'] == mtime:
        return _MODEL_CACHE['model']

    try:
        data = joblib.load(MODEL_PATH)
    except ImportError as e:
        # joblib present mais scikit-learn absent : le depicklage echoue
        raise UserError(MSG_INSTALL % e)
    except Exception as e:
        _logger.exception("Erreur au chargement du modele ML")
        raise UserError("Impossible de charger le modele ML (%s).\n"
                        "Verifiez que scikit-learn est en version 1.8.0." % e)

    if not isinstance(data, dict) or 'model' not in data:
        raise UserError("Format du fichier modele inattendu : "
                        "attendu {'model': ..., 'features': [...]}.")
    if list(data.get('features', FEATURES)) != FEATURES:
        raise UserError("Le modele attend les variables %s, or SysLab fournit %s."
                        % (data.get('features'), FEATURES))

    _MODEL_CACHE.update(mtime=mtime, model=data['model'])
    _logger.info("Modele ML charge depuis %s", MODEL_PATH)
    return data['model']


class DemandeML(models.Model):
    _inherit = 'syslab.demande'

    # ---------- Resultat de la prediction ----------
    risque_diabete = fields.Float(string="Risque de diabete (%)", digits=(5, 1),
                                  readonly=True, copy=False)
    risque_niveau = fields.Selection([
        ('faible', 'Faible'),
        ('modere', 'Modere'),
        ('eleve', 'Eleve'),
    ], string="Niveau de risque", readonly=True, copy=False)
    risque_date = fields.Datetime(string="Estime le", readonly=True, copy=False)

    # ---------- Tracabilite : donnees reellement envoyees au modele ----------
    risque_glucose = fields.Float(string="Glycemie utilisee (mg/dL)", digits=(6, 1),
                                  readonly=True, copy=False)
    risque_imc = fields.Float(string="IMC utilise", digits=(5, 1), readonly=True, copy=False)
    risque_age = fields.Integer(string="Age utilise", readonly=True, copy=False)

    # Le bouton n'est visible que si la demande contient une glycemie
    has_glycemie = fields.Boolean(string="Contient une glycemie", compute='_compute_has_glycemie')

    @api.depends('resultat_ids.analyse_id.code')
    def _compute_has_glycemie(self):
        for rec in self:
            rec.has_glycemie = bool(rec._get_resultat_glycemie())

    def _get_resultat_glycemie(self):
        """Retourne le resultat de glycemie (analyse de code 'GLY'), ou un recordset vide."""
        self.ensure_one()
        return self.resultat_ids.filtered(
            lambda r: (r.analyse_id.code or '').strip().upper() == 'GLY')[:1]

    @staticmethod
    def _niveau_depuis_pourcentage(pct):
        if pct < SEUIL_MODERE:
            return 'faible'
        if pct <= SEUIL_ELEVE:
            return 'modere'
        return 'eleve'

    def write(self, vals):
        """Si les resultats ou le patient changent, l'estimation precedente n'est plus valable :
        on l'efface pour eviter d'afficher (ou d'imprimer) un risque obsolete."""
        if ('resultat_ids' in vals or 'patient_id' in vals) and 'risque_diabete' not in vals:
            vals = dict(vals, risque_diabete=0.0, risque_niveau=False, risque_date=False,
                        risque_glucose=0.0, risque_imc=0.0, risque_age=0)
        return super().write(vals)

    def action_predire_risque(self):
        """Bouton 'Predire le risque de diabete' : couche 2 (ML)."""
        self.ensure_one()

        # 1. Glycemie (resultat de code GLY), convertie en mg/dL
        res_gly = self._get_resultat_glycemie()
        if not res_gly:
            raise UserError("Cette demande ne contient pas d'analyse de glycemie (code GLY).")
        if not res_gly.valeur:
            raise UserError("Saisissez d'abord la valeur de la glycemie avant de lancer la prediction.")
        unite = (res_gly.analyse_id.unite or '').replace(' ', '').lower()
        # Le dataset Pima est en mg/dL ; SysLab stocke la glycemie en g/L (x 100)
        glucose = res_gly.valeur if unite == 'mg/dl' else res_gly.valeur * 100.0

        # 2. Donnees du patient
        patient = self.patient_id
        manquants = []
        if not patient.imc:
            manquants.append("poids et taille (pour l'IMC)")
        if not patient.date_naissance:
            manquants.append("date de naissance (pour l'age)")
        if manquants:
            raise UserError("Donnees du patient incompletes : renseignez %s sur la fiche de %s."
                            % (" et ".join(manquants), patient.name))
        bmi, age = patient.imc, patient.age

        # 3. Prediction : vecteur dans l'ordre [Glucose, BMI, Age]
        model = _charger_modele()
        try:
            with warnings.catch_warnings():
                # Le modele a ete entraine sur un DataFrame : on ignore l'avertissement
                # "X does not have valid feature names" (l'ordre est garanti par FEATURES)
                warnings.simplefilter('ignore')
                proba = model.predict_proba([[glucose, bmi, age]])[0][1]
        except Exception as e:
            _logger.exception("Erreur lors de la prediction ML")
            raise UserError("La prediction a echoue : %s" % e)

        pct = round(float(proba) * 100.0, 1)
        self.write({
            'risque_diabete': pct,
            'risque_niveau': self._niveau_depuis_pourcentage(pct),
            'risque_date': fields.Datetime.now(),
            'risque_glucose': glucose,
            'risque_imc': bmi,
            'risque_age': age,
        })
        # Pas de valeur de retour : le formulaire se recharge et affiche la jauge
        return True
