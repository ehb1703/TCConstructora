# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

class purchaseCRMLEAD(models.Model):
    _inherit = 'purchase.order'

    lead_id = fields.Many2one('crm.lead', string='Oportudidad')
    type_purchase = fields.Selection(selection=[('bases','Bases de Licitación'), ('ins', 'Insumos')],
            string='Tipo de movimiento')