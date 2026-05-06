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
    line_ids = fields.One2many('requisition.materials.line', 'req_id', string='Resumen')
    oc_ids = fields.One2many('purchase.order', 'materials_id', string='Ordenes de compra relacionada')
    state = fields.Selection(selection=[('draft','Borrador'), ('send','Enviado'), ('aprobado','Aprobado')],
        string='Estatus', default='draft', tracking=True)
    
    @api.model
    def _search(self, domain, offset=0, limit=None, order=None):
        """if self.env.user.login == 'admin':
            return super()._search(domain, offset=offset, limit=limit, order=order)"""

        if self.env.user.has_group('requisition_residents.group_requisition_capture'):
            domain = [('create_uid', '=', self.env.user.id)]

        return super()._search(domain, offset=offset, limit=limit, order=order)


    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['name'] = self.env['ir.sequence'].next_by_code('requisition.materials.name')
            employee = self.env['hr.employee'].search([('user_id','=',self.env.user.id)])
            if employee:
                vals['employee_id'] = employee.id
        return super().create(vals_list)

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
            if not rec.supplier_ids:
                raise UserError('No se ha capturado información del proveedor')

        self.env.cr.execute('''SELECT rel.supplier_id FROM requisition_materials_line rml JOIN materials_supplier_rel rel ON rml.ID = rel.MATERIALS_ID 
            WHERE rml.REQ_ID = ''' + str(self.id) + ' GROUP BY 1')
        supplier = self.env.cr.dictfetchall()
        for rec in supplier:
            supplier_id = self.env['res.partner'].search([('id','=',rec['supplier_id'])])
            oc = self.action_generar_orden(supplier_id)

        self.state = 'aprobado'


    def action_generar_orden(self, supplier):
        oc_vals = self.get_orden_default_values(supplier)
        oc_vals_2 = oc_vals[:]
        oc_new = self._create_oc_async(oc_vals=oc_vals_2)
        return oc_new

    def get_orden_default_values(self, supplier=False):
        orders = []
        order_lines = []
        taxes = []
        fpos = self.env['account.fiscal.position'].with_company(self.env.user.company_id)._get_fiscal_position(supplier)
        sequence = self.env['ir.sequence'].next_by_code('purchase.order')
        origin = 'Materiales - ' + self.name

        for rec in self.line_ids:
            if supplier.id in rec.supplier_ids.ids:
                taxes = rec.product_id.supplier_taxes_id._filter_taxes_by_company(self.company_id)
                lines = {'name': rec.product_id.name, 'product_uom': rec.product_uom_id.id, 'product_id': rec.product_id.id, 'partner_id': supplier.id, 
                    'company_id': self.env.user.company_id.id, 'currency_id': rec.product_id.currency_id.id, 'state': 'draft', 'product_qty': rec.product_qty, 
                    'price_unit': 0, 'taxes_id': fpos.map_tax(taxes)}
                order_lines.append((0, 0, lines))

        values = {'materials_id': self.id, 'name': sequence, 'partner_id': supplier.id, 'company_id': self.env.user.company_id.id, 'origin': origin, 
            'currency_id': self.env.user.company_id.currency_id.id, 'user_id': self.env.uid, 'state': 'draft', 'invoice_status': 'no', 'type_purchase': 'mat', 
            'order_line': order_lines}
        orders.append(values)
        return orders


    def _create_oc_async(self, oc_vals):
        oc_obj = self.env['purchase.order']
        new_oc = oc_obj.create(oc_vals)
        return new_oc


class requisitionMaterialsLine(models.Model):
    _name = 'requisition.materials.line'
    _description = 'Líneas de requisición'

    req_id = fields.Many2one('requisition.materials', readonly=True)
    urgencia = fields.Selection(selection=[('baja','Baja'), ('media','Media'), ('alta','Alta'), ('critica','Critica')],
        string='Urgencia', default='baja')
    product_qty = fields.Float(string='Cantidad', digits='Product Unit of Measure', required=True, readonly=False)
    product_id = fields.Many2one(comodel_name='product.product', string='Material', change_default=True, ondelete='restrict', 
        domain="[('purchase_ok', '=', True)]")
    product_uom_id = fields.Many2one(related='product_id.uom_id', string='UdM')
    supplier_ids = fields.Many2many('res.partner', 'materials_supplier_rel', 'materials_id', 'supplier_id', string='Proveedor',  domain="[('is_supplier','=',True)]",)


class purchaseOrderInherit(models.Model):
    _inherit = 'purchase.order'

    materials_id = fields.Many2one('requisition.materials', string='Requisición de Materiales')
    type_purchase = fields.Selection(selection_add=[('mat','Materiales')])
    
    @api.depends('lead_id', 'lead_id.empresa_concursante_id', 'materials_id', 'lead_id.company_id')
    def _compute_empresa_solicitante(self):
        for order in self:
            if order.lead_id and order.lead_id.empresa_concursante_id:
                order.empresa_solicitante = order.lead_id.empresa_concursante_id.partner_id
            elif order.materials_id and order.materials_id.company_id:
                order.empresa_solicitante = order.materials_id.company_id.partner_id
            else:
                order.empresa_solicitante = False
