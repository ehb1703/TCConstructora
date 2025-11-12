# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import html_escape
from markupsafe import Markup
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


class TipoZona(models.Model):
    _name = 'project.tipo.zona'
    _description = 'Tipos de Zona'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'code'

    name = fields.Char(string='Nombre del tipo', required=True, tracking=True)
    code = fields.Char(string='ID / Clave', tracking=True)
    description = fields.Char(string='Descripción', size=250)
    active = fields.Boolean(string='Activo', default=True)


class ZonaGeografica(models.Model):
    _name = 'project.zona.geografica'
    _description = 'Zonas Geográficas'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'code'

    name = fields.Char(string='Nombre de zona', required=True, tracking=True)
    code = fields.Char(string='Código de zona', size=10, tracking=True)
    tipo_zona_id = fields.Many2one('project.tipo.zona', string='Tipo de zona', ondelete='restrict', tracking=True)
    active = fields.Boolean(string='Activo', default=True)
    observaciones = fields.Text(string='Observaciones')

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.code} / {rec.name}" if rec.code else rec.name


class Especialidad(models.Model):
    _name = 'project.especialidad'
    _description = 'Especialidades'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char(string='Nombre de especialidad', required=True, tracking=True)
    description = fields.Char(string='Descripción', size=300)
    clasificacion_id = fields.Many2one('project.technical.category', string='Categoría técnica', tracking=True)
    active = fields.Boolean(string='Activo', default=True)


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
    origen_id = fields.Many2one('crm.lead.type', string='Tipo')
    origen_name = fields.Char(string='Tipo nombre', compute='_compute_bases')
    req_bases = fields.Boolean(string='Requiere pago de bases', compute='_compute_bases')
    tipo_obra_ok = fields.Boolean('Tipo de obra cumple', tracking=True)
    dependencia_ok = fields.Boolean('Dependencia emisora cumple', tracking=True)
    capital_ok = fields.Boolean('Capital contable cumple', tracking=True)
    in_calificado = fields.Boolean(string='En calificado', compute='_compute_botones', store=False)
    oc_id = fields.Many2one('purchase.order', string='Ordenes de compra relacionada')
    revert_log_ids = fields.One2many('crm.revert.log', 'lead_id', string='Bitácora de reversiones', readonly=True)
    revert_log_count = fields.Integer(compute='_compute_revert_log_count', string='Reversiones')

    def _get_stage_by_name(self, name):
        #Devuelve la etapa cuyo nombre coincide (iLike).
        return self.env['crm.stage'].search([('name', 'ilike', name)], limit=1)

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
            

    # ---------- Helpers ----------
    def _get_stage_by_name(self, name):
        """Busca etapa por nombre EXACTO en el pipeline del lead (o global)."""
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
            raise UserError(_('Solo puede marcar Ganado/Perdido en la etapa "Fallo".'))

    def _get_authorizer_emails_from_group(self):
        """Obtiene correos de los usuarios del grupo project_extra.group_conv_authorizer."""
        emails = set()
        group = self.env.ref('project_extra.group_conv_authorizer', raise_if_not_found=False)
        if group:
            for user in group.users.filtered(lambda u: u.active and u.partner_id and u.partner_id.email):
                emails.add(user.partner_id.email.strip())
        return sorted(e for e in emails if '@' in e)

    # ---- Helpers de bitácora / chatter ----
    def _log_stage_change(self, old_stage, new_stage, reason_text=''):
        self.env['crm.revert.log'].sudo().create({
            'lead_id': self.id,
            'user_id': self.env.user.id,
            'old_stage_id': old_stage.id if old_stage else False,
            'new_stage_id': new_stage.id if new_stage else False,
            'reason_id': False,
            'reason_text': reason_text or False,})


    def _post_html(self, title, old_stage=None, new_stage=None):
        parts = [f"<p>{html_escape(title)}</p>"]
        if old_stage or new_stage:
            parts.append(
                f"<p>{html_escape(_('De'))} <b>{html_escape((old_stage and old_stage.name) or '-')}</b> "
                f"{html_escape(_('a'))} <b>{html_escape((new_stage and new_stage.name) or '-')}</b>.</p>"
            )
        body = "<div>" + "".join(parts) + "</div>"
        self.message_post(body=Markup(body), message_type='comment', subtype_xmlid='mail.mt_note')


    # ----------------- Acciones -----------------
    def action_request_authorization(self):
        #Envía notificación de autorización.
        for lead in self:
            if not lead.in_calificado:
                raise UserError(_('Debe marcar los 3 criterios para solicitar autorización.'))

            correos_list = lead._get_authorizer_emails_from_group()
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
            raise UserError(_("No se encontró la etapa 'Calificado'."))

        old_stage = self.stage_id
        if old_stage.id != dest_stage.id:
            # mover con flag para no chocar con el guard de retrocesos
            self.with_context(allow_stage_revert=True).write({'stage_id': dest_stage.id})

        # Bitácora + chatter
        self._log_stage_change(old_stage, dest_stage, reason_text='Autorizado')
        self._post_html(_('Convocatoria autorizada.'), old_stage, dest_stage)

        # Correo
        tmpl = self.env.ref('project_extra.calif_mail_tmpl_convocatoria_autorizacion', raise_if_not_found=False)
        if tmpl:
            tmpl.send_mail(self.id, force_send=True)

        return {'type': 'ir.actions.client', 'tag': 'reload'}


    def action_decline(self):
	#Declinar convocatoria.
        self.ensure_one()
        if not self.env.user.has_group('project_extra.group_conv_authorizer'):
            raise UserError(_('No tiene permisos para declinar.'))
        if not self.in_calificado:
            raise UserError(_('Debe evaluar los tres criterios antes de declinar.'))

        dest_stage = self._get_stage_by_name('Declinado')
        if not dest_stage:
            raise UserError(_("No se encontró la etapa 'Declinado'."))

        old_stage = self.stage_id
        if old_stage.id != dest_stage.id:
            self.with_context(allow_stage_revert=True).write({'stage_id': dest_stage.id})

        self._log_stage_change(old_stage, dest_stage, reason_text='Declinado')
        self._post_html(_('Declinada por %s.') % self.env.user.display_name, old_stage, dest_stage)
        return {'type': 'ir.actions.client', 'tag': 'reload'}


    def write(self, vals):
        # Bloquea retrocesos de etapa salvo contexto {'allow_stage_revert': True}.
        if 'stage_id' in vals and not self.env.context.get('allow_stage_revert'):
            new_stage = self.env['crm.stage'].browse(vals['stage_id'])
            for lead in self:
                if not lead._is_forward_or_same_stage(new_stage):
                    raise UserError(_("No está permitido regresar etapas manualmente."))
        return super().write(vals)

    def action_set_lost(self, **kwargs):
        for lead in self:
            lead._ensure_stage_is_fallo()
        return super(CrmLead, self).action_set_lost(**kwargs)


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
        raise UserError('Pendiente de hacer el proceso completo')

    @api.depends('revert_log_ids')
    def _compute_revert_log_count(self):
        # más performante con read_group:
        groups = self.env['crm.revert.log'].read_group([('lead_id', 'in', self.ids)], ['lead_id'], ['lead_id'])
        counts = {g['lead_id'][0]: g['lead_id_count'] for g in groups}
        for r in self:
            r.revert_log_count = counts.get(r.id, 0)
