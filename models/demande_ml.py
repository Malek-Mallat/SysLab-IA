"""
SysLab - COUCHE 2 : estimation du risque de diabete par Machine Learning.

    Couche 1 (resultat.py) : regles -> interprete CHAQUE resultat (bas / normal / eleve).
    Couche 2 (ce fichier)  : modele ML -> estime un risque GLOBAL a partir de
                             plusieurs donnees combinees.

Le modele est entraine HORS d'Odoo par ml/train_model_nhanes.py sur NHANES 2017-2018
(CDC, adultes de 20 ans et plus, hommes et femmes), puis sauvegarde avec joblib dans
ml/diabetes_model_nhanes.pkl sous la forme :
    {"models": {"base":  {"model", "features": [Glucose, BMI, Age, Sexe], "metrics"},
                "hba1c": {"model", "features": [Glucose, HbA1c, BMI, Age, Sexe], "metrics"}},
     "dataset": ..., "label": ..., "sklearn_version": ...}

Le modele "hba1c" est utilise si la demande contient une HbA1c (code HBA1C),
sinon le modele "base".

Ethique : le resultat est une AIDE a la decision, jamais un diagnostic.
Il doit etre valide par un professionnel de sante.
"""
import logging
import os
import warnings

from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Chemin du modele : <module>/ml/diabetes_model_nhanes.pkl
MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          'ml', 'diabetes_model_nhanes.pkl')

# Variables que SysLab sait fournir au modele
FEATURES_CONNUES = {'Glucose', 'HbA1c', 'BMI', 'Age', 'Sexe'}

# Le modele a ete entraine sur des adultes de 20 ans et plus (NHANES plafonne l'age a 80)
AGE_MIN, AGE_MAX_DATASET = 20, 80

# Seuils du niveau de risque (en %)
SEUIL_MODERE = 30.0
SEUIL_ELEVE = 60.0

# Cache memoire : le .pkl n'est lu qu'une fois (recharge si le fichier change)
_MODEL_CACHE = {'mtime': None, 'data': None}

MSG_INSTALL = (
    "Les librairies de Machine Learning ne sont pas installees dans le Python d'Odoo.\n\n"
    "Ouvrez PowerShell en administrateur et executez :\n"
    "& \"C:\\Program Files\\Odoo 17.0.20260930\\python\\python.exe\" -s -m pip install "
    "scikit-learn==1.8.0 joblib\n\n"
    "(l'option -s force l'installation dans le Python d'Odoo, et non dans le profil "
    "utilisateur, invisible pour le service)\n\n"
    "puis redemarrez le service Odoo.\n(Detail technique : %s)"
)


def _charger_modeles():
    """Charge ml/diabetes_model_nhanes.pkl (avec cache) et verifie son format.

    Leve UserError avec un message clair si les librairies ou le fichier manquent.
    """
    try:
        import joblib  # noqa: F401 - import local : le module Odoo reste installable sans joblib
    except ImportError as e:
        raise UserError(MSG_INSTALL % e)

    if not os.path.isfile(MODEL_PATH):
        raise UserError(
            "Fichier du modele introuvable :\n%s\n\n"
            "Lancez d'abord l'entrainement : python ml/train_model_nhanes.py" % MODEL_PATH)

    mtime = os.path.getmtime(MODEL_PATH)
    if _MODEL_CACHE['data'] is not None and _MODEL_CACHE['mtime'] == mtime:
        return _MODEL_CACHE['data']

    try:
        data = joblib.load(MODEL_PATH)
    except ImportError as e:
        # joblib present mais scikit-learn absent : le depicklage echoue
        raise UserError(MSG_INSTALL % e)
    except Exception as e:
        _logger.exception("Erreur au chargement du modele ML")
        raise UserError("Impossible de charger le modele ML (%s).\n"
                        "Verifiez que scikit-learn est en version 1.8.0." % e)

    modeles = data.get('models') if isinstance(data, dict) else None
    if not modeles or 'base' not in modeles:
        raise UserError("Format du fichier modele inattendu : attendu "
                        "{'models': {'base': {...}, 'hba1c': {...}}}. "
                        "Relancez ml/train_model_nhanes.py.")
    for nom, m in modeles.items():
        inconnues = set(m.get('features', [])) - FEATURES_CONNUES
        if 'model' not in m or not m.get('features') or inconnues:
            raise UserError("Modele '%s' invalide : variables %s non fournies par SysLab."
                            % (nom, sorted(inconnues)))

    _MODEL_CACHE.update(mtime=mtime, data=data)
    _logger.info("Modeles ML charges depuis %s : %s", MODEL_PATH, list(modeles))
    return data


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
    risque_modele = fields.Char(string="Modele utilise", readonly=True, copy=False)

    # ---------- Tracabilite : donnees reellement envoyees au modele ----------
    risque_glucose = fields.Float(string="Glycemie utilisee (mg/dL)", digits=(6, 1),
                                  readonly=True, copy=False)
    risque_hba1c = fields.Float(string="HbA1c utilisee (%)", digits=(4, 1),
                                readonly=True, copy=False)
    risque_imc = fields.Float(string="IMC utilise", digits=(5, 1), readonly=True, copy=False)
    risque_age = fields.Integer(string="Age utilise", readonly=True, copy=False)
    risque_sexe = fields.Selection([('M', 'Homme'), ('F', 'Femme')], string="Sexe utilise",
                                   readonly=True, copy=False)

    # Le bouton n'est visible que si la demande contient une glycemie
    has_glycemie = fields.Boolean(string="Contient une glycemie", compute='_compute_has_glycemie')

    @api.depends('resultat_ids.analyse_id.code')
    def _compute_has_glycemie(self):
        for rec in self:
            rec.has_glycemie = bool(rec._get_resultat_par_code('GLY'))

    def _get_resultat_par_code(self, code):
        """Retourne le resultat de l'analyse de code donne (ex. 'GLY'), ou un recordset vide."""
        self.ensure_one()
        return self.resultat_ids.filtered(
            lambda r: (r.analyse_id.code or '').strip().upper() == code)[:1]

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
                        risque_modele=False, risque_glucose=0.0, risque_hba1c=0.0,
                        risque_imc=0.0, risque_age=0, risque_sexe=False)
        return super().write(vals)

    # ------------------------------------------------------------------
    # Preparation des donnees
    # ------------------------------------------------------------------
    def _lire_glycemie_mg_dl(self):
        """Glycemie (code GLY) convertie en mg/dL, unite du dataset."""
        res = self._get_resultat_par_code('GLY')
        if not res:
            raise UserError("Cette demande ne contient pas d'analyse de glycemie (code GLY).")
        if not res.valeur:
            raise UserError("Saisissez d'abord la valeur de la glycemie avant de lancer la prediction.")
        unite = (res.analyse_id.unite or '').replace(' ', '').lower()
        if unite == 'mg/dl':
            glucose = res.valeur
        elif unite == 'mmol/l':
            glucose = res.valeur * 18.016
        else:  # g/L (unite SysLab par defaut)
            glucose = res.valeur * 100.0
        if not 20 <= glucose <= 700:
            raise UserError("Glycemie de %.0f mg/dL hors des valeurs plausibles : "
                            "verifiez la valeur saisie et son unite (%s)."
                            % (glucose, res.analyse_id.unite or '?'))
        return glucose

    def _lire_hba1c_pct(self):
        """HbA1c (code HBA1C) en %, ou None si l'analyse n'est pas dans la demande."""
        res = self._get_resultat_par_code('HBA1C')
        if not res or not res.valeur:
            return None
        unite = (res.analyse_id.unite or '').replace(' ', '').lower()
        hba1c = res.valeur / 10.929 + 2.15 if unite == 'mmol/mol' else res.valeur  # IFCC -> NGSP
        if not 3 <= hba1c <= 20:
            raise UserError("HbA1c de %.1f %% hors des valeurs plausibles : "
                            "verifiez la valeur saisie." % hba1c)
        return hba1c

    def _lire_donnees_patient(self):
        """IMC, age et sexe du patient, avec messages clairs si une donnee manque."""
        patient = self.patient_id
        manquants = []
        if not patient.imc:
            manquants.append("poids et taille (pour l'IMC)")
        if not patient.date_naissance:
            manquants.append("date de naissance (pour l'age)")
        if not patient.sexe:
            manquants.append("sexe")
        if manquants:
            raise UserError("Donnees du patient incompletes : renseignez %s sur la fiche de %s."
                            % (", ".join(manquants), patient.name))
        if patient.age < AGE_MIN:
            raise UserError(
                "Le modele a ete entraine sur des adultes de %d ans et plus : il ne peut pas "
                "estimer le risque pour %s (%d ans). Interpretez les resultats sans l'IA."
                % (AGE_MIN, patient.name, patient.age))
        return patient.imc, patient.age, patient.sexe

    # ------------------------------------------------------------------
    # Bouton
    # ------------------------------------------------------------------
    def action_predire_risque(self):
        """Bouton 'Predire le risque de diabete' : couche 2 (ML)."""
        self.ensure_one()
        glucose = self._lire_glycemie_mg_dl()
        hba1c = self._lire_hba1c_pct()
        bmi, age, sexe = self._lire_donnees_patient()

        data = _charger_modeles()
        modeles = data['models']
        nom = 'hba1c' if hba1c is not None and 'hba1c' in modeles else 'base'
        modele = modeles[nom]

        # Vecteur construit dans l'ordre exact des variables enregistre dans le .pkl
        valeurs = {
            'Glucose': glucose,
            'HbA1c': hba1c,
            'BMI': bmi,
            'Age': min(age, AGE_MAX_DATASET),  # NHANES plafonne l'age a 80 ans
            'Sexe': 1 if sexe == 'M' else 0,   # 1 = homme, 0 = femme (comme a l'entrainement)
        }
        vecteur = [[valeurs[f] for f in modele['features']]]
        try:
            with warnings.catch_warnings():
                # Le modele a ete entraine sur un DataFrame : on ignore l'avertissement
                # "X does not have valid feature names" (l'ordre est garanti ci-dessus)
                warnings.simplefilter('ignore')
                proba = modele['model'].predict_proba(vecteur)[0][1]
        except Exception as e:
            _logger.exception("Erreur lors de la prediction ML")
            raise UserError("La prediction a echoue : %s" % e)

        auc = (modele.get('metrics') or {}).get('auc')
        libelle = "NHANES 2017-2018 - %s%s" % (
            ", ".join(modele['features']).replace('Glucose', 'glycemie').replace('BMI', 'IMC')
            .replace('Age', 'age').replace('Sexe', 'sexe'),
            " (AUC %.2f)" % auc if auc else "")

        pct = round(float(proba) * 100.0, 1)
        self.write({
            'risque_diabete': pct,
            'risque_niveau': self._niveau_depuis_pourcentage(pct),
            'risque_date': fields.Datetime.now(),
            'risque_modele': libelle,
            'risque_glucose': glucose,
            'risque_hba1c': hba1c or 0.0,
            'risque_imc': bmi,
            'risque_age': age,
            'risque_sexe': sexe,
        })
        # Pas de valeur de retour : le formulaire se recharge et affiche la jauge
        return True
