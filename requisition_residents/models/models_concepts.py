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
    _name = 'requisition.request.concept'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Solicitud de conceptos extraordinarios'

    @api.depends('tipo')
    def _compute_domain_project(self):
        lista = []
        for record in self:
            if self.env.user.has_group('requisition_residents.group_requisition_admin'):
                projects = self.env['project.project'].search([('stage_id.name','!=','Cancelada')])
                for x in projects:
                    lista.append(x.id)
            else:
                employee = self.env['hr.employee'].search([('user_id','=',self.env.user.id)])
                residentes = self.env['project.residents'].search([('resident_id','=',employee.id)])
                for x in residentes:
                    lista.append(x.project_id.id)
            record.project_domain = json.dumps([('id', 'in', lista)])

    tipo = fields.Selection(selection=[('concepto','Destajo'), ('insumo','Insumo')],
        string='Tipo de concepto', tracking=True)
    codigo = fields.Char(string='Codigo')
    description = fields.Char(string='Descripción')
    project_id = fields.Many2one('project.project', string='Obra')
    project_domain = fields.Char(readonly=True, store=False, compute=_compute_domain_project)
    product_id = fields.Many2one('product.template', string='Concepto')
    uom_id = fields.Many2one('uom.uom', string='Unidad de medida')
    price = fields.Float(string='Precio')
    state = fields.Selection(selection=[('draft','Borrador'), ('revision','Revision'), ('costos','Costos'), ('aprobado','Aprobado')],
        string='Estatus', default='draft', tracking=True)

    def _post_html(self, title, old_stage=None, new_stage=None):
        parts = [f'<p>{html_escape(title)}</p>']
        if old_stage or new_stage:
            parts.append(
                f'<p>{html_escape(_('De'))} <b>{html_escape((old_stage and old_stage.name) or '-')}</b> '
                f'{html_escape(_('a'))} <b>{html_escape((new_stage and new_stage.name) or '-')}</b>.</p>')

        body = '<div>' + ''.join(parts) + '</div>'
        self.message_post(body=Markup(body), message_type='comment', subtype_xmlid='mail.mt_note')


    def action_review(self):
        emails = set()
        group = self.env.ref('requisition_residents.group_encargado', raise_if_not_found=False)
        if group:
            for user in group.users.filtered(lambda u: u.active and u.partner_id and u.partner_id.email):
                emails.add(user.partner_id.email.strip())
        else:
            raise ValidationError('No hay usuarios asignados al grupo correspondiente. Favor de revisar con el administrador.')

        correos_list = sorted(e for e in emails if '@' in e)
        template = self.env.ref('requisition_residents.mail_tmpl_requisition_concept_solicitud', raise_if_not_found=False)
        try:
            correos = ', '.join(correos_list)
            email_values = {'model': 'requisition_request_concept', 'email_to': correos}
            template.send_mail(self.id, force_send=True, email_values=email_values)
            self._post_html(_('Se envió correo a: ') + correos)
        except Exception:
            self._post_html(_('Error al enviar el correo'))

        self.state = 'revision'


    def action_costos(self):
        emails = set()
        group = self.env.ref('requisition_residents.group_costos', raise_if_not_found=False)
        if group:
            for user in group.users.filtered(lambda u: u.active and u.partner_id and u.partner_id.email):
                emails.add(user.partner_id.email.strip())
        else:
            raise ValidationError('No hay usuarios asignados al grupo correspondiente. Favor de revisar con el administrador.')

        correos_list = sorted(e for e in emails if '@' in e)
        template = self.env.ref('requisition_residents.mail_tmpl_requisition_concept_costos', raise_if_not_found=False)
        try:
            correos = ', '.join(correos_list)
            email_values = {'model': 'requisition_request_concept', 'email_to': correos}
            template.send_mail(self.id, force_send=True, email_values=email_values)
            self._post_html(_('Se envió correo a: ') + correos)
        except Exception:
            self._post_html(_('Error al enviar el correo'))

        self.state = 'costos'


    def action_confirm(self):
        concepto = self.env['product.template'].search([('name','=',self.description)])
        if not concepto:
            cat = self.env['product.category'].search([('name','=','All')])
            if self.tipo == 'concepto':
                purchase = False
                sale = True
                iva = self.env['account.tax'].search([('name','=','16%'),('type_tax_use','=','sale')])
                type = 'service'
            else:
                purchase = True
                sale = False
                iva = self.env['account.tax'].search([('name','=','16%'),('type_tax_use','=','purchase')])
                type = 'consu'

            concepto = self.env['product.template'].create({'categ_id':cat.id, 'uom_id':self.uom_id.id, 'uom_po_id':self.uom_id.id, 
                'type':type, 'default_code':self.codigo, 'name':self.description, 'purchase_ok':purchase, 'sale_ok':sale, 'list_price':self.price, 
                'standard_price':self.price, 'supplier_taxes_id':[(6, 0, iva.ids)], 'active':True,})

        self.product_id = concepto.id
        self.state = 'aprobado'
