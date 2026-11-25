# -*- coding: utf-8 -*-
import logging
from datetime import datetime
from odoo import api, models

_logger = logging.getLogger(__name__)
# Lo que el checador puede corregir al reenviar una checada que aún no se procesa
CAMPOS_REENVIO = ('photo_url', 'latitude', 'longitude', 'lateness_time', 'left_early_time', 'is_active', 'verification_status',
                  'match_percentage', 'log_message', 'sigob_log_folio')


class CtrolAsistenciasDestajista(models.Model):
    _inherit = 'ctrol.asistencias'

    def _validate_for_import(self):
        valido, mensaje = super()._validate_for_import()
        if valido or not mensaje.startswith('Sin contrato activo'):
            return valido, mensaje
        empleado = self._get_employee_from_registration()
        if empleado.tipo_personal != 'destajista':
            return valido, mensaje
        # Un destajista no tiene contrato (no participa en nómina): se aplican las demás validaciones del proceso original
        if not self.check_date or not isinstance(self.check_date, datetime):
            return (False, 'Formato de fecha inválido | check_date es nulo o no es fecha')
        if self.check_type not in ('entrada', 'salida'):
            return (False, f'check_type inválido | Valor recibido: "{self.check_type}" | Valores permitidos: entrada, salida')
        return (True, '')

    @api.model
    def create_from_checador(self, vals):
        """Actualiza en vez de insertar cuando el checador reenvía la misma checada (mismo número, tipo y fecha-hora exactas, o mismo folio).
        Una checada ya importada a asistencia no se toca: se devuelve la existente."""
        previa = self._checada_previa(vals)
        if not previa:
            return super().create_from_checador(vals)
        if previa.log_status == 'importada':
            _logger.info('Checada reenviada ya importada | ID %s | %s %s', previa.id, previa.registration_number, previa.check_date_local)
            return previa
        cambios = {c: vals[c] for c in CAMPOS_REENVIO if c in vals}
        if previa.log_status == 'error':
            cambios['log_status'] = 'pendiente'   # se reintenta con los datos corregidos
        cambios['updatedAt'] = datetime.now()
        previa.write(cambios)
        _logger.info('Checada reenviada actualizada | ID %s | %s %s', previa.id, previa.registration_number, previa.check_date_local)
        return previa

    @api.model
    def _checada_previa(self, vals):
        if vals.get('sigob_log_folio'):
            previa = self.search([('sigob_log_folio', '=', vals['sigob_log_folio'])], limit=1)
            if previa:
                return previa
        if not (vals.get('registration_number') and vals.get('check_type') and vals.get('check_date')):
            return self.browse()
        fecha = str(vals['check_date']).replace('T', ' ').replace('Z', '').split('.')[0].strip()
        try:
            local = datetime.strptime(fecha, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            try:
                local = datetime.strptime(fecha, '%Y-%m-%d %H:%M')
            except ValueError:
                return self.browse()
        utc = self._local_to_utc(local, self._get_checador_tz())
        return self.search([('registration_number', '=', vals['registration_number']), ('check_type', '=', vals['check_type']),
                            ('check_date', '=', utc.strftime('%Y-%m-%d %H:%M:%S'))], order='id', limit=1)
