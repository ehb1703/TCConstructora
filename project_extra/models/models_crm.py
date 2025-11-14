# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import html_escape
from markupsafe import Markup
from dateutil.relativedelta import relativedelta
import logging

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
        #Permite avanzar a etapas con secuencia mayor o igual. Bloquea retrocesos salvo contexto.
        self.ensure_one()
        if not self.stage_id or not new_stage:
            return True
        return (new_stage.sequence or 0) >= (self.stage_id.sequence or 0)

    def _ensure_stage_is_fallo(self):
        #Asegura que la etapa actual sea 'Fallo' (por nombre).
        self.ensure_one()
        stage_name = (self.stage_id.name or '').strip().lower()
        if stage_name != 'fallo':
            raise UserError(_('Solo puede marcar Perdido en la etapa FALLO.'))

    def _get_authorizer_emails_from_group(self, grupo):
        #Obtiene correos de los usuarios del grupo project_extra.group_conv_authorizer.
        emails = set()
        group = self.env.ref(grupo, raise_if_not_found=False)
        if group:
            for user in group.users.filtered(lambda u: u.active and u.partner_id and u.partner_id.email):
                emails.add(user.partner_id.email.strip())
        return sorted(e for e in emails if '@' in e)

    def _get_visita_emails(self):
        if not self.stage_id.email_ids:
            raise UserError('No hay información para realizar la distribución de correos.')

        emails = set()
        for rec in self.stage_id.email_ids:
            _logger.warning('Aqui 129')
            _logger.wanring(rec.id)

        raise UserError('Pendiente de revisar bien el proceso :D')
        

    def _send_visita_reminder(self, manual=False):
        # Envía correo de recordatorio de visita usando la plantilla de visita.
        template = self.env.ref('project_extra.mail_tmpl_visita_recordatorio', raise_if_not_found=False)
        if not template:
            raise UserError('No se encontró la plantilla de correo para recordatorio de visita de obra.')

        correos_list = self._get_visita_emails()
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
        #Envía notificación de autorización.
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
        #Autoriza la convocatoria y mueve a 'Calificado'.
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
	#Declinar convocatoria.
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
        #Envía correo a group_conv_authorizer para solicitar autorización de compra de bases.
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

    def action_send_visita_reminder(self):
        #Botón manual para enviar recordatorio de visita.
        self.ensure_one()
        if not self.visita_fecha:
            raise UserError('Debe capturar la fecha de visita.')
        self._send_visita_reminder(manual=True)

    # --- VISITA DE OBRA: CRON ---
    @api.model
    def cron_send_visita_reminders(self):
        """Cron: envía recordatorio un día antes de la fecha de visita."""
        today = fields.Date.context_today(self)
        target = today + relativedelta(days=1)

        domain = [('visita_obligatoria', '=', True), ('visita_fecha', '=', target), ('visita_notif_auto_sent', '=', False),]
        leads = self.search(domain)
        if leads:
            leads._send_visita_reminder(manual=False)
