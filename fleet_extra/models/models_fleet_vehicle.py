# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import config

_logger = logging.getLogger(__name__)


class fleetVehicleModelInherit(models.Model):
    _inherit = 'fleet.vehicle.model'

    type_id = fields.Many2one('fleet.type.equipment', string='Tipo de Equipo')


class fleetVehicleInherit(models.Model):
    _inherit = 'fleet.vehicle'

    companyresg_id = fields.Many2one('res.company', string='Resguardante')
    companyaseg_id = fields.Many2one('res.company', string='Asegurado')
    type_fleet = fields.Char(string='Tipo de Equipo', compute='_compute_type')
    code = fields.Char(string='Código interno')
    no_motor = fields.Char(string='No de Motor')
    aseguradora_id = fields.Many2one('res.partner', string='Aseguradora')
    poliza = fields.Char(string='Póliza')
    inciso = fields.Char(string='Inciso')
    eqstate_id = fields.Many2one('fleet.state.equipment', string='Estado del Equipo')

    @api.onchange('model_id')
    def _compute_type(self):
        for record in self:
            if record.model_id.type_id.name != None:
                record.type_fleet = record.model_id.type_id.name
