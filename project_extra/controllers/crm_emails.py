# -*- coding: utf-8 -*-
from odoo import _, http
from odoo.http import request
from odoo.exceptions import UserError

class BasesAuthorizationController(http.Controller):
    def _get_lead(self, lead_id):
        # Obtiene el lead o lanza un error claro si no existe.
        lead = request.env['crm.lead'].sudo().browse(lead_id)
        if not lead or not lead.exists():
            raise UserError(_('La convocatoria ya no existe o fue eliminada.'))
        return lead

    def _check_common_security(self, lead):
        user = request.env.user
        if not lead.active:
            raise UserError(_('No puede operar sobre una oportunidad archivada.'))

        if lead.company_id and lead.company_id != user.company_id:
            raise UserError(_('La oportunidad pertenece a otra compañía.'))


    def _ensure_bases_stage(self, lead):
        stage_name = (lead.stage_name or lead.stage_id.name or '').strip()
        if lead.stage_name not in ('Inscripción/Compra de bases', 'Declinado'):
            raise UserError(_('Solo puede autorizar o declinar la compra de bases en la etapa "Inscripción/Compra de bases" o "Declinado.'))

    @http.route('/project_extra/bases/<int:lead_id>/authorize', type='http', auth='user')
    def authorize_bases(self, lead_id, **kw):
        lead = self._get_lead(lead_id)
        self._check_common_security(lead)
        self._ensure_bases_stage(lead)
        lead.with_user(request.env.user).action_authorize_bases()
        return request.redirect(f"/web#id={lead.id}&model=crm.lead&view_type=form")

    @http.route('/project_extra/bases/<int:lead_id>/decline', type='http', auth='user')
    def bases_decline(self, lead_id, **kw):
        lead = self._get_lead(lead_id)
        self._check_common_security(lead)
        self._ensure_bases_stage(lead)
        lead.with_user(request.env.user).action_decline_bases()
        return request.redirect(f"/web#id={lead.id}&model=crm.lead&view_type=form")


class ConvocatoriaAuthorizationController(http.Controller):
    # Reusamos la misma idea de helpers, pero independientes por clase
    def _get_lead(self, lead_id):
        lead = request.env['crm.lead'].sudo().browse(lead_id)
        if not lead or not lead.exists():
            raise UserError(_('La convocatoria ya no existe o fue eliminada.'))
        return lead

    def _check_common_security(self, lead):
        user = request.env.user
        if not lead.active:
            raise UserError(_('No puede operar sobre una oportunidad archivada.'))

        if lead.company_id and lead.company_id != user.company_id:
            raise UserError(_('La oportunidad pertenece a otra compañía.'))


    def _ensure_convocatoria_stage(self, lead):
        if stage_name not in ('Nuevas Convocatorias', 'Declinado'):
            raise UserError(_('Solo puede autorizar o declinar la convocatoria desde las etapas "Nuevas Convocatorias" o "Declinado".'))

    @http.route('/project_extra/convocatoria/<int:lead_id>/authorize', type='http', auth='user')
    def authorize_convocatoria(self, lead_id, **kw):
        lead = self._get_lead(lead_id)
        self._check_common_security(lead)
        self._ensure_convocatoria_stage(lead)
        lead.with_user(request.env.user).action_authorize()
        return request.redirect(f"/web#id={lead.id}&model=crm.lead&view_type=form")

    @http.route('/project_extra/convocatoria/<int:lead_id>/decline', type='http', auth='user')
    def decline_convocatoria(self, lead_id, **kw):
        lead = self._get_lead(lead_id)
        self._check_common_security(lead)
        self._ensure_convocatoria_stage(lead)
        lead.with_user(request.env.user).action_decline()
        return request.redirect(f"/web#id={lead.id}&model=crm.lead&view_type=form")
