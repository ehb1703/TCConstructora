# -*- coding: utf-8 -*-
from odoo import api, models, _
from odoo.exceptions import ValidationError


class ProductProductInsumo(models.Model):
    _inherit = 'product.product'

    @api.constrains('default_code', 'purchase_ok', 'active')
    def _check_referencia_insumo_unica(self):
        # Solo insumos (productos de compra): los conceptos de venta del CRM pueden repetir código entre partidas
        for producto in self.filtered(lambda p: p.purchase_ok and p.active and (p.default_code or '').strip()):
            codigo = producto.default_code.strip()
            # ilike trae candidatos (el _ y el % actúan como comodín); la igualdad exacta sin mayúsculas se decide aquí
            otro = self.search([('id', '!=', producto.id), ('purchase_ok', '=', True), ('default_code', 'ilike', codigo)]).filtered(
                lambda p: (p.default_code or '').strip().lower() == codigo.lower())[:1]
            if otro:
                raise ValidationError(_('Ya existe el insumo %(otro)s con la referencia interna %(codigo)s. No se permiten insumos duplicados.',
                                        otro=otro.display_name, codigo=codigo))


class ProductTemplateInsumo(models.Model):
    _inherit = 'product.template'

    @api.constrains('default_code', 'purchase_ok', 'active')
    def _check_referencia_insumo_unica(self):
        self.product_variant_ids._check_referencia_insumo_unica()
