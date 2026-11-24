# -*- coding: utf-8 -*-
from odoo import api, models


class IrSequenceDestajista(models.Model):
    _inherit = 'ir.sequence'

    @api.model
    def next_by_code(self, sequence_code, sequence_date=None):
        # El alta de empleados de hr_extra toma su número de 'numemployee'; para un destajista se usa la serie D0001 sin gastar números de empleado
        if sequence_code == 'numemployee' and self.env.context.get('alta_destajista'):
            sequence_code = 'hr.destajista'
        return super().next_by_code(sequence_code, sequence_date=sequence_date)
