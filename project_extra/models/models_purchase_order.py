# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class purchaseOrderInherit(models.Model):
    _inherit = 'purchase.order'

    lead_id = fields.Many2one('crm.lead', string='Oportunidad')
    type_purchase = fields.Selection(selection=[('bases','Bases de Licitación'), ('ins', 'Insumos')],
            string='Tipo de movimiento')

    def action_comparativo(self):
        url = '/web/binary/purchase_cuadro_comparativo?&lead=%s'% (self.lead_id.id)
        return {'type': 'ir.actions.act_url', 'url': url, 'target': 'new', }

    def generate_purchase_order(self):
        rfq_to_merge = self.filtered(lambda r: r.state in ['sent'] and r.type_purchase == 'ins')
        if len(rfq_to_merge.lead_id) > 1:
            raise UserError(_('Existen diferentes Oportunidades en la acción, favor de revisar.'))
        if not rfq_to_merge.lead_id:
            raise UserError(_('Las ordenes de compra seleccionadas no cumplen con los requisitos para esta acción, favor de revisar.'))

        faltantes = self.search([('id','not in',rfq_to_merge.ids), ('lead_id','=',rfq_to_merge.lead_id.id), ('state','=','sent'), ('type_purchase','=','ins')])
        if faltantes:
            raise UserError(_('Faltan ordenes de compra relacionadas de seleccionar.'))

        if rfq_to_merge:
            action = {
                'name': _('Confirmar Ordenes - Tipo'),
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'purchase.confirm.order',
                'view_id': self.env.ref('project_extra.view_order_conf_type').id,
                'context': {'orders': rfq_to_merge.ids},
                'target': 'new'}
            return action


class purchaseOrderLineInherit(models.Model):
    _inherit = 'purchase.order.line'

    active = fields.Boolean(string='Activo', default=True, tracking=True)
