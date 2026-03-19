# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class RequisitionHrSolicitud(models.Model):
    _name = 'requisition.hr.solicitud'
    _description = 'Solicitudes de Alta/Baja de Personal'
    _order = 'fecha_aplicacion desc, id desc'

    nombre = fields.Char(string='Nombre(s)', required=True)
    apellido_paterno = fields.Char(string='Apellido paterno', required=True)
    apellido_materno = fields.Char(string='Apellido materno')
    codigo_postal = fields.Char(string='Código postal')
    tipo_tramite = fields.Selection(selection=[('alta', 'Alta'), ('baja', 'Baja')], string='Tipo de Trámite', required=True)
    fecha_aplicacion = fields.Date(string='Fecha de aplicación')
    nss = fields.Char(string='NSS')
    rfc = fields.Char(string='RFC')
    curp = fields.Char(string='CURP')
    genero = fields.Selection(selection=[('masculino', 'Masculino'), ('femenino', 'Femenino')], string='Género')
    fecha_nacimiento = fields.Date(string='Fecha de nacimiento')
    ciudad_nacimiento = fields.Char(string='Ciudad de nacimiento')
    observaciones = fields.Char(string='Observaciones')

    @api.constrains('nss')
    def _check_nss(self):
        for rec in self:
            if rec.nss and (' ' in rec.nss or '-' in rec.nss):
                raise ValidationError('El NSS no puede contener guiones ni espacios.')

    @api.constrains('curp')
    def _check_curp(self):
        for rec in self:
            if rec.curp:
                if ' ' in rec.curp or '-' in rec.curp:
                    raise ValidationError('El CURP no puede contener guiones ni espacios.')
                if len(rec.curp) != 18:
                    raise ValidationError('El CURP debe tener exactamente 18 caracteres.')