# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare

from .requisicion import TIPOS_REQUERIMIENTO


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    # Catálogo de campos: Proyecto Global en el encabezado de la compra (la obra de la orden)
    x_proyecto_id = fields.Many2one('project.project', string='Proyecto Global', related='project_id', store=True, readonly=False)
    # Regla 5: casilla de validación ejecutiva de Dirección para compras de $100,000 MXN o más
    x_aprobado_direccion = fields.Boolean(string='Aprobado por Dirección', tracking=True, copy=False)
    x_requisicion_ids = fields.Many2many('requisition.materials', string='Requisiciones consolidadas', compute='_compute_x_requisicion_ids')

    def _compute_x_requisicion_ids(self):
        for order in self:
            order.x_requisicion_ids = order.order_line.mapped('x_requisicion_line_ids.req_id')


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    x_frente_id = fields.Many2one('account.analytic.account', string='Bloque / Frente / Contrato', index=True,
        help='Frente de obra o contrato al que se imputa la recepción y el costo del insumo.')
    x_tipo_requerimiento = fields.Selection(TIPOS_REQUERIMIENTO, string='Tipo de Requerimiento')
    x_motivo_extraordinario = fields.Text(string='Motivo Extraordinario')
    x_requisicion_line_ids = fields.Many2many('requisition.materials.line', 'requisicion_materiales_compra_rel', 'compra_line_id',
        'requisicion_line_id', string='Líneas de requisición', copy=False)

    def write(self, vals):
        # Matriz, Jefatura de Compras: "Impedida la alteración de cantidades solicitadas por obra sin adenda"
        if 'product_qty' in vals and not self.env.context.get('permitir_cambio_cantidad'):
            for line in self.filtered('x_requisicion_line_ids'):
                solicitado = sum(line.x_requisicion_line_ids.mapped('product_qty'))
                if float_compare(vals['product_qty'], solicitado, precision_rounding=line.product_uom.rounding or 0.01):
                    raise UserError(_('No se puede alterar la cantidad solicitada por obra de "%(p)s" (%(q)s) sin adenda.',
                                      p=line.product_id.display_name, q=solicitado))
        res = super().write(vals)
        # Especificación, paso 4: el precio negociado se propaga a cada línea del mismo insumo asociada a su frente
        if 'price_unit' in vals and not self.env.context.get('homologando_precio'):
            for line in self.filtered('x_requisicion_line_ids'):
                hermanas = line.order_id.order_line.filtered(
                    lambda l: l != line and l.product_id == line.product_id and l.x_requisicion_line_ids and l.price_unit != line.price_unit)
                hermanas.with_context(homologando_precio=True).write({'price_unit': line.price_unit})
        return res


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # Regla 2: precio tope autorizado del insumo para los frentes
    x_precio_limite_frente = fields.Float(string='Precio tope por frente', digits='Product Price',
        help='Precio unitario máximo autorizado por Costos. Si está en cero se usa el costo del producto.')
