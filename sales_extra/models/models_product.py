# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)

class ProductUnspscCodeExtended(models.Model):
    _inherit = 'product.unspsc.code'

    grupo_sat = fields.Char(string='Grupo SAT', compute='_compute_grupo_segmento', store=True, help='Primeros 4 dígitos del código UNSPSC')
    segmento_sat = fields.Char(string='Segmento', compute='_compute_grupo_segmento', store=True, help='Primeros 2 dígitos del código UNSPSC')

    @api.depends('code')
    def _compute_grupo_segmento(self):
        for record in self:
            if record.code and len(record.code) >= 4:
                record.grupo_sat = record.code[:4]
                record.segmento_sat = record.code[:2]
            elif record.code and len(record.code) >= 2:
                record.grupo_sat = record.code
                record.segmento_sat = record.code[:2]
            else:
                record.grupo_sat = record.code or ''
                record.segmento_sat = record.code or ''
                

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

class ProductComboInherit(models.Model):
    _inherit = 'product.combo'

    combo_line_ids = fields.One2many('product.combo.line', 'combo_id', string='Combos')

    @api.depends('combo_item_ids', 'combo_line_ids')
    def _compute_base_price(self):
        for combo in self:
            combo.base_price = sum(combo.combo_item_ids.mapped(lambda item: item.currency_id._convert(
                    from_amount=item.extra_price, to_currency=combo.currency_id, company=combo.company_id or self.env.company, date=self.env.cr.now(),)
                )) if combo.combo_item_ids else 0
            for x in combo.combo_line_ids:
                combo.base_price +=  x.price
            

class ProductComboItemInherit(models.Model):
    _inherit = 'product.combo.item'

    combo_qty = fields.Float(string='Cantidad', digits='Product Unit of Measure')

class ProductComboLine(models.Model):
    _name = 'product.combo.line'

    combo_id = fields.Many2one(comodel_name='product.combo', required=True, string='Combo relacionado', readonly=True)
    combos_id = fields.Many2one(comodel_name='product.combo', required=True, string='Combo')
    lst_price = fields.Float(string='Precio', digits='Product Price', compute='_compute_lst_price')
    combo_qty = fields.Float(string='Cantidad', digits='Product Unit of Measure', default=1)
    price = fields.Float(string='Price', digits='Product Price', compute='_compute_price', store=True)

    @api.onchange('combos_id')
    def _compute_lst_price(self):
        for record in self:
            if record.combos_id:
                _logger.warning(record.combos_id)
                record.lst_price = record.combos_id.base_price

    @api.depends('lst_price', 'combo_qty')
    def _compute_price(self):
        for combo in self:
            combo.price = combo.lst_price * combo.combo_qty
