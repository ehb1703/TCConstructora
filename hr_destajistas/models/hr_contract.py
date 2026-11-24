# -*- coding: utf-8 -*-
from odoo import api, models, _
from odoo.exceptions import ValidationError


class HrContractDestajista(models.Model):
    _inherit = 'hr.contract'

    @api.constrains('employee_id')
    def _check_no_destajista(self):
        for contrato in self:
            if contrato.employee_id.tipo_personal == 'destajista':
                raise ValidationError(_('%s es destajista: los destajistas no llevan contrato ni participan en la nómina.', contrato.employee_id.name))
