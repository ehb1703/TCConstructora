# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)

class CatalogoGastos(models.Model):
    _name = 'account.catalog.expense'
    _description = 'Catálogo de Gastos'
    _rec_name = 'nombre_categoria'

    tipo_formato = fields.Selection([('tipo1','Tipo 1'),('tipo2','Tipo 2')], string='Tipo / Formato')
    descripcion = fields.Text('Descripción')
    codigo_categoria = fields.Char('Código de categoría', required=True)
    nombre_categoria = fields.Char('Nombre de categoría', required=True)
    descripcion_detallada = fields.Text('Descripción detallada')
    active = fields.Boolean(string='Activo', default=True)

    _sql_constraints = [('codigo_categoria_uniq','unique(codigo_categoria)','El código de categoría debe ser único.')]


class cls_municipios(models.Model):
    _name = 'res.municipalities'
    _rec_name = 'municipio'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Municipios'
    
    codigo = fields.Char(string='Código del Municipio', tracking=True, required=True)
    municipio = fields.Char(string='Municipio', tracking=True, required=True)
    state_id = fields.Many2one('res.country.state', string='Estado', tracking=True, required=True)
    active = fields.Boolean(string='Activo', default=True, tracking=True)
    
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
    active = fields.Boolean(string='Activo', default=True, tracking=True)


class tipoProveedor(models.Model):
    _name = 'partner.type.supplier'
    _description = 'Tipo de Proveedor'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    
    name = fields.Char(string='Tipo de Proveedor')
    description = fields.Char(string='Descripción')
    active = fields.Boolean(string='Activo', default=True, tracking=True)


class clasificacionProveedor(models.Model):
    _name = 'partner.classification.supplier'
    _description = 'Clasificación del Proveedor'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    
    name = fields.Char(string='Clasificación del Proveedor')
    description = fields.Char(string='Descripción')
    active = fields.Boolean(string='Activo', default=True, tracking=True)    
