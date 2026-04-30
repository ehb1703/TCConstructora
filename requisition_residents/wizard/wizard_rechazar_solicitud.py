# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import ValidationError
from markupsafe import Markup


class WizardRechazarSolicitud(models.TransientModel):
    _name = 'requisition.rechazar.solicitud'
    _description = 'Rechazar solicitud de trámite RH'

    solicitud_id = fields.Many2one('requisition.hr.solicitud', string='Solicitud', required=True)
    motivo = fields.Text(string='Motivo de rechazo', required=True)

    def action_confirmar_rechazo(self):
        self.ensure_one()
        if not self.motivo:
            raise ValidationError(_('Debe indicar el motivo de rechazo.'))

        solicitud = self.solicitud_id
        solicitud.motivo_rechazo = self.motivo

        partner = solicitud.create_uid.partner_id
        body = Markup(
            '<p>Su solicitud <b>{nombre}</b> fue <b>rechazada</b>.</p>'
            '<p><b>Motivo:</b> {motivo}</p>'
            '<p>Por favor corrija la información y vuelva a enviar la solicitud.</p>'
        ).format(nombre=solicitud.display_name, motivo=self.motivo)

        solicitud.message_post(body=body, message_type='email', subtype_xmlid='mail.mt_comment', partner_ids=partner.ids,)
        solicitud.state = 'draft'
        solicitud._post_html(Markup(_('Solicitud rechazada. Motivo: ') + self.motivo))