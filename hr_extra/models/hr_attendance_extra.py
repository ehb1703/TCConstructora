# -*- coding: utf-8 -*-
from odoo import fields, models

class HrAttendanceOvertimeExtra(models.Model):
    _inherit = 'hr.attendance.overtime'

    attendance_id = fields.Many2one('hr.attendance', string='Asistencia', ondelete='set null', help='Registro hr.attendance relacionado con este overtime')
    reason = fields.Char(string='Razón', help='Motivo del overtime (ej: Retraso en entrada: 01:30)')