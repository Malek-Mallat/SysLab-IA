from odoo import models, fields, api


class Resultat(models.Model):
    _name = 'syslab.resultat'
    _description = "Resultat d'analyse"

    demande_id = fields.Many2one('syslab.demande', string="Demande",
                                 required=True, ondelete='cascade')
    analyse_id = fields.Many2one('syslab.analyse', string="Analyse", required=True)
    # group_operator='avg' : dans le pivot/graph, on affiche la MOYENNE des valeurs (une somme n'a pas de sens)
    valeur = fields.Float(string="Valeur mesuree", digits=(10, 2), group_operator='avg')

    # Champs recopies (stockes) pour pouvoir filtrer / grouper dans les vues graph et pivot
    famille = fields.Selection(related='analyse_id.famille', string="Famille", store=True)
    date_demande = fields.Date(related='demande_id.date_demande', string="Date de la demande", store=True)
    patient_id = fields.Many2one(related='demande_id.patient_id', string="Patient", store=True)
    medecin_id = fields.Many2one(related='demande_id.medecin_id', string="Medecin", store=True)

    # Champs rattaches a l'analyse (normes, unite) pour l'affichage et les regles
    unite = fields.Char(related='analyse_id.unite', string="Unite", readonly=True)
    borne_min = fields.Float(related='analyse_id.borne_min', string="Min", readonly=True)
    borne_max = fields.Float(related='analyse_id.borne_max', string="Max", readonly=True)

    # Couche 1 - Interpretation par regles
    interpretation = fields.Selection([
        ('nd', 'Non defini'),
        ('bas', 'Bas'),
        ('normal', 'Normal'),
        ('eleve', 'Eleve'),
    ], string="Interpretation", compute='_compute_interpretation', store=True)
    commentaire = fields.Char(string="Commentaire", compute='_compute_interpretation', store=True)

    @api.depends('valeur', 'analyse_id', 'analyse_id.borne_min', 'analyse_id.borne_max')
    def _compute_interpretation(self):
        for rec in self:
            if not rec.analyse_id or not rec.valeur:
                rec.interpretation = 'nd'
                rec.commentaire = ''
                continue
            vmin = rec.analyse_id.borne_min
            vmax = rec.analyse_id.borne_max
            nom = rec.analyse_id.name
            unite = rec.analyse_id.unite or ''
            if vmax and rec.valeur > vmax:
                rec.interpretation = 'eleve'
                rec.commentaire = "%s elevee (> %s %s), a confirmer." % (nom, vmax, unite)
            elif vmin and rec.valeur < vmin:
                rec.interpretation = 'bas'
                rec.commentaire = "%s basse (< %s %s), a confirmer." % (nom, vmin, unite)
            else:
                rec.interpretation = 'normal'
                rec.commentaire = "Valeur normale."
