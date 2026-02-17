# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)

class SaleAdvanceInvoiceWizard(models.TransientModel):
    _name = 'requisition.transfer.wizard'
    _description = 'Wizard para realizar movimientos'

    raccount_id = fields.Many2one('requisition.bank.account', string='Cuenta bancaria', required=True)
    type_mov = fields.Selection(selection=[('dep','Depósito'), ('trans','Transferencia')],
        string='Tipo de Movimiento', default='dep')
    fecha = fields.Date(string='Fecha')
    authorize = fields.Char(string='Autorización')
    account_id = fields.Many2one('requisition.bank.account', string='Cuenta bancaria')
    amount = fields.Float(string='Importe')
    description = fields.Char(string='Descripción')

    def action_confirm(self):
        self.ensure_one()
        if self.type_mov == 'trans' and self.amount > self.raccount_id.balance:
            raise ValidationError('El importe a transferir es mayor al saldo actual.')

        raccount_lines = []
        if self.type_mov == 'dep':
            lines = {'fecha': self.fecha, 'debit': self.amount, 'credit': 0.0, 'concepto': 'Depósito a la cuenta. Autorización: ' + self.authorize, 
                'origen': 'Depósito', 'description': self.description}
            raccount_lines.append((0, 0, lines))
        else:
            account_lines = []
            lines = {'fecha': self.fecha, 'debit': 0.0, 'credit': self.amount, 'origen': 'Transferencia', 'description': self.description,
                'concepto': 'Transferencia a la cuenta ' + self.account_id.res_partner_bank.acc_number + '. Autorización: ' + self.authorize}
            trans = {'fecha': self.fecha, 'debit': self.amount, 'credit': 0.0, 'origen': 'Transferencia', 'description': self.description,
                'concepto': 'Transferencia de la cuenta ' + self.raccount_id.res_partner_bank.acc_number + '. Autorización: ' + self.authorize}
            raccount_lines.append((0, 0, lines))
            account_lines.append((0, 0, trans))
            self.account_id.write({'line_ids': account_lines})    

        self.raccount_id.write({'line_ids': raccount_lines})
