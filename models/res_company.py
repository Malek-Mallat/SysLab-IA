from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Destinataire par defaut de l'email "Envoyer le bulletin par email".
    # Si vide, on utilise l'email de l'utilisateur connecte.
    syslab_email_biologiste = fields.Char(
        string="Email du biologiste",
        help="Adresse a laquelle les bulletins de resultats sont envoyes par defaut. "
             "Si vide, l'email de l'utilisateur connecte est utilise.")

    def _syslab_init_email_biologiste(self, email):
        """Appele par data/company_data.xml : renseigne l'email du biologiste
        uniquement s'il est vide (ne remplace jamais une valeur saisie)."""
        self.filtered(lambda c: not c.syslab_email_biologiste).write(
            {'syslab_email_biologiste': email})
        return True

    def _syslab_init_logo(self, logo_b64):
        """Appele par data/company_data.xml : pose le logo SysLab uniquement si la
        societe a encore le logo par defaut d'Odoo (ou aucun logo).
        Un logo televerse ensuite dans l'interface n'est donc jamais ecrase."""
        logo_defaut = self._get_logo()
        for company in self:
            if not company.logo or company.logo == logo_defaut:
                company.logo = logo_b64
        return True
