"""
SysLab - Envoi du bulletin de resultats par email au biologiste.

La demande herite de mail.thread : le compositeur d'email d'Odoo
(mail.compose.message) peut ainsi poster le message sur la demande, et chaque
envoi reste trace dans l'historique (chatter) en bas du formulaire.
"""
from odoo import api, fields, models


class DemandeMail(models.Model):
    _name = 'syslab.demande'
    _inherit = ['syslab.demande', 'mail.thread']

    # Destinataire par defaut, utilise par le modele d'email (champ calcule non stocke)
    email_biologiste = fields.Char(string="Email du biologiste",
                                   compute='_compute_email_biologiste')

    @api.depends_context('company', 'uid')
    def _compute_email_biologiste(self):
        email = self.env.company.syslab_email_biologiste or self.env.user.email or ''
        for rec in self:
            rec.email_biologiste = email

    def action_envoyer_bulletin(self):
        """Ouvre le compositeur d'email pre-rempli : modele 'Bulletin de resultats',
        PDF du bulletin en piece jointe, destinataire = biologiste (modifiable)."""
        self.ensure_one()
        template = self.env.ref('syslab.mail_template_bulletin', raise_if_not_found=False)
        ctx = {
            'default_model': 'syslab.demande',
            'default_res_ids': self.ids,
            'default_template_id': template.id if template else False,
            'default_composition_mode': 'comment',
            'force_email': True,
            # L'expediteur (email de la societe) peut etre la MEME adresse que le
            # biologiste : Odoo considere alors le destinataire comme l'auteur du
            # message et, par defaut, ne lui envoie rien. On force donc l'envoi.
            'mail_notify_author': True,
        }
        return {
            'type': 'ir.actions.act_window',
            'name': "Envoyer le bulletin par email",
            'res_model': 'mail.compose.message',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': ctx,
        }
