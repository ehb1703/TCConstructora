# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrParentesco(models.Model):
    _name = 'hr.parentesco'
    _description = 'Parentesco'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'nombre'
    _order = 'codigo'

    codigo = fields.Char(string='Código', required=True, tracking=True)
    nombre = fields.Char(string='Nombre del parentesco', required=True, tracking=True)
    descripcion = fields.Text(string='Descripción detallada', tracking=True,)
    active = fields.Boolean(string='Activo', default=True, tracking=True)

    _sql_constraints = [('codigo_uniq', 'unique(codigo)', 'El código del parentesco debe ser único.'),]

    @api.depends('codigo', 'nombre')
    def _compute_display_name(self):
        for rec in self:
            if rec.codigo and rec.nombre:
                rec.display_name = f'{rec.codigo} - {rec.nombre}'
            else:
                rec.display_name = rec.nombre or rec.codigo or ''


class HrContractBeneficiario(models.Model):
    _name = 'hr.contract.beneficiario'
    _description = 'Beneficiario de Contrato'
    _order = 'contract_id, id'

    contract_id = fields.Many2one('hr.contract', string='Contrato', required=True)
    nombre_id = fields.Many2one('res.partner', string='Nombre', required=True, domain="[('is_company', '=', False)]",)
    parentesco_id = fields.Many2one('hr.parentesco', string='Parentesco', required=True)
    porcentaje = fields.Integer(string='Porcentaje', required=True, default=0)

    @api.constrains('porcentaje')
    def _check_porcentaje(self):
        for rec in self:
            if rec.porcentaje < 0 or rec.porcentaje > 100:
                raise ValidationError(_('El porcentaje debe estar entre 0 y 100.'))


class HrContractEmpresa(models.Model):
    _name = 'hr.contract.empresa'
    _description = 'Empresas para contratos'
    _order = 'tipo_contrato_id, id'

    tipo_contrato_id = fields.Many2one('hr.contract.type', string='Tipo de contrato', required=True)
    empresa_id = fields.Many2one('res.partner', string='Empresa', required=True, 
        domain="[('is_company', '=', True), ('typesupplier_id.name', 'ilike', 'RH')]",)
    fecha_inicio = fields.Date(string='Fecha Inicio')
    fecha_fin = fields.Date(string='Fecha Final')


class HrJob(models.Model):
    _inherit = 'hr.job'

    descripcion_puesto = fields.Text(string='Descripción del puesto')
