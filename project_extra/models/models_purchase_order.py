# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class purchaseOrderInherit(models.Model):
    _inherit = 'purchase.order'

    lead_id = fields.Many2one('crm.lead', string='Oportunidad')
    type_purchase = fields.Selection(selection=[('bases','Bases de Licitación'), ('ins', 'Insumos'), ('esp', 'Trabajos especiales')],
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

    def _check_bases_payment_status(self):
        # Verifica si las facturas de bases de licitación están pagadas y actualiza el CRM
        for order in self:
            if order.type_purchase == 'bases' and order.lead_id:
                # Buscar facturas asociadas a esta orden de compra
                invoices = order.invoice_ids.filtered(lambda inv: inv.state == 'posted')
                if invoices:
                    # Verificar si todas las facturas están pagadas
                    all_paid = all(inv.payment_state == 'paid' for inv in invoices)
                    if all_paid and not order.lead_id.bases_pagado:
                        order.lead_id.sudo().write({'bases_pagado': True})


class AccountMoveInherit(models.Model):
    _inherit = 'account.move'

    def write(self, vals):
        res = super(AccountMoveInherit, self).write(vals)
        # Si cambió el estado de pago, verificar si hay que actualizar el CRM
        if 'payment_state' in vals:
            for move in self:
                if move.move_type == 'in_invoice' and move.payment_state == 'paid':
                    # Buscar órdenes de compra relacionadas
                    purchase_orders = self.env['purchase.order'].search([('invoice_ids','in',move.id), ('type_purchase','=','bases'), ('lead_id','!=',False)])
                    for po in purchase_orders:
                        po._check_bases_payment_status()
        return res


class purchaseOrderLineInherit(models.Model):
    _inherit = 'purchase.order.line'

    active = fields.Boolean(string='Activo', default=True)


class purchaseRequisitionInherit(models.Model):
    _inherit = 'purchase.requisition'

    description_contract = fields.Char(string='Descripción')
    doctos_delivered = fields.Char(string='Documentos a entregar')
    retencion = fields.Float(string='% de retención')
    schedule = fields.Char(string='Horario de entrega')
    warranty_period = fields.Char(string='Periodo de garantía')
    signature_date = fields.Date(string='Fecha de firma del contrato')
