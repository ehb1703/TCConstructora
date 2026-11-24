# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartnerDestajista(models.Model):
    _inherit = 'res.partner'

    es_destajista = fields.Boolean(string='Destajista (Requisiciones)', compute='_compute_es_destajista', search='_search_es_destajista',
        help='Contacto que ya se paga como destajista en Requisiciones → Destajos.')

    def _ids_destajistas(self):
        self.env.cr.execute('SELECT DISTINCT partner_id FROM requisition_destajo WHERE partner_id IS NOT NULL')
        return [r[0] for r in self.env.cr.fetchall()]

    def _compute_es_destajista(self):
        ids = set(self._ids_destajistas())
        for partner in self:
            partner.es_destajista = partner.id in ids

    def _search_es_destajista(self, operator, value):
        dentro = (operator == '=') == bool(value)
        return [('id', 'in' if dentro else 'not in', self._ids_destajistas())]
