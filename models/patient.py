from odoo import models, fields, api
from datetime import date


class Patient(models.Model):
    _name = 'syslab.patient'
    _description = "Patient"

    name = fields.Char(string="Nom complet", required=True)
    date_naissance = fields.Date(string="Date de naissance")
    age = fields.Integer(string="Age", compute='_compute_age', store=True)
    sexe = fields.Selection([
        ('M', 'Homme'),
        ('F', 'Femme'),
    ], string="Sexe")
    telephone = fields.Char(string="Telephone")
    email = fields.Char(string="Email")

    # Contact lie (res.partner) pour la facturation
    partner_id = fields.Many2one('res.partner', string="Contact lie", readonly=True, copy=False)

    # Donnees utiles pour la couche ML (ex. risque de diabete)
    poids = fields.Float(string="Poids (kg)", digits=(5, 1))
    taille = fields.Float(string="Taille (cm)", digits=(5, 1))
    imc = fields.Float(string="IMC", compute='_compute_imc', store=True, digits=(5, 1))
    # Categorie de corpulence (seuils OMS), affichee en badge colore
    imc_categorie = fields.Selection([
        ('nd', 'Non renseigne'),
        ('maigreur', 'Maigreur'),
        ('normal', 'Corpulence normale'),
        ('surpoids', 'Surpoids'),
        ('obesite', 'Obesite'),
    ], string="Corpulence", compute='_compute_imc', store=True)

    # Historique des demandes du patient (alimente le smart button)
    demande_ids = fields.One2many('syslab.demande', 'patient_id', string="Demandes")
    demande_count = fields.Integer(string="Nombre de demandes", compute='_compute_demande_count')

    @api.depends('demande_ids')
    def _compute_demande_count(self):
        for rec in self:
            rec.demande_count = len(rec.demande_ids)

    def action_voir_demandes(self):
        """Smart button : ouvre la liste des demandes de ce patient."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': "Demandes de %s" % self.name,
            'res_model': 'syslab.demande',
            'view_mode': 'tree,form',
            'domain': [('patient_id', '=', self.id)],
            # Pre-remplit le patient si on cree une demande depuis cette liste
            'context': {'default_patient_id': self.id},
        }

    @api.depends('date_naissance')
    def _compute_age(self):
        for rec in self:
            if rec.date_naissance:
                today = date.today()
                rec.age = today.year - rec.date_naissance.year - (
                    (today.month, today.day) < (rec.date_naissance.month, rec.date_naissance.day)
                )
            else:
                rec.age = 0

    @api.depends('poids', 'taille')
    def _compute_imc(self):
        for rec in self:
            if rec.poids and rec.taille:
                m = rec.taille / 100.0
                rec.imc = rec.poids / (m * m)
            else:
                rec.imc = 0.0
            # Classification OMS de l'IMC
            if not rec.imc:
                rec.imc_categorie = 'nd'
            elif rec.imc < 18.5:
                rec.imc_categorie = 'maigreur'
            elif rec.imc < 25:
                rec.imc_categorie = 'normal'
            elif rec.imc < 30:
                rec.imc_categorie = 'surpoids'
            else:
                rec.imc_categorie = 'obesite'
