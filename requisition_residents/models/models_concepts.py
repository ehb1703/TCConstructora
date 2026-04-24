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

    """def _post_html(self, title, old_stage=None, new_stage=None):
        parts = [f'<p>{html_escape(title)}</p>']
        if old_stage or new_stage:
            parts.append(
                f'<p>{html_escape(_('De'))} <b>{html_escape((old_stage and old_stage.name) or '-')}</b> '
                f'{html_escape(_('a'))} <b>{html_escape((new_stage and new_stage.name) or '-')}</b>.</p>')

        body = '<div>' + ''.join(parts) + '</div>'
        self.message_post(body=Markup(body), message_type='comment', subtype_xmlid='mail.mt_note')


    def action_send(self):
        # Agregar grupo
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

        self.state = 'aprobado' """