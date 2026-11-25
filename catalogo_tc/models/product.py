# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.osv import expression
from odoo.exceptions import UserError, ValidationError

GRUPO_ADMIN = 'catalogo_tc.group_admin_catalogo'
CAMPOS_CLASIFICACION = {'tipo_insumo_id', 'categoria_insumo_id', 'familia_insumo_id', 'clave_insumo'}


class ProductTemplateCatalogo(models.Model):
    _inherit = 'product.template'

    equivalencia_ids = fields.One2many('catalogo.equivalencia', 'product_tmpl_id', string='Equivalencias')
    equivalencia_count = fields.Integer(compute='_compute_equivalencia_count', string='Núm. de equivalencias')

    def _compute_equivalencia_count(self):
        datos = {p.id: n for p, n in self.env['catalogo.equivalencia']._read_group([('product_tmpl_id', 'in', self.ids)], ['product_tmpl_id'], ['__count'])}
        for rec in self:
            rec.equivalencia_count = datos.get(rec.id, 0)

    def _exigir_admin(self):
        # La clasificación y la clave solo las cambia el Administrador del Catálogo (los procesos internos usan sudo)
        if not self.env.su and not self.env.user.has_group(GRUPO_ADMIN):
            raise UserError(_('Solo el Administrador del Catálogo puede clasificar insumos o asignar su clave.'))

    @api.model_create_multi
    def create(self, vals_list):
        if any(CAMPOS_CLASIFICACION & set(v) and any(v.get(c) for c in CAMPOS_CLASIFICACION) for v in vals_list):
            self._exigir_admin()
        productos = super().create(vals_list)
        productos._sincronizar_referencia()
        return productos

    def write(self, vals):
        if CAMPOS_CLASIFICACION & set(vals):
            self._exigir_admin()
        res = super().write(vals)
        if CAMPOS_CLASIFICACION & set(vals) or 'default_code' in vals:
            self._sincronizar_referencia()
        return res

    def _sincronizar_referencia(self):
        """La referencia interna de un insumo del catálogo es su Clave TC (nunca el código de una obra)."""
        for rec in self.filtered(lambda p: p.clave_insumo_tc and p.default_code != p.clave_insumo_tc):
            super(ProductTemplateCatalogo, rec).write({'default_code': rec.clave_insumo_tc})

    @api.constrains('categoria_insumo_id', 'familia_insumo_id')
    def _check_combinacion(self):
        # Regla de gobierno para personas; las cargas y procesos del sistema (superusuario) la registran ellos mismos
        if self.env.su:
            return
        Combo = self.env['catalogo.categoria.familia'].sudo()
        for rec in self.filtered(lambda p: p.categoria_insumo_id and p.familia_insumo_id):
            if not Combo.search_count([('categoria_id', '=', rec.categoria_insumo_id.id), ('familia_id', '=', rec.familia_insumo_id.id)]):
                raise ValidationError(_('La familia %(f)s no está permitida en la categoría %(c)s. El Administrador del Catálogo debe autorizar la combinación.',
                                        f=rec.familia_insumo_id.display_name, c=rec.categoria_insumo_id.display_name))

    def action_nuevo_insumo(self):
        # Botón de encabezado de lista: Odoo lo llama con los registros seleccionados (puede ser ninguno)
        """El alta de insumos pasa siempre por el asistente: asigna la clave consecutiva y avisa de duplicados."""
        return {'type': 'ir.actions.act_window', 'name': _('Nuevo insumo'), 'res_model': 'catalogo.alta.wizard', 'view_mode': 'form', 'target': 'new'}

    def action_importar_insumos(self):
        return self.env['ir.actions.act_window']._for_xml_id('catalogo_tc.action_catalogo_importar_wizard')

    @api.model
    def proxima_clave(self):
        """Consulta (sin consumir) el consecutivo que recibirá la siguiente alta."""
        usados = self.with_context(active_test=False).search([('clave_insumo', '!=', False)]).mapped('clave_insumo')
        maximo = max([int(c) for c in usados if c.isdigit()] or [0])
        seq = self.env['ir.sequence'].sudo().search([('code', '=', 'catalogo.insumo.clave')], limit=1)
        return '%05d' % max(maximo + 1, seq.number_next_actual)

    @api.model
    def siguiente_clave(self):
        """Siguiente consecutivo de 5 dígitos; nunca reutiliza uno ya usado (aunque el insumo se haya fusionado o archivado)."""
        usados = self.with_context(active_test=False).search([('clave_insumo', '!=', False)]).mapped('clave_insumo')
        maximo = max([int(c) for c in usados if c.isdigit()] or [0])
        seq = self.env['ir.sequence'].sudo().search([('code', '=', 'catalogo.insumo.clave')], limit=1)
        if seq.number_next_actual <= maximo:
            seq.number_next = maximo + 1
        return seq.next_by_id()

    def buscar_duplicados(self, nombre, uom, categoria=False, familia=False):
        """Insumos que podrían ser el mismo: misma unidad, mismos atributos y nombre parecido (lista para revisión, nunca se fusiona solo)."""
        motor = self.env['catalogo.motor']
        firma = motor.firma(nombre)
        dominio = [('clave_insumo', '!=', False), ('uom_id', '=', uom.id)]
        if categoria:
            dominio.append(('categoria_insumo_id', '=', categoria.id))
        return self.search(dominio).filtered(lambda p: motor.firma(p.name) == firma and motor.parecido(p.name, nombre) >= 0.5)

    def action_ver_equivalencias(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': _('Equivalencias'), 'res_model': 'catalogo.equivalencia', 'view_mode': 'list,form',
                'domain': [('product_tmpl_id', '=', self.id)], 'context': {'default_product_tmpl_id': self.id}}


class ProductProductCatalogo(models.Model):
    _inherit = 'product.product'

    def _search_display_name(self, operator, value):
        """El código de obra (equivalencia) también encuentra el insumo, como antes cuando era la referencia interna."""
        domain = super()._search_display_name(operator, value)
        if isinstance(value, str) and value and operator not in expression.NEGATIVE_TERM_OPERATORS:
            domain = expression.OR([domain, [('product_tmpl_id.equivalencia_ids.codigo_externo', operator, value)]])
        return domain

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        res = super().name_search(name, args, operator, limit)
        if name and operator not in expression.NEGATIVE_TERM_OPERATORS and (not limit or len(res) < limit):
            ya = [r[0] for r in res]
            eqs = self.env['catalogo.equivalencia'].search([('codigo_norm', '=', self.env['catalogo.motor'].normalizar(name))])
            extra = self.search_fetch(expression.AND([args or [], [('product_tmpl_id', 'in', eqs.product_tmpl_id.ids), ('id', 'not in', ya)]]),
                                      ['display_name'], limit=limit and limit - len(res))
            res += [(p.id, p.display_name) for p in extra]
        return res
