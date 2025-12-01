# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class supplyProductTemplate(models.Model):
    _inherit = 'product.template'
    
    type_supply = fields.Selection(selection=[('int','Interna'), ('ext','Externa')],
        string='Tipo de Aprovisionamiento', default='ext')
    budget_id = fields.Many2one('product.budget.item', string='Partida Presupestaria')
    

class productBudgetItem(models.Model):
    _name = 'product.budget.item'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Partida Presupuestaria'
    _rec_name = 'code'

    level = fields.Integer(string='Nivel', default='1')
    parent_id = fields.Many2one('product.budget.item', string='Padre')
    code = fields.Char(string='Código')
    name = fields.Char(string='Nombre')
    active = fields.Boolean(string='Activo')    
