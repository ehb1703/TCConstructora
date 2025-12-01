# -*- coding: utf-8 -*-
from odoo import _, http
from odoo.http import request


class ConvocatoriaAuthorizationController(http.Controller):

    @http.route('/project_extra/convocatoria/<int:lead_id>/authorize', type='http', auth='user')
    def authorize_convocatoria(self, lead_id, **kw):
        lead = request.env['crm.lead'].browse(lead_id)
        if not lead.exists():
            return request.redirect('/web')

        # Solo usuarios autorizadores
        if not request.env.user.has_group('project_extra.group_conv_authorizer'):
            return request.redirect('/web')

        # Ejecuta tu lógica existente
        lead.with_user(request.env.user).action_authorize()
        # Ir a la oportunidad para "visualizar"
        return request.redirect(f"/web#id={lead.id}&model=crm.lead&view_type=form")

    @http.route('/project_extra/convocatoria/<int:lead_id>/decline', type='http', auth='user')
    def decline_convocatoria(self, lead_id, **kw):
        lead = request.env['crm.lead'].browse(lead_id)
        if not lead.exists():
            return request.redirect('/web')

        if not request.env.user.has_group('project_extra.group_conv_authorizer'):
            return request.redirect('/web')

        lead.with_user(request.env.user).action_decline()
        return request.redirect(f"/web#id={lead.id}&model=crm.lead&view_type=form")


class BasesAuthorizationController(http.Controller):

    @http.route('/project_extra/bases/<int:lead_id>/authorize', type='http', auth='user')
    def authorize_bases(self, lead_id, **kw):
        lead = request.env['crm.lead'].browse(lead_id)
        if not lead.exists():
            return request.redirect('/web')

        # Grupo que autoriza bases (ajusta si usas otro)
        if not request.env.user.has_group('project_extra.group_conv_authorizer'):
            return request.redirect('/web')

        lead.with_user(request.env.user).action_authorize_bases()
        return request.redirect(f"/web#id={lead.id}&model=crm.lead&view_type=form")

    @http.route('/project_extra/bases/<int:lead_id>/decline', type='http', auth='user')
    def bases_decline(self, lead_id, **kw):
        lead = request.env['crm.lead'].sudo().browse(lead_id)
        if lead.exists():
            lead.action_decline_bases()
        return request.redirect('/web#id=%s&model=crm.lead&view_type=form' % lead.id)


class ConvocatoriaAuthorizationController(http.Controller):

    @http.route('/project_extra/convocatoria/<int:lead_id>/authorize', type='http', auth='user')
    def authorize_convocatoria(self, lead_id, **kw):
        # Autorizar NUEVA convocatoria desde el correo.
        lead = request.env['crm.lead'].sudo().browse(lead_id)
        if not lead.exists():
            return request.redirect('/web')

        # Solo usuarios autorizadores
        if not request.env.user.has_group('project_extra.group_conv_authorizer'):
            # Si no tiene permisos, solo lo mandamos a la vista sin hacer nada
            return request.redirect('/web#id=%s&model=crm.lead&view_type=form' % lead.id)

        lead.action_authorize()

        # Regresa al formulario para visualizar el resultado
        return request.redirect('/web#id=%s&model=crm.lead&view_type=form' % lead.id)

    @http.route('/project_extra/convocatoria/<int:lead_id>/decline', type='http', auth='user')
    def decline_convocatoria(self, lead_id, **kw):
        """Declinar NUEVA convocatoria desde el correo."""
        lead = request.env['crm.lead'].sudo().browse(lead_id)
        if not lead.exists():
            return request.redirect('/web')

        if not request.env.user.has_group('project_extra.group_conv_authorizer'):
            return request.redirect('/web#id=%s&model=crm.lead&view_type=form' % lead.id)

        lead.action_decline()

        return request.redirect('/web#id=%s&model=crm.lead&view_type=form' % lead.id)