# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import html_escape
from markupsafe import Markup  # Si prefieres, puedes prescindir y usar solo strings


class CrmRevertStageWizard(models.TransientModel):
    _name = 'crm.revert.stage.wizard'
    _description = 'Revertir etapa de CRM con motivo'

    lead_id = fields.Many2one('crm.lead', required=True, default=lambda self: self.env.context.get('default_lead_id') or self.env.context.get('active_id'))
    current_stage_sequence = fields.Integer(related='lead_id.stage_id.sequence', store=False, readonly=True)
    current_team_id = fields.Many2one('crm.team', related='lead_id.team_id', store=False, readonly=True)
    target_stage_id = fields.Many2one('crm.stage', string='Etapa destino', required=True)
    reason_id = fields.Many2one('crm.revert.reason', string='Motivo (catálogo)')
    reason_text = fields.Text(string='Motivo adicional')

    @api.onchange('lead_id')
    def _onchange_lead_id_set_domain(self):
        if self.lead_id and self.lead_id.stage_id:
            dom = [('sequence', '<', self.lead_id.stage_id.sequence)]
            if self.lead_id.team_id:
                dom = ['&', '|', ('team_id', '=', self.lead_id.team_id.id), ('team_id', '=', False)] + dom
            return {'domain': {'target_stage_id': dom}}
        return {'domain': {'target_stage_id': []}}

    def _check_target_stage(self):
        #Validación en servidor por si cambian el dominio desde el cliente.
        self.ensure_one()
        lead = self.lead_id
        if not self.target_stage_id:
            raise UserError('Debe seleccionar una etapa destino.')
        if lead.stage_id == self.target_stage_id:
            raise UserError(_('La etapa destino debe ser distinta a la actual.'))
        # Solo permitir secuencia estrictamente menor (ir hacia atrás)
        if not lead.stage_id or self.target_stage_id.sequence >= lead.stage_id.sequence:
            raise UserError('No es posible realizar esta acción.')
        # Misma pipeline/equipo si ambos lo tienen
        if lead.team_id and self.target_stage_id.team_id and lead.team_id != self.target_stage_id.team_id:
            raise UserError(_('La etapa destino no pertenece al equipo del lead.'))

    def action_confirm(self):
        self.ensure_one()
        self._check_target_stage()

        lead = self.lead_id.sudo()
        old_stage = lead.stage_id

        # Mover etapa permitiendo retroceso
        lead.with_context(allow_stage_revert=True).write({'stage_id': self.target_stage_id.id})

        # Log
        self.env['crm.revert.log'].sudo().create({
            'lead_id': lead.id,
            'user_id': self.env.user.id,
            'old_stage_id': old_stage.id,
            'new_stage_id': self.target_stage_id.id,
            'reason_id': self.reason_id.id or False,
            'reason_text': (self.reason_text or '').strip() or False,})

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
            f'</div>'
        )
        lead.message_post(body=Markup(body), message_type='comment', subtype_xmlid='mail.mt_note')

        return {'type': 'ir.actions.act_window_close'}
