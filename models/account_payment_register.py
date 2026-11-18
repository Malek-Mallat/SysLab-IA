"""
SysLab - Reglement des factures en ESPECES uniquement.

Dans l'assistant "Enregistrer un paiement" (account.payment.register), Odoo propose
tous les journaux de type banque ou caisse. Le laboratoire n'encaisse qu'en especes :
on ne garde donc que les journaux de type 'cash' (journal "Especes"), qui devient
de fait le journal unique et par defaut. Methode de paiement : "Manuel" (pas de
carte, pas de virement).

Securite : si aucun journal especes n'existe pour la societe, on garde le
comportement standard d'Odoo pour ne jamais bloquer l'enregistrement d'un paiement.
"""
from odoo import api, models


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    @api.model
    def _get_batch_available_journals(self, batch_result):
        journals = super()._get_batch_available_journals(batch_result)
        journaux_especes = journals.filtered(lambda j: j.type == 'cash')
        return journaux_especes or journals
