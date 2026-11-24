# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.osv import expression

from .hr_employee import TIPOS_PERSONAL

SIN_DESTAJISTAS = [('tipo_personal', '!=', 'destajista')]

# Los destajistas no se eligen en Asistencias ni en Nómina: se consultan solo en el módulo Destajistas.
# Se conservan los dominios que ya pone hr_extra (finiquito y empresa) y se agrega la condición de tipo de personal.


class HrAttendanceSinDestajistas(models.Model):
    _inherit = 'hr.attendance'

    employee_id = fields.Many2one(domain=[('finiquito', '=', False)] + SIN_DESTAJISTAS)


class HrContractSinDestajistas(models.Model):
    _inherit = 'hr.contract'

    employee_id = fields.Many2one(domain="[('finiquito', '=', False), '|', ('company_id', '=', False), ('company_id', '=', company_id), "
                                         "('tipo_personal', '!=', 'destajista')]")


class HrPayslipSinDestajistas(models.Model):
    _inherit = 'hr.payslip'

    employee_id = fields.Many2one(domain="[('finiquito', '=', False), '|', ('company_id', '=', False), ('company_id', '=', company_id), "
                                         "'|', ('active', '=', True), ('active', '=', False), ('tipo_personal', '!=', 'destajista')]")


class RequisitionDestajoConsulta(models.Model):
    _inherit = 'requisition.destajo'

    # Datos de la requisición para la consulta de pagos en el módulo Destajistas (los campos relacionados se leen con sudo,
    # así el grupo Destajistas no necesita acceso a las requisiciones)
    destajo_requisicion = fields.Char(string='Requisición', related='req_id.name')
    destajo_obra = fields.Char(string='Obra', related='req_id.project_id.name')
    destajo_periodo_inicio = fields.Date(string='Periodo inicial', related='req_id.finicio')
    destajo_periodo_fin = fields.Date(string='Periodo final', related='req_id.ffinal')
    destajo_tipo = fields.Char(string='Tipo de destajo', related='destajo_id.nombre')



# Toda pantalla de Odoo que busca, lista o deja elegir empleados (listas, kanban, organigrama, "Buscar más…" y las listas de
# selección de cualquier aplicación) excluye destajistas, salvo que pida verlos con el contexto 'mostrar_destajistas': solo el
# módulo Destajistas y el filtro del reporte de asistencias lo hacen. No afecta búsquedas internas (API de checadores,
# procesamiento de checadas, cálculos), que usan search().


class HrEmployeeOcultarEnPantalla(models.Model):
    _inherit = 'hr.employee'

    def _dominio_pantalla(self, domain):
        if self.env.context.get('mostrar_destajistas'):
            return domain or []
        return expression.AND([domain or [], SIN_DESTAJISTAS])

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        return super().name_search(name=name, args=self._dominio_pantalla(args), operator=operator, limit=limit)

    @api.model
    def web_search_read(self, domain, specification, offset=0, limit=None, order=None, count_limit=None):
        return super().web_search_read(self._dominio_pantalla(domain), specification, offset=offset, limit=limit, order=order, count_limit=count_limit)

    @api.model
    def web_read_group(self, domain, fields, groupby, limit=None, offset=0, orderby=False, lazy=True):
        return super().web_read_group(self._dominio_pantalla(domain), fields, groupby, limit=limit, offset=offset, orderby=orderby, lazy=lazy)

    @api.model
    def hierarchy_read(self, domain, fields, parent_field, child_field=None, order=None):
        return super().hierarchy_read(self._dominio_pantalla(domain), fields, parent_field, child_field=child_field, order=order)

    # Contadores del panel lateral (Empresa / Departamento) en Empleados y Organigrama
    @api.model
    def search_panel_select_range(self, field_name, **kwargs):
        kwargs['search_domain'] = self._dominio_pantalla(kwargs.get('search_domain'))
        return super().search_panel_select_range(field_name, **kwargs)

    @api.model
    def search_panel_select_multi_range(self, field_name, **kwargs):
        kwargs['search_domain'] = self._dominio_pantalla(kwargs.get('search_domain'))
        return super().search_panel_select_multi_range(field_name, **kwargs)


class HrEmployeePublicOcultarEnPantalla(models.Model):
    # Versión de empleados que ven quienes no son de RRHH (gerentes, ausencias, etc.): se le agrega el tipo de personal
    _inherit = 'hr.employee.public'

    tipo_personal = fields.Selection(TIPOS_PERSONAL, string='Tipo de personal', readonly=True)

    def _dominio_pantalla(self, domain):
        if self.env.context.get('mostrar_destajistas'):
            return domain or []
        return expression.AND([domain or [], SIN_DESTAJISTAS])

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        return super().name_search(name=name, args=self._dominio_pantalla(args), operator=operator, limit=limit)

    @api.model
    def web_search_read(self, domain, specification, offset=0, limit=None, order=None, count_limit=None):
        return super().web_search_read(self._dominio_pantalla(domain), specification, offset=offset, limit=limit, order=order, count_limit=count_limit)

    @api.model
    def web_read_group(self, domain, fields, groupby, limit=None, offset=0, orderby=False, lazy=True):
        return super().web_read_group(self._dominio_pantalla(domain), fields, groupby, limit=limit, offset=offset, orderby=orderby, lazy=lazy)

    @api.model
    def hierarchy_read(self, domain, fields, parent_field, child_field=None, order=None):
        return super().hierarchy_read(self._dominio_pantalla(domain), fields, parent_field, child_field=child_field, order=order)

    # Contadores del panel lateral (Empresa / Departamento) en Empleados y Organigrama
    @api.model
    def search_panel_select_range(self, field_name, **kwargs):
        kwargs['search_domain'] = self._dominio_pantalla(kwargs.get('search_domain'))
        return super().search_panel_select_range(field_name, **kwargs)

    @api.model
    def search_panel_select_multi_range(self, field_name, **kwargs):
        kwargs['search_domain'] = self._dominio_pantalla(kwargs.get('search_domain'))
        return super().search_panel_select_multi_range(field_name, **kwargs)
