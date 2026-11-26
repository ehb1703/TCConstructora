# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID
from odoo.addons.gestion_obras.hooks import adoptar_kontrol


def migrate(cr, version):
    # T0110 entra a gestion_obras: adopta lo que ya exista (de analytic_kontrol, project_extra o capturado a mano)
    adoptar_kontrol(api.Environment(cr, SUPERUSER_ID, {}))
