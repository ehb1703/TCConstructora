# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import html_escape
from markupsafe import Markup
from dateutil.relativedelta import relativedelta
import logging
import os
import tempfile
import openpyxl
import binascii

_logger = logging.getLogger(__name__)

class CrmRevertLog(models.Model):
    _name = 'crm.revert.log'
    _description = 'Bitácora de reversiones de etapa'

    lead_id = fields.Many2one('crm.lead', string='Oportunidad', required=True, ondelete='cascade')
    user_id = fields.Many2one('res.users', string='Usuario', default=lambda self: self.env.user, required=True)
    old_stage_id = fields.Many2one('crm.stage', string='Etapa anterior', required=True)
    new_stage_id = fields.Many2one('crm.stage', string='Etapa nueva', required=True)
    reason_id = fields.Many2one('crm.revert.reason', string='Motivo (catálogo)')
    reason_text = fields.Text(string='Motivo adicional')

class CrmLead(models.Model):
    _inherit = 'crm.lead'

    zona_geografica_id = fields.Many2one('project.zona.geografica', string='Zona geográfica', tracking=True)
    partner_emisor_id = fields.Many2one('res.partner', string='Dependencia emisora', tracking=True)
    tipo_obra_id = fields.Many2one('project.type', string='Tipo de obra', tracking=True)
    especialidad_ids = fields.Many2many('project.especialidad', string='Especialidad(es) requerida(s)')
    monto_min = fields.Float(string='Monto mínimo')
    monto_max = fields.Float(string='Monto máximo')
    fecha_convocatoria = fields.Date(string='Fecha de convocatoria')
    fecha_limite_inscripcion = fields.Date(string='Fecha límite de inscripción')
    fecha_apertura = fields.Date(string='Fecha de apertura')
    convocatoria_pdf = fields.Binary(string='PDF de convocatoria', attachment=True)
    convocatoria_pdf_name = fields.Char(string='Nombre del archivo')
    origen_id = fields.Many2one('crm.lead.type', string='Tipo de Venta')
    origen_name = fields.Char(string='Tipo nombre', compute='_compute_bases')
    req_bases = fields.Boolean(string='Requiere pago de bases', compute='_compute_bases')
    tipo_obra_ok = fields.Boolean('Tipo de obra cumple', tracking=True)
    dependencia_ok = fields.Boolean('Dependencia emisora cumple', tracking=True)
    capital_ok = fields.Boolean('Capital contable cumple', tracking=True)
    in_calificado = fields.Boolean(string='En calificado', compute='_compute_botones', store=False)
    oc_ids = fields.One2many('purchase.order', 'lead_id', string='Ordenes de compra relacionada')
    revert_log_ids = fields.One2many('crm.revert.log', 'lead_id', string='Bitácora de reversiones', readonly=True)
    revert_log_count = fields.Integer(compute='_compute_revert_log_count', string='Reversiones')
    no_licitacion = fields.Char(string='No. de Licitación')
    desc_licitacion = fields.Char(string='Descripción')
    stage_name = fields.Char(string='State name', compute='_compute_name_stage', store=False)
    # Inscripción / Compra de bases
    bases_pay = fields.Boolean('Pagar bases', tracking=True)
    bases_supervisor_id = fields.Many2one('hr.employee', string='Supervisor general', tracking=True)
    bases_cost = fields.Float(string='Costo', tracking=True)
    bases_doc = fields.Binary(string='Docto. Bases', attachment=True)
    bases_doc_name = fields.Char(string='Nombre del documento')
    bases_notification_sent = fields.Boolean(string='Notificación de bases enviada', default=False)
    # Visita de obra
    visita_obligatoria = fields.Boolean(string='Visita obligatoria')
    visita_personas_ids = fields.Many2many('hr.employee', 'crm_lead_visita_employee_rel', 'lead_id', 'employee_id', string='Personas asignadas')
    visita_fecha = fields.Date(string='Fecha de visita')
    visita_acta = fields.Binary(string='Acta de visita', attachment=True)
    visita_acta_name = fields.Char(string='Nombre acta de visita')
    visita_notif_auto_sent = fields.Boolean(string='Notif. automática enviada', default=False)
    visita_notif_manual_sent = fields.Boolean(string='Notif. manual enviada', default=False)
    # Junta de Aclaración de dudas
    junta_obligatoria = fields.Boolean(string='Asistencia obligatoria')
    junta_personas_ids = fields.Many2many('hr.employee','crm_lead_junta_employee_rel','lead_id','employee_id',string='Personas asignadas')
    junta_fecha = fields.Date(string='Fecha de junta')
    junta_fecha_limite_dudas = fields.Date(string='Fecha límite para envío de dudas')
    junta_docto_dudas = fields.Binary(string='Docto. de dudas', attachment=True)
    junta_docto_dudas_name = fields.Char(string='Nombre docto. de dudas')
    junta_acta = fields.Binary(string='Acta de la junta', attachment=True)
    junta_acta_name = fields.Char(string='Nombre acta de la junta')
    junta_notif_auto_sent = fields.Boolean(string='Notif. automática junta enviada', default=False)
    junta_notif_manual_sent = fields.Boolean(string='Notif. manual junta enviada', default=False)
    # Insumos
    input_ids = fields.One2many('crm.input.line', 'lead_id', string='Insumos')
    input_file = fields.Binary(string='Archivo', help='Seleccionar el archivo con el formato correcto para la carga la información.')
    input_filename = fields.Char(string='Nombre del archivo', tracking=True)

    @api.onchange('origen_id')
    def _compute_bases(self):
        for record in self:
            record.req_bases = bool(getattr(record.origen_id, 'bases', False))
            record.origen_name = record.origen_id.name if record.origen_id else False

    @api.onchange('tipo_obra_ok', 'dependencia_ok', 'capital_ok')
    def _compute_botones(self):
        for rec in self:
            rec.in_calificado = False
            if rec.stage_id.name in ('Nuevas Convocatorias', 'Fallo'):
                if (rec.tipo_obra_ok and rec.dependencia_ok and rec.capital_ok):
                    rec.in_calificado = True

    @api.depends('revert_log_ids')
    def _compute_revert_log_count(self):
        groups = self.env['crm.revert.log'].read_group([('lead_id', 'in', self.ids)], ['lead_id'], ['lead_id'])
        counts = {g['lead_id'][0]: g['lead_id_count'] for g in groups}
        for r in self:
            r.revert_log_count = counts.get(r.id, 0)

    def _compute_name_stage(self):
        for record in self:
            record.stage_name = record.stage_id.name

    # ---------- Helpers ----------
    def _get_stage_by_name(self, name):
        #Busca etapa por nombre EXACTO en el pipeline del lead (o global).
        self.ensure_one()
        Stage = self.env['crm.stage']
        domain = [('name', '=', name)]
        if self.team_id:
            domain = ['|', ('team_id', '=', self.team_id.id), ('team_id', '=', False)] + domain
        return Stage.search(domain, limit=1)

    def _is_forward_or_same_stage(self, new_stage):
        # Permite avanzar a etapas con secuencia mayor o igual. Bloquea retrocesos salvo contexto.
        self.ensure_one()
        if not self.stage_id or not new_stage:
            return True
        return (new_stage.sequence or 0) >= (self.stage_id.sequence or 0)

    def _ensure_stage_is_fallo(self):
        # Asegura que la etapa actual sea 'Fallo' (por nombre).
        self.ensure_one()
        stage_name = (self.stage_id.name or '').strip().lower()
        if stage_name != 'fallo':
            raise UserError(_('Solo puede marcar Perdido en la etapa FALLO.'))

    def _get_authorizer_emails_from_group(self, grupo):
        # Obtiene correos de los usuarios del grupo project_extra.group_conv_authorizer.
        emails = set()
        group = self.env.ref(grupo, raise_if_not_found=False)
        if group:
            for user in group.users.filtered(lambda u: u.active and u.partner_id and u.partner_id.email):
                emails.add(user.partner_id.email.strip())
        return sorted(e for e in emails if '@' in e)

    def _post_html(self, title, old_stage=None, new_stage=None):
        parts = [f'<p>{html_escape(title)}</p>']
        if old_stage or new_stage:
            parts.append(
                f'<p>{html_escape(_('De'))} <b>{html_escape((old_stage and old_stage.name) or '-')}</b> '
                f'{html_escape(_('a'))} <b>{html_escape((new_stage and new_stage.name) or '-')}</b>.</p>')
        body = '<div>' + ''.join(parts) + '</div>'
        self.message_post(body=Markup(body), message_type='comment', subtype_xmlid='mail.mt_note')

    def _log_stage_change(self, old_stage, new_stage, reason_id, reason_text=''):
        self.env['crm.revert.log'].sudo().create({
            'lead_id': self.id,
            'user_id': self.env.user.id,
            'old_stage_id': old_stage.id if old_stage else False,
            'new_stage_id': new_stage.id if new_stage else False,
            'reason_id': reason_id,
            'reason_text': reason_text or False,})

    # ----------------- Acciones -----------------
    def action_request_authorization(self):
        # Envía notificación de autorización.
        for lead in self:
            if not lead.in_calificado:
                raise UserError(_('Debe marcar los 3 criterios para solicitar autorización.'))

            correos_list = lead._get_authorizer_emails_from_group('project_extra.group_conv_authorizer')
            template = self.env.ref('project_extra.calif_mail_tmpl_convocatoria_autorizacion', raise_if_not_found=False)

            faltantes = []
            if not template:
                faltantes.append(_('plantilla'))
            if not correos_list:
                faltantes.append(_('destinatarios con permiso'))

            if faltantes:
                lead._post_html(_('Solicitud de autorización lista, pero faltan: ') + ', '.join(faltantes))
                if not correos_list:
                    raise UserError(_('''No hay usuarios configurados con permiso para autorizar (o no tienen correo).
                        Agregue usuarios al grupo “Puede autorizar convocatorias”.'''))
                if not template:
                    raise UserError(_('No se encontró la plantilla de correo para solicitar autorización.'))
                continue

            try:
                correos = ', '.join(correos_list)
                email_values = {'model': 'crm.lead', 'email_to': correos}
                template.send_mail(lead.id, force_send=True, email_values=email_values)
                lead._post_html(_('Se envió correo a: ') + correos)
            except Exception:
                lead._post_html(_('Error al enviar el correo'))

    def action_authorize(self):
        # Autoriza la convocatoria y mueve a 'Calificado'.
        self.ensure_one()
        if not self.env.user.has_group('project_extra.group_conv_authorizer'):
            raise UserError(_('No tiene permisos para autorizar.'))
        if not self.in_calificado:
            raise UserError(_('No puede autorizar sin los 3 criterios marcados.'))
        # Etapa destino
        dest_stage = self._get_stage_by_name('Calificado')
        if not dest_stage:
            raise UserError(_('No se encontró la etapa CALIFICADO'))
        old_stage = self.stage_id
        if old_stage.id != dest_stage.id:
            self.with_context(allow_stage_revert=True).write({'stage_id': dest_stage.id})

        self._log_stage_change(old_stage, dest_stage, False, 'Autorizado')
        self._post_html(_('Convocatoria autorizada.'), old_stage, dest_stage)

    def action_decline(self):
        # Declinar convocatoria.
        self.ensure_one()
        if not self.env.user.has_group('project_extra.group_conv_authorizer'):
            raise UserError(_('No tiene permisos para declinar.'))
        if not self.in_calificado:
            raise UserError(_('Debe evaluar los tres criterios antes de declinar.'))

        dest_stage = self._get_stage_by_name('Declinado')
        if not dest_stage:
            raise UserError('No se encontró la etapa DECLINADO')

        old_stage = self.stage_id
        if old_stage.id != dest_stage.id:
            self.with_context(allow_stage_revert=True).write({'stage_id': dest_stage.id})

        self._log_stage_change(old_stage, dest_stage, False, 'Declinado')
        self._post_html(_('Declinada por %s.') % self.env.user.display_name, old_stage, dest_stage)

    def write(self, vals):
        # Bloquea retrocesos de etapa salvo contexto {'allow_stage_revert': True}.
        if 'stage_id' in vals and not self.env.context.get('allow_stage_revert'):
            new_stage = self.env['crm.stage'].browse(vals['stage_id'])
            for lead in self:
                if not lead._is_forward_or_same_stage(new_stage):
                    raise UserError('No está permitido regresar etapas manualmente.')
        return super().write(vals)

    def action_set_lost(self, **kwargs):
        for lead in self:
            lead._ensure_stage_is_fallo()
        return super(CrmLead, self).action_set_lost(**kwargs)

    def action_advance_stage(self):
        if self.stage_name == 'Inscripción/Compra de bases':
            if self.bases_pay:
                if not self.oc_ids.filtered(lambda u: u.state != 'cancel' and u.type_purchase == 'bases'):
                    raise UserError('Favor de realizar la orden de compra antes de avanzar la etapa') 
                if not self.bases_doc:
                    raise UserError('Falta cargar las Bases correspondientes') 
            else:
                if not self.bases_doc:
                    raise UserError('Falta cargar las Bases correspondientes')

        if self.stage_name == 'Visita de Obra':
            if self.visita_obligatoria and not self.visita_acta:
                raise UserError('Falta cargar el Acta de la Visita')

        if self.stage_name == 'Junta de Aclaración de Dudas':
            if self.junta_obligatoria and not self.junta_acta:
                raise UserError('Falta cargar el Acta de la Junta de Aclaración de Dudas.')

        sequence = self.stage_id.sequence
        reason = self.env['crm.revert.reason'].search([('name','=','Avance')])
        new_stage = self.env['crm.stage'].search([('sequence','=', sequence + 1)])

        if not new_stage:
            raise UserError('Existe un error en el flujo de las etapas, favor de revisar las configuraciones')

        self._log_stage_change(self.stage_id, new_stage, reason.id, 'Autorizado')
        self.stage_id = new_stage.id


    def action_revert_stage(self):
        # Abre el asistente para regresar la etapa con motivo.
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'crm.revert.stage.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_lead_id': self.id},}

    def action_generar_orden(self):
        oc_vals = self.get_orden_default_values(self.id)
        oc_vals_2 = oc_vals[:]
        oc_new = self._create_oc_async(oc_vals=oc_vals_2)
        return oc_new

    def get_orden_default_values(self, lead=False):
        if not self.partner_id.id:
            raise UserError('No se ha capturado información de contacto')

        if not self.origen_id.product_id.id:
            raise UserError('Falta configurar el concepto a pagar')

        if not self.env.user.has_group('project_extra.group_conv_authorizer'):
            raise UserError('Solo usuarios autorizadores pueden aprobar la compra de bases.')

        if not self.bases_pay:
            raise UserError('La licitación no necesita orden de compra')

        if not self.bases_cost or self.bases_cost == 0.00:
            raise UserError('Capturar el costo de la requisición.')

        if self.oc_ids.filtered(lambda u: u.state != 'cancel' and u.type_purchase == 'bases'):
            raise UserError('Ya existe Orden de pago ligada.')

        self.ensure_one()
        sequence = self.env['ir.sequence'].next_by_code('purchase.order')
        price = self.bases_cost
        
        orders = []
        order_lines = []
        taxes = []
        fpos = self.env['account.fiscal.position'].with_company(self.company_id)._get_fiscal_position(self.partner_id)
        taxes = self.origen_id.product_id.supplier_taxes_id._filter_taxes_by_company(self.company_id)

        name = self.origen_id.product_id.name
        if self.no_licitacion:
            name += ' ' + self.no_licitacion

        raise UserError(name)

        order_lines.append((0, 0, {
            'name': name,
            'product_uom': self.origen_id.product_id.uom_po_id.id,            
            'product_id': self.origen_id.product_id.id,
            'company_id': self.company_id.id,
            'partner_id': self.partner_id.id,
            'currency_id': self.origen_id.product_id.currency_id.id,
            'state': 'purchase',
            'product_qty': 1,
            'price_unit': price,
            'taxes_id': fpos.map_tax(taxes) },))
        
        values = {
            'lead_id': self.id,
            'name': sequence,
            'partner_id': self.partner_id.id,
            'company_id': self.company_id.id,
            'currency_id': self.origen_id.product_id.currency_id.id,
            'user_id': self.env.uid,
            'state': 'purchase',
            'invoice_status': 'no',
            'type_purchase': 'bases',
            'order_line': order_lines}
        orders.append(values)
        return orders

    def _create_oc_async(self, oc_vals):
        oc_obj = self.env['purchase.order']
        new_oc = oc_obj.create(oc_vals)        
        return new_oc

    def action_open_revert_logs(self):
        self.ensure_one()
        action = self.env.ref('project_extra.action_crm_revert_log').read()[0]
        action['domain'] = [('lead_id', '=', self.id)]
        action['context'] = {'default_lead_id': self.id}
        return action

    def action_send_bases(self):
        # Envía correo a group_conv_authorizer para solicitar autorización de compra de bases.
        for lead in self:
            if not lead.bases_cost:
                raise UserError('Debes capturar el costo de las bases.')

            correos_list = lead._get_authorizer_emails_from_group('project_extra.group_conv_authorizer')
            template = self.env.ref('project_extra.mail_tmpl_bases_solicitud', raise_if_not_found=False)

            if not correos_list:
                raise UserError(_('''No hay usuarios configurados con permiso para autorizar (o no tienen correo).
                        Agregue usuarios al grupo “Puede autorizar convocatorias”.'''))
            if not template:
                raise UserError(_('No se encontró la plantilla de correo para solicitud de bases.'))

            try:
                correos = ', '.join(correos_list)
                email_values = {'model': 'crm.lead', 'email_to': correos}
                template.send_mail(lead.id, force_send=True, email_values=email_values)
                lead.bases_notification_sent = True
                lead._post_html(_('Se envió correo a: ') + correos)
            except Exception:
                lead._post_html(_('Error al enviar el correo'))

    def action_authorize_bases(self):
        # La ejecuta un usuario del grupo project_extra.group_conv_authorizer. Genera OC y notifica a Finanzas.
        self.ensure_one()

        oc = self.action_generar_orden()

        correos_list = self._get_authorizer_emails_from_group('purchase.group_purchase_user')
        template = self.env.ref('project_extra.mail_tmpl_bases_autorizar', raise_if_not_found=False)

        if not correos_list:
            raise UserError('No hay usuarios configurados con permiso para autorizar (o no tienen correo).')
        if not template:
            raise UserError(_('No se encontró la plantilla de correo para solicitud de bases.'))

        try:
            correos = ', '.join(correos_list)
            email_values = {'model': 'purchase.order', 'email_to': correos}
            template.send_mail(self.id, force_send=True, email_values=email_values)
            self.bases_notification_sent = True
            self._post_html(_('Se envió correo a: ') + correos)
        except Exception:
            self._post_html(_('Error al enviar el correo'))


    def _get_emails(self):
        emails = set()
        for rec in self.stage_id.email_ids:
            if rec.work_email:
                emails.add(rec.work_email.strip())
            elif rec.private_email:
                emails.add(rec.private_email.strip())
            elif rec.address_id.email:
                emails.add(rec.address_id.email.strip())
            else:
                raise UserError(('No existen correos configurados del empleado %s') % rec.name)

        if self.stage_name == 'Visita de Obra':
            correos = self.visita_personas_ids
        else:
            correos = self.junta_personas_ids

        if not correos:
            raise UserError(_('Debe asignar al menos una persona para la %s') % self.stage_name)

        for rec in correos:
            if rec.work_email:
                emails.add(rec.work_email.strip())
            elif rec.private_email:
                emails.add(rec.private_email.strip())
            elif rec.address_id.email:
                emails.add(rec.address_id.email.strip())
            else:
                raise UserError(('No existen correos configurados del empleado %s') % rec.name)

        return sorted(e for e in emails if '@' in e) 


    def _send_visita_reminder(self, manual=False):
        # Envía correo de recordatorio de visita usando la plantilla de visita.
        template = self.env.ref('project_extra.mail_tmpl_visita_recordatorio', raise_if_not_found=False)
        if not template:
            raise UserError('No se encontró la plantilla de correo para recordatorio de visita de obra.')

        correos_list = self._get_emails()
        correos = ', '.join(correos_list)

        for lead in self:
            if not lead.visita_obligatoria or not lead.visita_fecha:
                continue

            email_values = {'email_to': correos,}
            template.send_mail(lead.id, force_send=True, email_values=email_values)
            if manual:
                lead.visita_notif_manual_sent = True
            else:
                lead.visita_notif_auto_sent = True

            lead.message_post(body=_("Se envió recordatorio de visita de obra a: %s") % correos)

    def action_send_visita_reminder(self):
        #Botón manual para enviar recordatorio de visita.
        self.ensure_one()
        if not self.visita_fecha:
            raise UserError('Debe capturar la fecha de visita.')
        self._send_visita_reminder(manual=True)

    @api.model
    def cron_send_visita_reminders(self):
        # Cron: envía recordatorio un día antes de la fecha de visita.
        today = fields.Date.context_today(self)
        target = today + relativedelta(days=1)

        domain = [('visita_obligatoria', '=', True), ('visita_fecha', '=', target), ('visita_notif_auto_sent', '=', False),]
        leads = self.search(domain)
        if leads:
            leads._send_visita_reminder(manual=False)

    # Funciones de actualización de los campos relacionados con la junta
    @api.onchange('junta_obligatoria', 'junta_personas_ids', 'junta_fecha')
    def _compute_junta_notif(self):
        for rec in self:
            if rec.junta_obligatoria and rec.junta_personas_ids:
                rec.junta_notif_auto_sent = False
                rec.junta_notif_manual_sent = False

    @api.onchange('junta_fecha', 'junta_fecha_limite_dudas')
    def _validate_junta_fields(self):
        for rec in self:
            if rec.junta_fecha and rec.junta_fecha_limite_dudas and rec.junta_fecha > rec.junta_fecha_limite_dudas:
                raise UserError(_('La fecha límite para enviar dudas no puede ser posterior a la fecha de la junta.'))

    def _send_junta_reminder(self, manual=False):
        template = self.env.ref('project_extra.mail_tmpl_junta_recordatorio', raise_if_not_found=False)
        if not template:
            raise UserError(_('No se encontró la plantilla de correo para recordatorio de la Junta de Aclaración de Dudas.'))

        for lead in self:
            if not lead.junta_obligatoria or not lead.junta_fecha:
                continue

            email_to = ', '.join(lead._get_emails())
            email_values = {'email_to': email_to}

            template.send_mail(lead.id, force_send=True, email_values=email_values)

            if manual:
                lead.junta_notif_manual_sent = True
            else:
                lead.junta_notif_auto_sent = True

            lead.message_post(body=_("Se envió recordatorio de junta a: %s") % email_to)

    def action_send_junta_reminder_manual(self):
        self.ensure_one()
        if not self.junta_fecha:
            raise UserError(_('Debe capturar la fecha de la Junta de Aclaración de Dudas.'))
        self._send_junta_reminder(manual=True)

    @api.model
    def cron_send_junta_reminders(self):
        # Cron: envía recordatorio un día antes de la Junta de Aclaración de Dudas.
        today = fields.Date.context_today(self)
        target = today + relativedelta(days=1)

        domain = [('junta_obligatoria', '=', True), ('junta_fecha', '=', target), ('junta_notif_auto_sent', '=', False),]
        leads = self.search(domain)
        if leads:
            leads._send_junta_reminder(manual=False)

    def action_cargar_registros(self):
        for record in self:
            if not record.input_file:
                raise ValidationError('Seleccione un archivo para cargar.')

            if record.input_file and record.input_ids:
                raise ValidationError('Ya hay información cargada. En caso de ser necesario volver a cargar debe eliminarlos.')

            filename, file_extension = os.path.splitext(record.input_filename)
            if file_extension in ['.xlsx', '.xls', '.xlsm']:
                record.__leer_carga_archivo()
            else:
                raise ValidationError('Seleccione un archivo tipo xlsx, xls, xlsm')


    def __leer_carga_archivo(self):
        for record in self:
            file = tempfile.NamedTemporaryFile(suffix=".xlsx")
            file.write(binascii.a2b_base64(record.input_file))
            file.seek(0)
            xlsx_file = file.name
            
            wb = openpyxl.load_workbook(filename=xlsx_file, data_only=True)
            sheets = wb.sheetnames
            sheet_name = sheets[0]
            sheet = wb[sheet_name]
            registros = []
            cargar = False
            for row in sheet.iter_rows(values_only=True):
                col1 = str(row[0]).strip()
                col2 = str(row[1]).strip()
                col3 = str(row[2]).strip()
                col4 = str(row[3]).strip()
                col5 = str(row[4]).strip()
                col6 = str(row[5]).strip()
                col7 = str(row[6]).strip()
                col8 = str(row[7]).strip()
                if col1 == 'None':
                    col1 = ''
                if col2 == 'None':
                    col2 = ''
                if col3 == 'None':
                    col3 = ''
                if col4 == 'None':
                    col4 = ''
                if col5 == 'None':
                    col5 = ''
                if col6 == 'None':
                    col6 = ''
                if col7 == 'None':
                    col7 = ''
                if col8 == 'None':
                    col8 = ''
                if col1.upper() == 'CÓDIGO':
                    cargar = True

                if cargar:
                    if col1 != '' and col8 != '':
                        registro = {'col1': col1, 'col2': col2, 'col3': col3, 'col4': col4, 'col5': col5, 'col6': col6, 'col7': col7, 'col8': col8}
                        registros.append((0, 0, registro))

            record.write({'input_ids': registros})

    def action_genera_conceptos(self):
        self.env.cr.execute('SELECT col1, COUNT(*) num FROM crm_input_line WHERE lead_id = ' + str(self.id) + ' GROUP BY 1 HAVING COUNT(*) > 1')
        duplicado = self.env.cr.dictfetchall()
        if duplicado:
            raise UserError('Existen conceptos repetidos favor de revisar el archivo.')

        self.env.cr.execute('SELECT MIN(ID) min_id FROM crm_input_line ci WHERE ci.lead_id = ' + str(self.id))
        min_id = self.env.cr.dictfetchall()

        self.env.cr.execute('''UPDATE crm_input_line cil SET input_ex = True
            FROM (SELECT cil.id, REPLACE(cil.col1, ' ', '') CODE, COUNT(pt.id) num 
                    FROM crm_input_line cil LEFT JOIN product_template pt ON REPLACE(cil.col1, ' ', '') = pt.default_code 
                   WHERE cil.LEAD_ID = ''' + str(self.id) + ' and cil.id != ' + str(min_id[0]['min_id']) + ''' AND cil.input_ex = False GROUP BY 1, 2) as t1
            WHERE cil.id = t1.id AND t1.num != 0;
            UPDATE crm_input_line cil SET account_ex = true
            FROM (SELECT cil.id, REPLACE(cil.col1, ' ', '') code, COUNT(pt.account_id) num 
                    FROM crm_input_line cil JOIN product_template pt ON REPLACE(cil.col1, ' ', '') = pt.default_code 
                   WHERE cil.LEAD_ID = ''' + str(self.id) + ' AND cil.id != ' + str(min_id[0]['min_id']) + ''' AND pt.account_id = False GROUP BY 1, 2) as t1
            WHERE cil.id = t1.id;''')

        #self.


    def action_unlink_details(self):
        for record in self:
            record.input_ids.unlink()


class crmInputsLine(models.Model):
    _name = 'crm.input.line'
    _description = 'Insumos'
    
    lead_id = fields.Many2one(comodel_name='crm.lead', string='Oportudidad', readonly=True)
    col1 = fields.Char(string='Columna 1')
    col2 = fields.Char(string='Columna 2')
    col3 = fields.Char(string='Columna 3')
    col4 = fields.Char(string='Columna 4')
    col5 = fields.Char(string='Columna 5')
    col6 = fields.Char(string='Columna 6')
    col7 = fields.Char(string='Columna 7')
    col8 = fields.Char(string='Columna 8')
    input_ex = fields.Boolean(string='Insumo cargado', default=False)
    account_ex = fields.Char(string='Cuenta relacionada', default=False)
