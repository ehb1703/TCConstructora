# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import json
import logging

_logger = logging.getLogger(__name__)

class CrmCotizacionInsumoseWizard(models.TransientModel):
    _name = 'crm.cotizacion.insumos.wizard'
    _description = 'Generación de cotización para insumos'

    @api.depends('tipoinsumo_id')
    def _compute_domain_supplier(self):
        for record in self:
            if record.tipoinsumo_id:
                record.supplier_domain = json.dumps([('is_supplier', '=', True), ('tipo_insumo_ids', '=', record.tipoinsumo_id.id)])
            else:
                record.supplier_domain = json.dumps([('is_supplier', '=', True)])

    lead_id = fields.Many2one('crm.lead', required=True, default=lambda self: self.env.context.get('default_lead_id') or self.env.context.get('active_id'))
    tipoinsumo_id = fields.Many2one('product.tipo.insumo', string='Tipo de insumo')
    supplier_domain = fields.Char(readonly=True, store=False, compute=_compute_domain_supplier)
    supplier_ids = fields.Many2many('res.partner', string='Proveedores')

    def action_generar_orden(self, supplier):
        oc_vals = self.get_orden_default_values(self.lead_id, supplier)
        oc_vals_2 = oc_vals[:]
        oc_new = self._create_oc_async(oc_vals=oc_vals_2)
        return oc_new

    def get_orden_default_values(self, lead=False, supplier=False):
        if not supplier.id:
            raise UserError('No se ha capturado información de contacto')

        self.env.cr.execute('''SELECT (CASE WHEN UPPER(col5) = 'CANTIDAD' THEN 'col5' ELSE 'col6' END) cantidad, 
                (CASE WHEN UPPER(col6) = 'PRECIO' THEN 'col6' ELSE 'col7' END) precio 
            FROM crm_input_line ci WHERE ci.id = (SELECT MIN(ID) min_id FROM crm_input_line ci WHERE ci.lead_id = ''' + str(lead.id) + ')')
        min_id = self.env.cr.dictfetchall()

        cantidad = min_id[0]['cantidad']
        precio = min_id[0]['precio']
        sequence = self.env['ir.sequence'].next_by_code('purchase.order')
        orders = []
        order_lines = []
        taxes = []
        fpos = self.env['account.fiscal.position'].with_company(lead.company_id)._get_fiscal_position(supplier)
        origin = 'Insumos - ' + lead.name

        for rec in lead.input_ids.filtered(lambda u: u.input_ex and u.input_id.tipo_insumo_id.id == self.tipoinsumo_id.id):
            taxes = rec.input_id.supplier_taxes_id._filter_taxes_by_company(lead.company_id)
            product_id = self.env['product.product'].search([('product_tmpl_id','=',rec.input_id.id)])
            self.env.cr.execute('SELECT ' + cantidad + '::float qty, (CASE WHEN ' + precio + " = '' THEN '0.0' ELSE " + precio + 
                ' END)::float importe FROM crm_input_line cil WHERE cil.id = ' + str(rec.id))
            statement = self.env.cr.dictfetchall()

            lines = {'name': product_id.name, 'product_uom': product_id.uom_po_id.id, 'product_id': product_id.id, 'company_id': lead.company_id.id,
                'partner_id': supplier.id, 'currency_id': product_id.currency_id.id, 'state': 'draft', 'product_qty': statement[0]['qty'], 
                'price_unit': statement[0]['importe'], 'taxes_id': fpos.map_tax(taxes)}
            order_lines.append((0, 0, lines))

        values = {'lead_id': lead.id, 'name': sequence, 'partner_id': supplier.id, 'company_id': lead.company_id.id, 'currency_id': lead.company_id.currency_id.id,
            'user_id': self.env.uid, 'state': 'draft', 'invoice_status': 'no', 'type_purchase': 'ins', 'origin': origin, 'order_line': order_lines}
        orders.append(values)
        return orders


    def _create_oc_async(self, oc_vals):
        oc_obj = self.env['purchase.order']
        new_oc = oc_obj.create(oc_vals)        
        return new_oc

    def action_confirm(self):
        for rec in self.lead_id.oc_ids.filtered(lambda u: u.state != 'cancel' and u.type_purchase == 'ins'):
            if len(rec.order_line.filtered(lambda u: u.state != 'cancel' and u.product_id.tipo_insumo_id.id == self.tipoinsumo_id.id)) > 0:
                raise UserError('Ya existen Cotizaciones de Insumos generadas.')

        if len(self.lead_id.input_ids.filtered(lambda u: u.input_ex and u.input_id.tipo_insumo_id.id == self.tipoinsumo_id.id)) == 0:
            raise UserError('No existen productos a cotizar del tipo seleccionado.')

        for rec in self.supplier_ids:
            oc = self.action_generar_orden(rec)


class WizardCotizacionConfirmar(models.TransientModel):
    _name = 'purchase.confirm.order'

    def _get_orders(self):
        if self._context.get('orders'):
            orders_obj = self.env['purchase.order']
            orders = orders_obj.browse(self._context.get('orders', False))
            return orders

    ids_order = fields.Many2many('purchase.order', 'orden_confirmar', default=_get_orders)
    type_election = fields.Selection(selection=[('precio','Precio Unitario Menor')], string='Tipo de elección')

    def realizar_conf(self):
        order = ''
        precio = 0
        for rec in self.ids_order:
            order += str(rec.id) + ','

        order = order[:-1]
        if order != '':
            if self.type_election == 'precio':
                self.env.cr.execute('''UPDATE purchase_order_line pol SET ACTIVE = False 
                    FROM (SELECT pol.id FROM (SELECT product_id, MIN(price_unit) price_unit, COUNT(*) num FROM purchase_order_line pol WHERE active IS TRUE 
                                AND pol.order_id in (''' + order + ') GROUP BY 1) as t1 JOIN purchase_order_line pol ON pol.order_id IN (' + order + 
                            ') AND pol.active IS TRUE AND t1.product_id = pol.product_id AND t1.price_unit != pol.price_unit ) as t2 WHERE pol.ID = t2.id;')

                for rec in self.ids_order:
                    rec.button_confirm()
                    rec._amount_all()
        
        return True
