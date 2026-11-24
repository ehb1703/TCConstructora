# -*- coding: utf-8 -*-
from odoo.http import route
from odoo.osv import expression
from odoo.addons.hr_attendance.controllers.main import HrAttendance

SIN_DESTAJISTAS = [('tipo_personal', '!=', 'destajista')]


class HrAttendanceKioskSinDestajistas(HrAttendance):

    @route()
    def employees_infos(self, token, limit, offset, domain):
        # Modo quiosco: los destajistas checan en los relojes de obra, no aparecen en la lista para elegir
        return super().employees_infos(token, limit, offset, expression.AND([domain or [], SIN_DESTAJISTAS]))
