# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from datetime import date, datetime, timedelta
import json
import logging

_logger = logging.getLogger(__name__)

class requisitionMaterials(models.Model):
    _name = 'requisition.materials'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Requisiciones de Residentes de Obras'

    name = fields.Char(string='Nombre')
    project_id = fields.Many2one('project.project', string='Obra')
    employee_id = fields.Many2one('hr.employee', string='Responsable')
    company_id = fields.Many2one('res.company', string='Empresa', tracking=True)
    amount_untaxed = fields.Float(string='Importe sin IVA', compute='_compute_amount', store=True, readonly=True, tracking=True)
    amount_tax = fields.Float(string='Impuestos', compute='_compute_amount', store=True, readonly=True)
    amount_total = fields.Float(string='Total', compute='_compute_amount', store=True, readonly=True)
    line_ids = fields.One2many('requisition.materials.line', 'req_id', string='Resumen')
    state = fields.Selection(selection=[('draft','Borrador'), ('send','Enviado'), ('aprobado','Aprobado')],
        string='Estatus', default='draft', tracking=True)

    @api.depends('line_ids.price_amount', 'line_ids.price_tax', 'line_ids.price_total')
    def _compute_amount(self):
        for req in self:
            total_untaxed, total_tax, total = 0.0, 0.0, 0.0
            for line in req.line_ids:
                total_untaxed += line.price_amount
                total_tax += line.price_tax
                total += line.price_total
            req.amount_untaxed = total_untaxed
            req.amount_tax = total_tax
            req.amount_total = total
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['name'] = self.env['ir.sequence'].next_by_code('requisition.materials.name')
            employee = self.env['hr.employee'].search([('user_id','=',self.env.user.id)])
            if employee:
                vals['employee_id'] = employee.id
        return super().create(vals_list)

    def action_send(self):
        _logger.warning('Falta definir')


class requisitionMaterialsLine(models.Model):
    _name = 'requisition.materials.line'
    _description = 'Líneas de requisición'

    req_id = fields.Many2one('requisition.materials', readonly=True)
    urgencia = fields.Selection(selection=[('baja','Baja'), ('media','Media'), ('alta','Alta'), ('critica','Critica')],
        string='Urgencia', default='baja')
    product_qty = fields.Float(string='Cantidad', digits='Product Unit of Measure', required=True, readonly=False)
    taxes_id = fields.Many2many('account.tax', string='Taxes', domain="[('type_tax_use','=','purchase')]")
    product_id = fields.Many2one(comodel_name='product.product', string='Material', change_default=True, ondelete='restrict', 
        domain="[('purchase_ok', '=', True)]")
    product_uom_id = fields.Many2one(related='product_id.uom_id', string='UdM')
    price_unit = fields.Float(string='Unit Price', related='product_id.list_price')
    price_amount = fields.Float(string='Subtotal')
    price_total = fields.Float(string='Total')
    price_tax = fields.Float(string='Impuesto')

    @api.onchange('product_qty', 'price_unit', 'taxes_id')
    def _onchange_amount(self):
        imp = 0
        for rec in self.taxes_id:
            if rec.amount_type == 'percent':
                imp = rec.amount / 100
            else:
                imp = rec.amount
        self.price_amount = self.product_qty * self.price_unit
        self.price_tax = self.price_amount * imp
        self.price_total = self.price_amount + self.price_tax