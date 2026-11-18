# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import html_escape
from markupsafe import Markup
import logging

_logger = logging.getLogger(__name__)

class CrmRevertStageWizard(models.TransientModel):
    _inherit = 'crm.revert.stage.wizard'

    def action_confirm(self):
        self.ensure_one()
        self._check_target_stage()

        lead = self.lead_id.sudo()
        old_stage = lead.stage_id

        if old_stage.name == 'Junta de Aclaración de Dudas':
            lead.junta_notif_auto_sent = False
            lead.junta_notif_manual_sent = False
            lead.junta_obligatoria = False
            lead.junta_personas_ids = [(5, 0, 0)]
            lead.junta_fecha = False
            lead.junta_fecha_limite_dudas = False
            lead.junta_docto_dudas = False
            lead.junta_docto_dudas_name = False
            lead.junta_acta = False
            lead.junta_acta_name = False

        if old_stage.name == 'Junta de Apertura de Propuestas':
            lead.apertura_obligatoria = False
            lead.apertura_personas_ids = [(5, 0, 0)]
            lead.apertura_fecha = False
            lead.apertura_acta = False
            lead.apertura_acta_name = False
            lead.apertura_notif_auto_sent = False
            lead.apertura_notif_manual_sent = False

        if old_stage.name == 'Fallo':
            lead.fallo_ganado = False
            lead.fallo_notif_auto_sent = False
            lead.fallo_notif_manual_sent = False
            lead.fallo_fecha_publicacion = False
            lead.fallo_acta = False
            lead.fallo_acta_name = False

        if old_stage.name == 'Ganado':
            count = len(lead.order_ids.filtered(lambda u: u.state not in ('cancel', 'draft', 'sent')))
            if count != 0:
                raise UserError('Existen ordenes de trabajo pendientes, favor de revisar si no deben de ser canceladas para hacer esta acción')
            
            lead.fecha_limite_firma = False
            lead.contrato_firmado = False
            lead.fecha_firma = False
            lead.contrato_documento = False
            lead.fallo_ganado = False

        if self.target_stage_id.name == 'Propuesta Económica':
            presupuesto = self.env['gestion.obra.presupuesto.base'].search([('lead_id','=',lead.id), ('state','!=','cancel')])
            presupuesto.write({'state': 'cancel'})
        
        lead.write({'stage_id': self.target_stage_id.id, 'stage_previous': old_stage.name})

        self.env['crm.revert.log'].sudo().create({'lead_id': lead.id, 'user_id': self.env.user.id, 'old_stage_id': old_stage.id, 
            'new_stage_id': self.target_stage_id.id, 'reason_id': self.reason_id.id or False, 'reason_text': (self.reason_text or '').strip() or False,})

        # Mensaje al chatter (HTML renderizable)
        reason_lines = []
        if self.reason_id:
            reason_lines.append(html_escape(self.reason_id.name))
        if self.reason_text:
            reason_lines.append(html_escape(self.reason_text))
        reason_html = '<br/>'.join(reason_lines) if reason_lines else '-'

        body = (
            f'<div>'
            f'<p>{html_escape(_('Reversión de etapa ejecutada.'))}</p>'
            f'<p>{html_escape(_('De'))} <b>{html_escape(old_stage.name or '-')}</b> '
            f'{html_escape(_('a'))} <b>{html_escape(self.target_stage_id.name or '-')}</b>.</p>'
            f'<p>{html_escape(_('Motivo:'))} {reason_html}</p>'
            f'</div>')
        lead.message_post(body=Markup(body), message_type='comment', subtype_xmlid='mail.mt_note')

        return {'type': 'ir.actions.act_window_close'}