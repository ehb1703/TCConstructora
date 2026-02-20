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
    _description = 'Estado de cuenta del Proveedor'

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

    @api.depends('partner_id')
    def _compute_display_name(self):
        if self._context.get('special_display_name', False):
            for rec in self:
                rec.display_name = f'Abrir'
        else:
            for rec in self:
                rec.display_name = f'{rec.partner_id.name}'


class requisitionDebtLine(models.Model):
    _name = 'requisition.debt.line'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Movimientos'

    req_id = fields.Many2one('requisition.debt', readonly=True)
    project_id = fields.Many2one('project.project', string='Obra')
    fecha = fields.Date(string='Fecha')
    debit = fields.Float(string='Cargo')
    credit = fields.Float(string='Abono')
    concepto = fields.Char(string='Concepto')
    origen = fields.Char(string='Origen')
    type_pay = fields.Char(string='Tipo de pago', readonly=True)
    recibo = fields.Binary(string='Recibo', attachment=True)
    recibo_name = fields.Char(string='Nombre del recibo')
    account_id = fields.Many2one('res.partner.bank', string='Cuenta Bancaria', tracking=True, ondelete='restrict', copy=False)
    comprobantes_ids = fields.Many2many(comodel_name='ir.attachment', string='Comprobantes')
    observaciones = fields.Char(string='Observaciones')
    reqres_id = fields.Many2one('requisition.residents', string='Requisición Residente')
    movcta_id = fields.Many2one('requisition.bank.movements', string='Movimiento bancario')
    reqw_id = fields.Many2one('requisition.weekly', string='Requisición semanal')


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
    line_ids = fields.One2many('requisition.bank.movements', 'mov_id', string='Resumen')

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

    @api.depends('line_ids.credit', 'line_ids.debit')
    def _compute_balance(self):
        for req in self:
            credit, debit = 0.0, 0.0
            for line in req.line_ids:
                credit += line.credit
                debit += line.debit
            req.balance = debit - credit

    def action_agregar(self):
        return {
            'name': _('Generar Cargo Bancario'),
            'type': 'ir.actions.act_window',
            'res_model': 'requisition.transfer.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_raccount_id': self.id}}


class requisitionBankMovements(models.Model):
    _name = 'requisition.bank.movements'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Movimientos bancarios'

    mov_id = fields.Many2one('requisition.bank.account', readonly=True)
    fecha = fields.Date(string='Fecha')
    debit = fields.Float(string='Cargo')
    credit = fields.Float(string='Abono')
    concepto = fields.Text(string='Concepto')
    origen = fields.Char(string='Origen')
    description = fields.Char(string='Descripción')
    reqw_id = fields.Many2one('requisition.weekly', string='Requisición semanal')


class requisitionGeneralPayments(models.Model):
    _name = 'requisition.general.payments'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Pagos generales'

    partner_id = fields.Many2one('res.partner', string='Proveedor')
    type_comp = fields.Selection(selection=[('tiq','Tiquet'), ('fact','Factura'), ('rem','Nota de remisión')],
        string='Tipo de comprobación', default='tiq', tracking=True)
    reference = fields.Char(string='Referencia')
    accountbank_id = fields.Many2one('requisition.bank.account', string='Cuenta bancaria', domain="[('obsolete', '=', False)]")
    fecha = fields.Date(string='Fecha')
    product_id = fields.Many2one(comodel_name='product.product', string='Concepto', change_default=True, ondelete='restrict', 
        domain="[('purchase_ok', '=', True)]")
    product_template_id = fields.Many2one(comodel_name='product.template', string='Product Template', compute='_compute_product_template_id',
        search='_search_product_template_id', domain=[('purchase_ok', '=', True)])
    amount = fields.Float(string='Importe')
    state = fields.Selection(selection=[('draft','Borrador'), ('done', 'Pagado')],
        string='Estatus', default='draft', tracking=True)

    @api.depends('product_id')
    def _compute_product_template_id(self):
        for line in self:
            line.product_template_id = line.product_id.product_tmpl_id

    def _search_product_template_id(self, operator, value):
        return [('product_id.product_tmpl_id', operator, value)]
