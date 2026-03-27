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
    empresa_solicitante = fields.Many2one('res.partner', string='Empresa solicitante', compute='_compute_empresa_solicitante', store=False)
    bitacora_ids = fields.One2many('purchase.order.bitacora', 'order_id', string='Bitácora')

    STATES_LABELS = {'draft': 'Solicitud de cotización', 'sent': 'Solicitud de cotización enviada', 'purchase': 'Orden de compra', 'done': 'Bloqueado',
        'cancel': 'Cancelado'}

    @api.depends('lead_id', 'lead_id.empresa_concursante_id')
    def _compute_empresa_solicitante(self):
        for order in self:
            if order.lead_id and order.lead_id.empresa_concursante_id:
                order.empresa_solicitante = order.lead_id.empresa_concursante_id.partner_id
            else:
                order.empresa_solicitante = False

    def get_empresa_reporte(self):
        self.ensure_one()
        if self.type_purchase == 'bases' and self.lead_id and self.lead_id.empresa_concursante_id:
            return self.lead_id.empresa_concursante_id
        return self.company_id

    def action_print_order(self):
        self.ensure_one()
        return self.env.ref('purchase.action_report_purchase_order').report_action(self)

    def action_comparativo(self):
        if not self.lead_id:
            raise UserError(_('Esta solicitud no tiene una oportunidad vinculada.'))
        cotizaciones = self.env['purchase.order'].search([('lead_id', '=', self.lead_id.id), ('type_purchase', '=', 'ins'), ('state', '=', 'sent'),
            ('mail_reception_confirmed', '=', True)])
        if not cotizaciones:
            raise UserError(_('No se puede generar el Cuadro Comparativo.\n\n'
                'No existen cotizaciones que cumplan con todos los requisitos:\n'
                '  • Tipo de movimiento: Insumos\n'
                '  • Estado: Solicitud de cotización enviada\n'
                '  • Confirmación de recepción: marcada'))

        url = '/web/binary/purchase_cuadro_comparativo?&lead=%s' % self.lead_id.id
        return {'type': 'ir.actions.act_url', 'url': url, 'target': 'new'}


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
                invoices = order.invoice_ids.filtered(lambda inv: inv.state == 'posted')
                if invoices:
                    all_paid = all(inv.payment_state == 'paid' for inv in invoices)
                    if all_paid and not order.lead_id.bases_pagado:
                        order.lead_id.sudo().write({'bases_pagado': True})

    def write(self, vals):
        old_states = {order.id: order.state for order in self} if 'state' in vals else {}
        res = super().write(vals)
        if 'state' in vals:
            for order in self:
                old_state = old_states[order.id]
                if old_state != order.state:
                    self.env['purchase.order.bitacora'].create({'order_id':order.id, 'fecha':fields.Datetime.now(), 'usuario':self.env.user.name, 
                        'etapa_anterior':order.STATES_LABELS.get(old_state, old_state), 'etapa_nueva':order.STATES_LABELS.get(order.state, order.state)})
        return res


class AccountMoveInherit(models.Model):
    _inherit = 'account.move'

    def write(self, vals):
        res = super(AccountMoveInherit, self).write(vals)
        if 'payment_state' in vals:
            for move in self:
                if move.move_type == 'in_invoice' and move.payment_state == 'paid':
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


class PurchaseAsignacion(models.Model):
    _name = 'purchase.asignacion'
    _description = 'Asignación de solicitudes de cotización'
    _order = 'fecha_asignacion desc'

    nombre_id = fields.Many2one('hr.employee', string='Nombre',
        domain="[('department_id.name', 'ilike', 'compras')]")
    referencia_id = fields.Many2one('purchase.order', string='Referencia',
        domain="[('lead_id', '!=', False)]")
    fecha_asignacion = fields.Date(string='Fecha de asignación', default=fields.Date.context_today)
    fecha_limite = fields.Datetime(string='Fecha límite', related='referencia_id.date_order', readonly=True)
    observaciones = fields.Char(string='Observaciones')


class PurchaseOrderBitacora(models.Model):
    _name = 'purchase.order.bitacora'
    _description = 'Bitácora de solicitudes de cotización'
    _order = 'fecha asc'

    order_id = fields.Many2one('purchase.order', string='Solicitud', required=True, ondelete='cascade')
    fecha = fields.Datetime(string='Fecha', default=fields.Datetime.now, readonly=True)
    usuario = fields.Char(string='Usuario', readonly=True)
    etapa_anterior = fields.Char(string='Etapa anterior', readonly=True)
    etapa_nueva = fields.Char(string='Etapa nueva', readonly=True)
    motivo_id = fields.Many2one('crm.revert.reason', string='Motivo', domain="[('tipo', '=', 'av')]")
    observaciones = fields.Char(string='Observaciones')
