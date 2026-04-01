# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import date, datetime, timedelta
from markupsafe import Markup
from odoo.tools import html_escape
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
    """amount_untaxed = fields.Float(string='Importe sin IVA', compute='_compute_amount', store=True, readonly=True, tracking=True)
    amount_tax = fields.Float(string='Impuestos', compute='_compute_amount', store=True, readonly=True)
    amount_total = fields.Float(string='Total', compute='_compute_amount', store=True, readonly=True) """
    line_ids = fields.One2many('requisition.materials.line', 'req_id', string='Resumen')
    state = fields.Selection(selection=[('draft','Borrador'), ('send','Enviado'), ('aprobado','Aprobado')],
        string='Estatus', default='draft', tracking=True)

    """@api.depends('line_ids.price_amount', 'line_ids.price_tax', 'line_ids.price_total')
    def _compute_amount(self):
        for req in self:
            total_untaxed, total_tax, total = 0.0, 0.0, 0.0
            for line in req.line_ids:
                total_untaxed += line.price_amount
                total_tax += line.price_tax
                total += line.price_total
            req.amount_untaxed = total_untaxed
            req.amount_tax = total_tax
            req.amount_total = total """
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['name'] = self.env['ir.sequence'].next_by_code('requisition.materials.name')
            employee = self.env['hr.employee'].search([('user_id','=',self.env.user.id)])
            if employee:
                vals['employee_id'] = employee.id
        return super().create(vals_list)

    def action_send(self):
        template = self.env.ref('requisition_residents.mail_tmpl_requisition_materials_solicitud', raise_if_not_found=False)
        if not template:
            raise UserError(_('No se encontró la plantilla de correo.'))

        for lead in self:
            correos = ', '.join(lead._get_emails())
            template.send_mail(lead.id, force_send=True, email_values={'email_to': correos})
            if manual:
                lead.fallo_notif_manual_sent = True
            else:
                lead.fallo_notif_auto_sent = True

            lead.message_post(body=_("Se envió notificación de FALLO GANADO."))


    def _post_html(self, title, old_stage=None, new_stage=None):
        parts = [f'<p>{html_escape(title)}</p>']
        if old_stage or new_stage:
            parts.append(
                f'<p>{html_escape(_('De'))} <b>{html_escape((old_stage and old_stage.name) or '-')}</b> '
                f'{html_escape(_('a'))} <b>{html_escape((new_stage and new_stage.name) or '-')}</b>.</p>')

        body = '<div>' + ''.join(parts) + '</div>'
        self.message_post(body=Markup(body), message_type='comment', subtype_xmlid='mail.mt_note')


    def action_send(self):
        emails = set()
        group = self.env.ref('requisition_residents.group_materials_authorize', raise_if_not_found=False)
        if group:
            for user in group.users.filtered(lambda u: u.active and u.partner_id and u.partner_id.email):
                emails.add(user.partner_id.email.strip())

        correos_list = sorted(e for e in emails if '@' in e)
        template = self.env.ref('requisition_residents.mail_tmpl_requisition_materials_solicitud', raise_if_not_found=False)
        try:
            correos = ', '.join(correos_list)
            email_values = {'model': 'requisition_materials', 'email_to': correos}
            template.send_mail(self.id, force_send=True, email_values=email_values)
            self._post_html(_('Se envió correo a: ') + correos)
        except Exception:
            self._post_html(_('Error al enviar el correo'))

        self.state = 'send'


    def action_confirm(self):
        for rec in self.line_ids:
            if not rec.supplier_id:
                raise UserError('No se ha capturado información del proveedor')

        self.env.cr.execute('SELECT supplier_id FROM requisition_materials_line rml WHERE rml.REQ_ID = ' + str(self.id) + ' GROUP BY 1')
        supplier = self.env.cr.dictfetchall()
        for rec in supplier:
            oc = self.action_generar_orden(rec['supplier_id'])


    def action_generar_orden(self, supplier):
        oc_vals = self.get_orden_default_values(supplier)
        oc_vals_2 = oc_vals[:]
        oc_new = self._create_oc_async(oc_vals=oc_vals_2)
        return oc_new

    def get_orden_default_values(self, supplier=False):
        cantidad = min_id[0]['cantidad']
        precio = 0
        sequence = self.env['ir.sequence'].next_by_code('purchase.order')
        orders = []
        order_lines = []
        taxes = []
        fpos = self.env['account.fiscal.position'].with_company(lead.company_id)._get_fiscal_position(supplier)
        origin = 'Materiales - ' + self.name

        for rec in self.line_ids.filtered(lambda u: u.supplier_id.id == supplier):
            taxes = rec.input_id.supplier_taxes_id._filter_taxes_by_company(self.company_id)
            ###Voy aqui
            lines = {'name': rec.product_id.name, 'product_uom': rec.product_id.uom_po_id.id, 'product_id': product_id.id, 'company_id': lead.company_id.id,
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


class requisitionMaterialsLine(models.Model):
    _name = 'requisition.materials.line'
    _description = 'Líneas de requisición'

    """def _default_taxes_id(self):
        return self.req_id.company_id.account_purchase_tax_id """

    req_id = fields.Many2one('requisition.materials', readonly=True)
    urgencia = fields.Selection(selection=[('baja','Baja'), ('media','Media'), ('alta','Alta'), ('critica','Critica')],
        string='Urgencia', default='baja')
    product_qty = fields.Float(string='Cantidad', digits='Product Unit of Measure', required=True, readonly=False)
    product_id = fields.Many2one(comodel_name='product.product', string='Material', change_default=True, ondelete='restrict', 
        domain="[('purchase_ok', '=', True)]")
    product_uom_id = fields.Many2one(related='product_id.uom_id', string='UdM')
    supplier_id = fields.Many2one('res.partner', string='Proveedor',  domain="[('is_supplier','=',True)]",)
    """price_unit = fields.Float(string='Unit Price', related='product_id.list_price')
    taxes_id = fields.Many2many('account.tax', string='Taxes', domain="[('type_tax_use','=','purchase')]", default=_default_taxes_id)
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
        self.price_total = self.price_amount + self.price_tax """
