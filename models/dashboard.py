from odoo import models, fields, api


class SyslabDashboard(models.AbstractModel):
    """Fournit les indicateurs (KPI) du tableau de bord SysLab.

    Modele abstrait : aucune table en base, il sert uniquement a regrouper
    la logique de calcul appelee par le composant JavaScript (OWL) du tableau de bord.
    """
    _name = 'syslab.dashboard'
    _description = "Tableau de bord SysLab"

    @staticmethod
    def _pct(part, total):
        """Pourcentage arrondi (0 si total nul)."""
        return round(100.0 * part / total) if total else 0

    @api.model
    def get_data(self):
        Demande = self.env['syslab.demande']
        Resultat = self.env['syslab.resultat']
        Patient = self.env['syslab.patient']
        Medecin = self.env['syslab.medecin']

        # ---------- KPI principaux ----------
        nb_demandes = Demande.search_count([])
        nb_resultats_saisis = Resultat.search_count([('interpretation', '!=', 'nd')])
        nb_anormaux = Resultat.search_count([('interpretation', 'in', ('bas', 'eleve'))])

        today = fields.Date.context_today(self)
        debut_mois = today.replace(day=1)
        nb_demandes_mois = Demande.search_count([('date_demande', '>=', debut_mois)])

        # Chiffre d'affaires : demandes validees ou facturees
        ca = sum(Demande.search([('state', 'in', ('valide', 'facture'))]).mapped('prix_total'))
        nb_a_facturer = Demande.search_count([('state', '=', 'valide'), ('facture_id', '=', False)])

        # ---------- Demandes par statut ----------
        compte_statut = dict(Demande._read_group([], ['state'], ['__count']))
        par_statut = [{
            'key': key,
            'label': label,
            'count': compte_statut.get(key, 0),
            'pct': self._pct(compte_statut.get(key, 0), nb_demandes),
        } for key, label in Demande._fields['state'].selection]

        # ---------- Interpretation des resultats (couche 1) ----------
        nb_resultats = Resultat.search_count([])
        compte_interp = dict(Resultat._read_group([], ['interpretation'], ['__count']))
        par_interpretation = [{
            'key': key,
            'label': label,
            'count': compte_interp.get(key, 0),
            'pct': self._pct(compte_interp.get(key, 0), nb_resultats),
        } for key, label in Resultat._fields['interpretation'].selection]

        # ---------- Repartition par famille d'analyse ----------
        compte_famille = dict(Resultat._read_group([], ['famille'], ['__count']))
        par_famille = [{
            'key': key,
            'label': label,
            'count': compte_famille.get(key, 0),
            'pct': self._pct(compte_famille.get(key, 0), nb_resultats),
        } for key, label in self.env['syslab.analyse']._fields['famille'].selection]

        # ---------- Top 5 des analyses les plus demandees ----------
        top = Resultat._read_group([], ['analyse_id'], ['__count'], order='__count desc', limit=5)
        top_analyses = [{
            'id': analyse.id,
            'name': analyse.display_name,
            'count': count,
            'pct': self._pct(count, nb_resultats),
        } for analyse, count in top]

        # ---------- 5 dernieres demandes ----------
        labels_statut = dict(Demande._fields['state'].selection)
        dernieres = [{
            'id': d.id,
            'name': d.name,
            'patient': d.patient_id.name or '',
            'date': d.date_demande.strftime('%d/%m/%Y') if d.date_demande else '',
            'state': d.state,
            'state_label': labels_statut.get(d.state, ''),
            'nb_anomalies': d.nb_anomalies,
        } for d in Demande.search([], limit=5)]  # _order : date desc

        return {
            'kpi': {
                'nb_patients': Patient.search_count([]),
                'nb_medecins': Medecin.search_count([]),
                'nb_demandes': nb_demandes,
                'nb_demandes_mois': nb_demandes_mois,
                'nb_resultats': nb_resultats_saisis,
                'nb_anormaux': nb_anormaux,
                'taux_anomalie': self._pct(nb_anormaux, nb_resultats_saisis),
                'nb_a_facturer': nb_a_facturer,
                # Format francais : espace pour les milliers, virgule decimale
                'ca': '{:,.3f}'.format(ca).replace(',', ' ').replace('.', ','),
            },
            'par_statut': par_statut,
            'par_interpretation': par_interpretation,
            'par_famille': par_famille,
            'top_analyses': top_analyses,
            'dernieres': dernieres,
            'debut_mois': fields.Date.to_string(debut_mois),
        }
