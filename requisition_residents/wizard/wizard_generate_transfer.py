# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)

class SaleAdvanceInvoiceWizard(models.TransientModel):
    _name = 'requisition.transfer.wizard'
    _description = 'Wizard para realizar movimientos'

    raccount_id = fields.Many2one('requisition.bank.account', string='Cuenta bancaria', required=True)
    type_mov = fields.Selection(selection=[('dep','Depósito'), ('trans','Transferencia'), ('caja','Caja chica')],
        string='Tipo de Movimiento', default='dep')
    fecha = fields.Date(string='Fecha')
    authorize = fields.Char(string='Autorización')
    account_id = fields.Many2one('requisition.bank.account', string='Cuenta bancaria')
    amount = fields.Float(string='Importe')
    description = fields.Char(string='Descripción')
    employee_id = fields.Many2one('hr.employee', string='Empleado', 
        domain="[('state', '!=', 'baja'), ('finiquito', '=', False), ('job_id.name', 'ilike', 'RESIDENTE')]")
    tarjeta_facil = fields.Many2one('res.partner.bank', string='Tarjeta facil', related='employee_id.facil_tarjeta', store='True')

    def action_confirm(self):
        self.ensure_one()
        if self.amount == 0.0:
            raise ValidationError('Debe de capturar importe.')

        if self.type_mov in ['trans', 'caja'] and self.amount > self.raccount_id.balance:
            raise ValidationError('El importe a transferir es mayor al saldo actual.')

        if self.type_mov == 'caja' and not self.tarjeta_facil:
            raise ValidationError('El empleado no cuenta con la inforamción de la tarjeta a transferir, favor de actualizar.')

        raccount_lines = []
        if self.type_mov == 'dep':
            lines = {'fecha': self.fecha, 'debit': self.amount, 'credit': 0.0, 'concepto': 'Depósito a la cuenta. Autorización: ' + self.authorize, 
                'origen': 'Depósito', 'description': self.description}
            raccount_lines.append((0, 0, lines))
        elif self.type_mov == 'trans':
            account_lines = []
            lines = {'fecha': self.fecha, 'debit': 0.0, 'credit': self.amount, 'origen': 'Transferencia', 'description': self.description,
                'concepto': 'Transferencia a la cuenta ' + self.account_id.res_partner_bank.acc_number + '. Autorización: ' + self.authorize}
            trans = {'fecha': self.fecha, 'debit': self.amount, 'credit': 0.0, 'origen': 'Transferencia', 'description': self.description,
                'concepto': 'Transferencia de la cuenta ' + self.raccount_id.res_partner_bank.acc_number + '. Autorización: ' + self.authorize}
            raccount_lines.append((0, 0, lines))
            account_lines.append((0, 0, trans))
            self.account_id.write({'line_ids': account_lines})
        else:
            employee = self.env['requisition.petty.cash'].search([('employee_id','=',self.employee_id.id)])
            if not employee:
                employee = self.env['requisition.petty.cash'].create({'employee_id': self.employee_id.id})

            account_lines = []
            lines = {'fecha': self.fecha, 'debit': 0.0, 'credit': self.amount, 'origen': 'Caja Chica', 'description': self.description,
                'concepto': 'Fondo de caja chica ' + self.tarjeta_facil.acc_number + '. Autorización: ' + self.authorize}
            trans = {'fecha': self.fecha, 'debit': self.amount, 'credit': 0.0, 'origen': 'Caja chica', 'observaciones': self.description,
                'concepto': 'Fondo de caja chica ' + self.raccount_id.res_partner_bank.acc_number + ' a ' + self.tarjeta_facil.acc_number + 
                    'la cuenta . Autorización: ' + self.authorize}
            account_lines.append((0, 0, trans))
            raccount_lines.append((0, 0, lines))
            employee.write({'line_ids': account_lines})

        self.raccount_id.write({'line_ids': raccount_lines})       
