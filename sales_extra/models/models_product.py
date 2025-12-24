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


class ProductComboInherit(models.Model):
    _inherit = 'product.combo'

    combo_ids = fields.Many2many('product.combo', 'product_combo_rel', 'combo_id', string='Combos')

    @api.depends('combo_item_ids')
    def _compute_base_price(self):
        for combo in self:
            combo.base_price = sum(combo.combo_item_ids.mapped(lambda item: item.currency_id._convert(
                    from_amount=item.extra_price, to_currency=combo.currency_id, company=combo.company_id or self.env.company, date=self.env.cr.now(),)
                )) if combo.combo_item_ids else 0    


class ProductCombo(models.Model):
    _inherit = 'product.combo.item'

    combo_qty = fields.Float(string='Cantidad', digits='Product Unit of Measure')
