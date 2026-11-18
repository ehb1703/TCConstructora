# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID
from odoo.addons.gestion_obras.hooks import asignar_matriz_autorizaciones


def migrate(cr, version):
    # T0120: asigna la matriz de autorizaciones y pasa a su nivel a quienes estaban en los grupos anteriores (que se eliminan al terminar)
    asignar_matriz_autorizaciones(api.Environment(cr, SUPERUSER_ID, {}))
