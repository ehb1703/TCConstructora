# -*- coding: utf-8 -*-
import collections
from odoo import api, fields, models, _
from odoo.exceptions import UserError

GRUPO_ADMIN = 'catalogo_tc.group_admin_catalogo'


class CatalogoAltaWizard(models.TransientModel):
    _name = 'catalogo.alta.wizard'
    _description = 'Alta asistida de insumo en el catálogo'

    linea_id = fields.Many2one('crm.input.line', string='Renglón de la licitación')
    codigo_externo = fields.Char(related='linea_id.col1', string='Código de la obra')
    descripcion_externa = fields.Char(related='linea_id.col2', string='Descripción de la obra')
    accion = fields.Selection([('nuevo', 'Dar de alta un insumo nuevo'), ('existente', 'Es un insumo que ya existe')], string='Acción', default='nuevo', required=True)
    clave_proxima = fields.Char(string='Clave que recibirá', compute='_compute_clave_proxima')
    existente_id = fields.Many2one('product.template', string='Insumo existente', domain="[('clave_insumo', '!=', False)]")
    nombre = fields.Char(string='Nombre estandarizado')
    uom_id = fields.Many2one('uom.uom', string='Unidad')
    tipo_id = fields.Many2one('product.tipo.insumo', string='Tipo')
    categoria_id = fields.Many2one('product.categoria.insumo', string='Categoría')
    familia_id = fields.Many2one('product.familia.insumo', string='Familia')
    duplicado_ids = fields.Many2many('product.template', compute='_compute_duplicados', string='Posibles duplicados')

    @api.model
    def default_get(self, campos):
        res = super().default_get(campos)
        linea = self.env['crm.input.line'].browse(res.get('linea_id') or self.env.context.get('default_linea_id'))
        if linea:
            motor = self.env['catalogo.motor']
            res['nombre'] = motor.normalizar(linea.col2)
            unidad = linea[linea.lead_id._columnas_insumos()[1]] if linea.lead_id else False
            uom = self.env['catalogo.importador'].unidad(unidad) if unidad else False
            if uom:
                res['uom_id'] = uom.id
            categoria, familia = self._sugerir_clasificacion(res['nombre'])
            res.update({'categoria_id': categoria.id, 'familia_id': familia.id})
            if linea.sugerencia_id:
                res['existente_id'] = linea.sugerencia_id.id
        return res

    @api.model
    def _sugerir_clasificacion(self, nombre):
        """Familia cuyo nombre aparece en la descripción y categoría donde esa familia ya se usa (prueba 6b: 61%/41% de acierto: se confirma)."""
        motor = self.env['catalogo.motor']
        palabras = {p[:5] for p in motor.palabras(nombre)}
        mejor, puntos = self.env['product.familia.insumo'], 0.0
        for fam in self.env['product.familia.insumo'].search([]):
            raices = {p[:5] for p in motor.palabras(fam.name)}
            if raices and palabras & raices and len(palabras & raices) / len(raices) > puntos:
                mejor, puntos = fam, len(palabras & raices) / len(raices)
        categoria = self.env['product.categoria.insumo']
        if mejor:
            usos = collections.Counter(self.env['catalogo.categoria.familia'].search([('familia_id', '=', mejor.id)]).mapped('categoria_id'))
            categoria = usos.most_common(1)[0][0] if usos else categoria
        return categoria, mejor

    @api.depends('tipo_id', 'categoria_id', 'familia_id')
    def _compute_clave_proxima(self):
        consecutivo = self.env['product.template'].sudo().proxima_clave()
        for wiz in self:
            partes = [wiz.tipo_id.codigo, wiz.categoria_id.codigo, wiz.familia_id.codigo]
            wiz.clave_proxima = '-'.join(x or '___' for x in partes) + '-' + consecutivo

    @api.depends('nombre', 'uom_id', 'categoria_id')
    def _compute_duplicados(self):
        for wiz in self:
            wiz.duplicado_ids = self.env['product.template'].buscar_duplicados(wiz.nombre, wiz.uom_id, wiz.categoria_id) if wiz.nombre and wiz.uom_id else False

    def action_aplicar(self):
        self.ensure_one()
        if self.accion == 'existente':
            if not self.existente_id:
                raise UserError(_('Elija el insumo existente.'))
            producto = self.existente_id
        else:
            if not self.env.user.has_group(GRUPO_ADMIN):
                raise UserError(_('Solo el Administrador del Catálogo puede dar de alta insumos.'))
            if not all([self.nombre, self.uom_id, self.tipo_id, self.categoria_id, self.familia_id]):
                raise UserError(_('Capture nombre, unidad, tipo, categoría y familia.'))
            motor = self.env['catalogo.motor']
            iva = self.env['account.tax'].search([('type_tax_use', '=', 'purchase'), ('amount', '=', 16), ('company_id', '=', self.env.company.id)], limit=1)
            producto = self.env['product.template'].create({
                'name': motor.normalizar(self.nombre), 'uom_id': self.uom_id.id, 'uom_po_id': self.uom_id.id,
                'type': 'consu' if self.tipo_id.codigo == '001' else 'service', 'purchase_ok': True, 'sale_ok': False,
                'tipo_insumo_id': self.tipo_id.id, 'categoria_insumo_id': self.categoria_id.id, 'familia_insumo_id': self.familia_id.id,
                'clave_insumo': self.env['product.template'].siguiente_clave(), 'supplier_taxes_id': [(6, 0, iva.ids)],
                **({'property_account_expense_id': self.tipo_id.cuenta_gasto_id.id} if self.tipo_id.cuenta_gasto_id else {})})
        if self.linea_id:
            self.linea_id._ligar_insumo(producto)
        return {'type': 'ir.actions.act_window', 'res_model': 'product.template', 'res_id': producto.id, 'view_mode': 'form', 'target': 'current'} \
            if not self.linea_id else {'type': 'ir.actions.act_window_close'}
