from odoo import models, fields, api
from odoo.exceptions import UserError


class Demande(models.Model):
    _name = 'syslab.demande'
    _description = "Demande d'analyses"
    _order = 'date_demande desc, id desc'

    name = fields.Char(string="Reference", required=True, copy=False,
                       readonly=True, default="Nouveau")
    patient_id = fields.Many2one('syslab.patient', string="Patient", required=True)
    medecin_id = fields.Many2one('syslab.medecin', string="Medecin prescripteur")
    date_demande = fields.Date(string="Date de la demande", default=fields.Date.context_today)
    state = fields.Selection([
        ('brouillon', 'Brouillon'),
        ('en_cours', 'En cours'),
        ('valide', 'Valide'),
        ('facture', 'Facture'),
    ], string="Statut", default='brouillon',
        # Affiche toutes les colonnes du Kanban, meme vides
        group_expand='_group_expand_states')
    resultat_ids = fields.One2many('syslab.resultat', 'demande_id', string="Resultats")
    prix_total = fields.Float(string="Total (TND)", compute='_compute_prix_total',
                              store=True, digits=(10, 3))
    notes = fields.Text(string="Notes")

    # Indicateurs (stockes pour pouvoir filtrer/grouper et alimenter Kanban + tableau de bord)
    nb_analyses = fields.Integer(string="Nb analyses", compute='_compute_indicateurs', store=True)
    nb_anomalies = fields.Integer(string="Nb anomalies", compute='_compute_indicateurs', store=True,
                                  help="Nombre de resultats interpretes Bas ou Eleve")
    # Synthese des resultats (barre de progression des colonnes Kanban)
    etat_resultats = fields.Selection([
        ('vide', 'A saisir'),
        ('normal', 'Tout normal'),
        ('anomalie', 'Anomalie(s)'),
    ], string="Synthese resultats", compute='_compute_indicateurs', store=True)

    # Facturation (module natif Odoo)
    facture_id = fields.Many2one('account.move', string="Facture", readonly=True, copy=False)
    has_facture = fields.Boolean(string="Facturee", compute='_compute_has_facture')

    @api.depends('facture_id')
    def _compute_has_facture(self):
        for rec in self:
            rec.has_facture = bool(rec.facture_id)

    @api.depends('resultat_ids', 'resultat_ids.interpretation')
    def _compute_indicateurs(self):
        for rec in self:
            rec.nb_analyses = len(rec.resultat_ids)
            rec.nb_anomalies = len(rec.resultat_ids.filtered(
                lambda r: r.interpretation in ('bas', 'eleve')))
            # Priorite : anomalie > resultats encore a saisir > tout normal
            if rec.nb_anomalies:
                rec.etat_resultats = 'anomalie'
            elif not rec.resultat_ids or 'nd' in rec.resultat_ids.mapped('interpretation'):
                rec.etat_resultats = 'vide'
            else:
                rec.etat_resultats = 'normal'

    @api.model
    def _group_expand_states(self, states, domain, order):
        """Retourne toutes les valeurs du statut pour afficher chaque colonne du Kanban."""
        return [key for key, _label in self._fields['state'].selection]

    @api.depends('resultat_ids.analyse_id')
    def _compute_prix_total(self):
        for rec in self:
            rec.prix_total = sum(rec.resultat_ids.mapped('analyse_id.prix'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nouveau') == 'Nouveau':
                vals['name'] = self.env['ir.sequence'].next_by_code('syslab.demande') or 'Nouveau'
        return super().create(vals_list)

    def action_en_cours(self):
        for rec in self:
            rec.state = 'en_cours'

    def action_valider(self):
        for rec in self:
            rec.state = 'valide'

    def action_brouillon(self):
        for rec in self:
            rec.state = 'brouillon'

    def action_creer_facture(self):
        """Genere une facture client (module natif account) depuis la demande."""
        self.ensure_one()
        if self.facture_id:
            raise UserError("Une facture existe deja pour cette demande.")
        if not self.resultat_ids:
            raise UserError("Ajoutez au moins une analyse avant de facturer.")

        # Reutiliser ou creer le contact (res.partner) lie au patient
        partner = self.patient_id.partner_id
        if not partner:
            partner = self.env['res.partner'].create({
                'name': self.patient_id.name,
                'phone': self.patient_id.telephone,
                'email': self.patient_id.email,
            })
            self.patient_id.partner_id = partner.id

        # Une ligne de facture par analyse
        lignes = []
        for r in self.resultat_ids:
            lignes.append((0, 0, {
                'name': r.analyse_id.name,
                'quantity': 1,
                'price_unit': r.analyse_id.prix,
            }))

        facture = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'invoice_origin': self.name,
            'invoice_line_ids': lignes,
        })

        self.facture_id = facture.id
        self.state = 'facture'

        return {
            'type': 'ir.actions.act_window',
            'name': 'Facture',
            'res_model': 'account.move',
            'res_id': facture.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_voir_facture(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Facture',
            'res_model': 'account.move',
            'res_id': self.facture_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
