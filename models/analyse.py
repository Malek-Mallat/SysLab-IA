from odoo import models, fields


class Analyse(models.Model):
    _name = 'syslab.analyse'
    _description = "Catalogue des analyses"

    name = fields.Char(string="Nom de l'analyse", required=True)
    code = fields.Char(string="Code")
    famille = fields.Selection([
        ('biochimie', 'Biochimie'),
        ('hematologie', 'Hematologie'),
    ], string="Famille", required=True)
    unite = fields.Char(string="Unite", help="Ex: g/L, mg/L, g/dL")
    # group_operator=False : pas de somme (absurde) des bornes dans les vues groupees
    borne_min = fields.Float(string="Borne min (normale)", digits=(10, 2), group_operator=False)
    borne_max = fields.Float(string="Borne max (normale)", digits=(10, 2), group_operator=False)
    prix = fields.Float(string="Prix (TND)", digits=(10, 3))
    actif = fields.Boolean(string="Actif", default=True)
