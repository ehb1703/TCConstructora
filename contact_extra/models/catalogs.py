# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class cls_municipios(models.Model):
    _name = 'res.municipalities'
    _rec_name = 'municipio'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Municipios'
    
    codigo = fields.Char(string='Código del Municipio', tracking=True, required=True)
    municipio = fields.Char(string='Municipio', tracking=True, required=True)
    state_id = fields.Many2one('res.country.state', string='Estado', tracking=True, required=True)
    active = fields.Boolean(String='Activo', default=True, tracking=True)
    
    def name_get(self):
        res = []
        if self._context.get('special_display_name', False):
            for record in self:
                res.append((record.id,record.codigo.encode('utf-8') ))
        else:
            for municipio in self:
                for mun in municipio:
                    if mun.codigo and mun.municipio:
                        res.append((mun.id,mun.codigo.encode('utf-8')+' '+mun.municipio.encode('utf-8')))
                    else:
                         res.append((mun.id,str(mun.codigo)+' '+str(mun.municipio)))
        return res
    
    @api.constrains('municipio')
    def fnc_check_municipio(self):
        for x in self:
            if x.municipio:
                res = self.search([('municipio','=',x.municipio),('state_id','=',x.state_id.id),('id','!=',x.id)])
                if res:
                    raise ValidationError("Ya existe un municipio igual")                

    @api.onchange("municipio")
    def onchange_municipio(self):
        if self.municipio:                       
            nvacadena = self.municipio.strip(" ")            
            if len(nvacadena)==0:
                warning = {'title': 'Advertencia',
                        'message': 'El nombre del municipio es incorrecto, favor de verificar',}
                return {'warning':warning}
            self.municipio = nvacadena.upper()


class tipoContribuyente(models.Model):
    _name = 'company.type.taxpayer'
    _description = 'Tipo de Contribuyente'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    
    name = fields.Char(string='Tipo de Contribuyente')
    description = fields.Char(string='Descripción')
    active = fields.Boolean(String='Activo', default=True, tracking=True)


class tipoProveedor(models.Model):
    _name = 'partner.type.supplier'
    _description = 'Tipo de Proveedor'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    
    name = fields.Char(string='Tipo de Proveedor')
    description = fields.Char(string='Descripción')
    active = fields.Boolean(String='Activo', default=True, tracking=True)    