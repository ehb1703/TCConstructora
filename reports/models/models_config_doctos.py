# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)

class TipoDocumento(models.Model):
    _name = 'report.tipodocumento'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Tipo de documento'

    code = fields.Char(string='Código')
    name = fields.Char(string='Nombre')
    no_docto = fields.Char(string='Número de documento')
    description = fields.Text(string='Descripción')
    module_id = fields.Many2one('ir.model', string='Modelo')
    inicio_datos = fields.Integer(string = 'Fila donde inician los datos')
    configdoc_ids = fields.One2many('report.config.doc', 'config_id')
    docto_rel = fields.Many2one('report.tipodocumento', string='Documento relacionado')
    active = fields.Boolean(string='Activo', default=True, required=True)
    
    @api.constrains('name')
    def fnc_check_codigo(self):
        for x in self:
            if x:
                if x.name:
                    res = self.search([('name', '=', x.name), ('id', '!=', x.id)])
                    if res:
                        raise UserError('Ya existe el codigo')

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f'{rec.code} - {rec.name}'

    def button_configdoc(self):
        self.configdoc_ids.unlink()
        columnas = ['concepto', 'codigo', 'descripcion', 'unidad', 'precio_unitario', 'cantidad', 'importe']
        for  x in columnas:
            config = self.env['report.config.doc'].create({'columna' : x, 'config_id' : self.id})


class configdoc(models.Model):
    _name = 'report.config.doc'
    _description = 'Columnas del documento'

    config_id = fields.Many2one('report.tipodocumento', readonly=True)
    columna = fields.Char(string='Columna')
    no_columna = fields.Char(string='No. de Columna')    
