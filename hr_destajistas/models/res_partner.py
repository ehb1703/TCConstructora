# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartnerDestajista(models.Model):
    _inherit = 'res.partner'

    # Casilla junto a Es proveedor / Es cliente: solo los contactos marcados se ofrecen como "Contacto existente" en el alta
    # y sus pagos de destajo se consultan en el módulo Destajistas. El alta del destajista la marca sola.
    es_destajista = fields.Boolean(string='Es destajista', tracking=True, index=True,
        help='Marque los contactos que trabajan como destajistas en obra.')
