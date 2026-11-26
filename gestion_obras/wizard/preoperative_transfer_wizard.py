# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class TcPreoperativeTransferWizard(models.TransientModel):
    _name = 'presupuesto.preoperativo.transfer.wizard'
    _description = 'Asistente de Traslado y Compensación Preoperativa'

    preoperative_id = fields.Many2one('gestion.obra.presupuesto.preoperativo', string='Presupuesto Preoperativo Origen', required=True)
    target_analytic_id = fields.Many2one('account.analytic.account', string='Analítica Destino', required=True)
    transfer_date = fields.Date(string='Fecha de Traslado y Compensación', default=fields.Date.today, required=True)
    user_id = fields.Many2one('res.users', string='Usuario que Autoriza', default=lambda self: self.env.user, required=True)    
    transfer_line_ids = fields.One2many('presupuesto.preoperativo.transfer.line', 'wizard_id', string='Matriz de Mapeo y Conciliación')
    total_preoperative_incurred = fields.Monetary(string='Total Incurrido a Descontar', compute='_compute_total_incurred')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    notes = fields.Text(string='Observaciones / Justificación Técnica')

    @api.onchange('preoperative_id')
    def _onchange_preoperative_id(self):
        if self.preoperative_id:
            lines = []
            for line in self.preoperative_id.line_ids:
                lines.append((0, 0, {
                    'preoperative_line_id': line.id,
                    'amount_incurred_to_deduct': line.amount_incurred or line.amount_committed,
                    'reconciliation_status': 'pending'}))
            self.transfer_line_ids = [(5, 0, 0)] + lines

    @api.depends('transfer_line_ids.amount_incurred_to_deduct')
    def _compute_total_incurred(self):
        for wiz in self:
            wiz.total_preoperative_incurred = sum(wiz.transfer_line_ids.mapped('amount_incurred_to_deduct'))

    def action_execute_transfer(self):
        self.ensure_one()
        if not self.transfer_line_ids:
            raise UserError(_("Debe mapear al menos una partida para procesar el traslado."))
        
        for t_line in self.transfer_line_ids:
            t_line.preoperative_line_id.write({'is_transferred': True})
            t_line.write({'reconciliation_status': 'reconciled'})
            
        self.preoperative_id.write({'state': 'reconciled', 'analytic_id': self.target_analytic_id.id})
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Traslado Exitoso"),
                'message': _("Se ha completado el traslado y compensación del Presupuesto Preoperativo a Kontrol."),
                'sticky': False,}}


class TcPreoperativeTransferLine(models.TransientModel):
    _name = 'presupuesto.preoperativo.transfer.line'
    _description = 'Línea de Mapeo y Conciliación de Traslado'

    wizard_id = fields.Many2one('presupuesto.preoperativo.transfer.wizard', string='Asistente de Traslado', ondelete='cascade')
    preoperative_line_id = fields.Many2one('gestion.obra.presupuesto.preoperativo.line', string='Partida Preoperativa Origen', required=True)
    target_analytic_id = fields.Many2one('account.analytic.account', string='Cuenta Analítica Definitiva', required=True)
    amount_incurred_to_deduct = fields.Monetary(string='Monto Incurrido a Descontar en Kontrol', required=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    reconciliation_status = fields.Selection([('pending', 'Pendiente'), ('mapped', 'Mapeado'), ('reconciled', 'Conciliado')], 
        string='Estatus de Compensación', default='pending')