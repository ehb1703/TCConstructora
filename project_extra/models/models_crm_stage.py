# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

class crmStageOrigen(models.Model):
    _name = 'crm.stage.origen'
    _description = 'Origen'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char('Origen', tracking=True)
    description = fields.Char('Descripción')
    active = fields.Boolean('Activo', default=True)


class crmStageOrigen(models.Model):
    _inherit = 'crm.stage'
    
    origen_ids = fields.Many2many('crm.stage.origen', string='Origen permitido')