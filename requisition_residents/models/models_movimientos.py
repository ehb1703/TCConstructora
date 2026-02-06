# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import date, datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

class requisitionDebt(models.Model):
    _name = 'requisition.debt'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'partner_id'
    _description = 'Adeudo por proveedor'

    partner_id = fields.Many2one('res.partner', string='Proveedor')
    amount_total = fields.Float(string='Total', compute='_compute_amount', store=True, readonly=True)
    line_ids = fields.One2many('requisition.debt.line', 'req_id', string='Movimientos')

    @api.depends('line_ids.credit', 'line_ids.debit')
    def _compute_amount(self):
        for req in self:
            credit, debit = 0.0, 0.0
            for line in req.line_ids:
                credit += line.credit
                debit += line.debit
            req.amount_total = debit - credit


class requisitionDebtLine(models.Model):
    _name = 'requisition.debt.line'
    _description = 'Momivientos'

    req_id = fields.Many2one('requisition.debt', readonly=True)
    project_id = fields.Many2one('project.project', string='Obra')
    fecha = fields.Date(string='Fecha')
    debit = fields.Float(string='Cargo')
    credit = fields.Float(string='Abono')
    concepto = fields.Char(string='Concepto')
    origen = fields.Char(string='Origen')
    reqres_id = fields.Many2one('requisition.residents', string='Requisición Residente')


class requisitionBankAccount(models.Model):
    _name = 'requisition.bank.account'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'res_partner_bank'
    _description = 'Cuentas bancarias'

    company_id = fields.Many2one('res.company', string='Compañia')
    res_bank = fields.Many2one('res.bank', string='Banco')
    res_partner_bank = fields.Many2one('res.partner.bank', string='Cuenta bancaria')
    obsolete = fields.Boolean(string='Obsoleta')
    balance = fields.Float(string='Saldo', compute='_compute_balance', store=True, readonly=True)
    #line_ids = fields.One2many('requisition.bank.movements', 'mov_id', string='Resumen')

    _sql_constraints = [('req_account_uniq', 'unique(company_id, res_bank, res_partner_bank)', 'Los datos bancarios deben de ser unicos.'),]

    def action_update_account_bank(self):
        self.env.cr.execute('''INSERT INTO requisition_bank_account (company_id, res_bank, res_partner_bank, obsolete, create_date, write_date, create_uid, 
                write_uid)
            SELECT id, bank_id, bank_account_id, false, now(), now(), {}, {}
              FROM (SELECT rc.id, rc.name, bank_account_id, rpb.bank_id 
                      FROM res_company rc JOIN res_partner_bank rpb ON rc.bank_account_id = rpb.id
                    UNION ALL  
                    SELECT rc.id, rc.name, bank_accounts_id, rpb.bank_id 
                      FROM res_company rc JOIN res_partner_bank rpb ON rc.bank_accounts_id = rpb.id) as t1
             WHERE NOT EXISTS(SELECT * FROM requisition_bank_account rba WHERE rba.company_id = t1.id AND rba.res_bank = t1.bank_id 
                                AND rba.res_partner_bank = t1.bank_account_id);
            UPDATE requisition_bank_account rba SET obsolete = true, write_date = now(), write_uid = {}
              FROM (SELECT id FROM requisition_bank_account rba 
                     WHERE not exists (SELECT * FROM res_company rc 
                                        WHERE rba.company_id = rc.id 
                                          AND (rba.res_partner_bank = rc.bank_account_id OR rba.res_partner_bank = rc.bank_accounts_id))) as t1
             WHERE rba.id = t1.id;
            UPDATE requisition_bank_account rba SET obsolete = false, write_date = now(), write_uid = {}
              FROM (SELECT id FROM requisition_bank_account rba 
                     WHERE rba.obsolete IS true 
                       AND EXISTS (SELECT * FROM res_company rc 
                                        WHERE rba.company_id = rc.id 
                                          AND (rba.res_partner_bank = rc.bank_account_id OR rba.res_partner_bank = rc.bank_accounts_id))) as t1
             WHERE rba.id = t1.id; '''.format(self.env.user.id, self.env.user.id, self.env.user.id, self.env.user.id))


"""class requisitionBankMovements(models.Model):
    _name = 'requisition.bank.movements'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'res_partner_bank'
    _description = 'Movimientos bancarios'

    mov_id = fields.Many2one('requisition.bank.account', readonly=True)
    project_id = fields.Many2one('project.project', string='Obra')
    fecha = fields.Date(string='Fecha')
    debit = fields.Float(string='Cargo')
    credit = fields.Float(string='Abono')
    concepto = fields.Char(string='Concepto')
    origen = fields.Char(string='Origen')
    reqres_id = fields.Many2one('requisition.residents', string='Requisición Residente') """