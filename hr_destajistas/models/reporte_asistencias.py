# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.addons.hr_extra.models.hr_employee import _get_encargado_nomina_usuario
from odoo.exceptions import UserError

GRUPO = 'hr_destajistas.group_destajistas'


class WizardReporteAsistenciasDestajista(models.TransientModel):
    _inherit = 'wizard.reporte.asistencias'

    filtro_personal = fields.Selection([('ambos', 'Empleados y destajistas'), ('empleados', 'Solo empleados'), ('destajistas', 'Solo destajistas')],
        string='Personal', default='ambos', required=True)

    @api.depends('filtro_personal')
    def _compute_mostrar_tipo_pago(self):
        # En hr_extra el cálculo no tiene dependencias y la pantalla nunca lo ejecuta: el encargado de "ambas" no veía el Tipo de pago.
        # Con el filtro como dependencia se calcula al abrir; para "Solo destajistas" no aplica (no hay nómina).
        enc = _get_encargado_nomina_usuario(self.env)
        for record in self:
            record.mostrar_tipo_pago = enc == 'ambas' and record.filtro_personal != 'destajistas'

    def _url_reporte(self):
        if self.fecha_inicio > self.fecha_fin:
            raise UserError(_('La fecha inicial no puede ser mayor a la fecha final.'))
        return {'type': 'ir.actions.act_url', 'url': '/web/binary/hr_reporte_asistencias?wizard_id=%s' % self.id, 'target': 'new'}

    def action_generar_excel(self):
        # El grupo Destajistas (Administración) genera el reporte de destajistas aunque no sea de RRHH ni encargado de nómina
        usuario = self.env.user
        if usuario.has_group(GRUPO) and not usuario.has_group('base.group_system') and not usuario.has_group('hr.group_hr_manager') \
                and not self._get_enc_usuario():
            self.filtro_personal = 'destajistas'
            return self._url_reporte()
        if self.filtro_personal == 'destajistas' and (usuario.has_group(GRUPO) or usuario.has_group('base.group_system')
                                                     or usuario.has_group('hr.group_hr_manager') or self._get_enc_usuario()):
            return self._url_reporte()   # solo destajistas: no se pide tipo de pago de nómina
        return super().action_generar_excel()
