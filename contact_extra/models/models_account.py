# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)

class accountInherit(models.Model):
    _inherit = 'account.account'
    
    parent_id = fields.Many2one('account.account', string='Padre')
    naturaleza = fields.Selection([('deudora', 'Deudora'), ('acreedora','Acreedora')], string='Naturaleza')
    level = fields.Integer(string='Nivel')
    sat_code = fields.Char(string='Código SAT')
    nif_code = fields.Char(string='Código NIF')
    is_afectable = fields.Boolean(string='Es afectable')

class partnerBankInherit(models.Model):
    _inherit = 'res.partner.bank'

    bank_name = fields.Char(related='bank_id.name', string='Nombre del Banco', store=False)
    no_tarjeta = fields.Char(string='No. de Tarjeta')
    type_pay = fields.Selection(selection=[('estrategia','Estrategia'), ('transferencia','Transferencia'), ('fiscal','Fiscal')],
        string='Tipo', default='estrategia')

    @api.onchange('bank_name')
    def onchange_bank(self):
        if self.bank_name:
            generico = self.env['res.partner'].search([('name', '=', 'ADMINISTRADOR')])
            self.partner_id = generico.id
