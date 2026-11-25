# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

GRUPO_ADMIN = 'catalogo_tc.group_admin_catalogo'


class CatalogoEquivalencia(models.Model):
    _name = 'catalogo.equivalencia'
    _description = 'Equivalencia de insumo (código externo -> insumo del catálogo)'
    _inherit = ['mail.thread']
    _order = 'fuente, codigo_externo'
    _rec_name = 'codigo_externo'

    fuente = fields.Char(string='Fuente', required=True, tracking=True, help='Origen del código: obra, empresa o base de precios que lo usa.')
    codigo_externo = fields.Char(string='Código externo', tracking=True)
    descripcion_externa = fields.Char(string='Descripción externa', required=True)
    unidad_externa = fields.Char(string='Unidad externa')
    product_tmpl_id = fields.Many2one('product.template', string='Insumo del catálogo', required=True, ondelete='restrict', tracking=True,
        domain="[('clave_insumo', '!=', False)]")
    clave_insumo_tc = fields.Char(related='product_tmpl_id.clave_insumo_tc', string='Clave TC')
    estado = fields.Selection([('confirmada', 'Confirmada'), ('pendiente', 'Pendiente de revisión')], default='confirmada', required=True, tracking=True)
    lead_id = fields.Many2one('crm.lead', string='Licitación de origen', ondelete='set null')
    active = fields.Boolean(default=True)
    fuente_norm = fields.Char(compute='_compute_norm', store=True, index=True)
    codigo_norm = fields.Char(compute='_compute_norm', store=True, index=True)
    descripcion_norm = fields.Char(compute='_compute_norm', store=True, index=True)
    unidad_norm = fields.Char(compute='_compute_norm', store=True)

    @api.depends('fuente', 'codigo_externo', 'descripcion_externa', 'unidad_externa')
    def _compute_norm(self):
        motor = self.env['catalogo.motor']
        for rec in self:
            rec.fuente_norm = motor.normalizar(rec.fuente)
            rec.codigo_norm = motor.normalizar(rec.codigo_externo) or False
            rec.descripcion_norm = motor.normalizar(rec.descripcion_externa)
            rec.unidad_norm = motor.normalizar(rec.unidad_externa)

    @api.constrains('fuente_norm', 'codigo_norm', 'active')
    def _check_unica(self):
        # Un código externo apunta a un solo insumo dentro de su fuente (en otra fuente puede significar otra cosa: MO05)
        for rec in self.filtered(lambda r: r.active and r.codigo_norm):
            otra = self.search([('id', '!=', rec.id), ('fuente_norm', '=', rec.fuente_norm), ('codigo_norm', '=', rec.codigo_norm)], limit=1)
            if otra:
                raise ValidationError(_('El código %(c)s de la fuente %(f)s ya apunta al insumo %(p)s.', c=rec.codigo_externo, f=rec.fuente, p=otra.product_tmpl_id.display_name))


class CatalogoCategoriaFamilia(models.Model):
    _name = 'catalogo.categoria.familia'
    _description = 'Combinación permitida de categoría y familia'
    _order = 'categoria_id, familia_id'

    categoria_id = fields.Many2one('product.categoria.insumo', string='Categoría', required=True, ondelete='cascade')
    familia_id = fields.Many2one('product.familia.insumo', string='Familia', required=True, ondelete='cascade')

    _sql_constraints = [('combinacion_uniq', 'unique(categoria_id, familia_id)', 'La combinación de categoría y familia ya existe.')]


class ProductTipoInsumoCatalogo(models.Model):
    _inherit = 'product.tipo.insumo'

    cuenta_gasto_id = fields.Many2one('account.account', string='Cuenta de gasto para altas', company_dependent=True, tracking=True,
        help='Cuenta de gasto que reciben los insumos nuevos de este tipo (la exige Cotizaciones). La define el Administrador del Catálogo.')
