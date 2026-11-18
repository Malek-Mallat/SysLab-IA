from odoo import models, fields, api


class Medecin(models.Model):
    _name = 'syslab.medecin'
    _description = "Medecin prescripteur"

    name = fields.Char(string="Nom du medecin", required=True)
    specialite = fields.Char(string="Specialite")
    telephone = fields.Char(string="Telephone")
    email = fields.Char(string="Email")

    # Demandes prescrites (alimente le smart button)
    demande_ids = fields.One2many('syslab.demande', 'medecin_id', string="Demandes prescrites")
    demande_count = fields.Integer(string="Nombre de demandes", compute='_compute_demande_count')

    @api.depends('demande_ids')
    def _compute_demande_count(self):
        for rec in self:
            rec.demande_count = len(rec.demande_ids)

    def action_voir_demandes(self):
        """Smart button : ouvre la liste des demandes prescrites par ce medecin."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': "Demandes du %s" % self.name,
            'res_model': 'syslab.demande',
            'view_mode': 'tree,form',
            'domain': [('medecin_id', '=', self.id)],
            'context': {'default_medecin_id': self.id},
        }
