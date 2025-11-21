# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class CrmRevertStageWizard(models.TransientModel):
    _name = 'crm.cotizacion.insumos.wizard'
    _description = 'Generación de cotización para insumos'

    lead_id = fields.Many2one('crm.lead', required=True, default=lambda self: self.env.context.get('default_lead_id') or self.env.context.get('active_id'))
    supplier_ids = fields.Many2many('res.partner', string='Proveedores', domain="[('is_supplier', '=', True)]")

    def action_generar_orden(self, supplier):
        oc_vals = self.get_orden_default_values(self.lead_id, supplier)
        oc_vals_2 = oc_vals[:]
        oc_new = self._create_oc_async(oc_vals=oc_vals_2)
        return oc_new

    def get_orden_default_values(self, lead=False, supplier=False):
        if not supplier.id:
            raise UserError('No se ha capturado información de contacto')

        if self.lead_id.oc_ids.filtered(lambda u: u.state != 'cancel' and u.type_purchase == 'insumos'):
            raise UserError('Ya existen Cotizaciones de Insumos generadas.')

        sequence = self.env['ir.sequence'].next_by_code('purchase.order')

        
                
        orders = []
        order_lines = []
        taxes = []
        fpos = self.env['account.fiscal.position'].with_company(self.company_id)._get_fiscal_position(self.partner_id)

        for rec in lead.input_ids.filtered(lambda u: u.input_ex):
            product_id = self.env['product.product'].search([('product_tmpl_id','=',rec.input_id.id)])

            statement = ("""SELECT cil.col1 code, cil.col2 name, uu.id uom, pc.id cat,
                        (CASE WHEN uu.NAME->>'en_US' = 'Service' THEN 'service' ELSE 'consu' END) type, """ + cantidad + ' qty, ' + precio + 
                        '::float importe FROM crm_input_line cil JOIN uom_uom uu ON (CASE WHEN cil.' + unidad + 
                        " IN ('%MO', 'PIE TAB') THEN 'pza' ELSE lower(cil." + unidad + """) END) = lower(uu.name->>'en_US') 
                                JOIN uom_category uc ON uu.CATEGORY_ID = uc.ID 
                                JOIN product_category pc ON pc.NAME = 'All'
                    WHERE cil.id = """ + str(rec.id))

            taxes = rec.input_id.supplier_taxes_id._filter_taxes_by_company(self.company_id)
            order_lines.append((0, 0, {
                'name': product_id.name, 'product_uom': product_id.uom_po_id.id, 'product_id': product_id.id, 'company_id': self.lead_id.id,
                'partner_id': supplier.id, 'currency_id': product_id.currency_id.id, 'state': 'purchase', 'product_qty': 1, 
                'price_unit': price, 'taxes_id': fpos.map_tax(taxes) },))

            name = self.origen_id.product_id.name

        raise UserError('Sigo probando....')

        if self.no_licitacion:
            name += ' ' + self.no_licitacion

        
        values = {'lead_id': self.id, 'name': sequence, 'partner_id': self.partner_id.id, 'company_id': self.company_id.id, 
            'currency_id': self.origen_id.product_id.currency_id.id, 'user_id': self.env.uid, 'state': 'purchase', 'invoice_status': 'no', 
            'type_purchase': 'bases', 'order_line': order_lines}
        orders.append(values)
        return orders

    def _create_oc_async(self, oc_vals):
        oc_obj = self.env['purchase.order']
        new_oc = oc_obj.create(oc_vals)        
        return new_oc

    def action_confirm(self):
        for rec in self.supplier_ids:
            oc = self.action_generar_orden(rec)