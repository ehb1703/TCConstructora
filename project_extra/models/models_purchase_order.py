# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

class purchaseOrderInherit(models.Model):
    _inherit = 'purchase.order'

    lead_id = fields.Many2one('crm.lead', string='Oportunidad')
    type_purchase = fields.Selection(selection=[('bases','Bases de Licitación'), ('ins', 'Insumos')],
            string='Tipo de movimiento')

    def action_comparativo(self):
        url = '/web/binary/purchase_cuadro_comparativo?&lead=%s'% (self.lead_id.id)
        return {'type': 'ir.actions.act_url', 'url': url, 'target': 'new', }
