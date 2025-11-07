# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

class crmStageOrigen(models.Model):
    _name = 'crm.lead.type'
    _description = 'Tipo de Venta'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char(string='Tipo', tracking=True)
    description = fields.Char(string='Descripción')
    bases = fields.Boolean(string='Bases', default=False)
    active = fields.Boolean(string='Activo', default=True)


class crmStageOrigen(models.Model):
    _inherit = 'crm.stage'
    
    origen_ids = fields.Many2many('crm.lead.type', string='Tipo de venta permitido')


class purchaseCRMLEAD(models.Model):
    _inherit = 'purchase.order'

    lead_id = fields.One2many('crm.lead', 'oc_id', string='Oportudidad')