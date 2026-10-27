# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api, _

def update_data(cr):
    cr.execute('''INSERT INTO product_budget_item_line (item_id, company_id, lead_id, name)
SELECT cbl.budget_id, cl.company_id, cl.id, cbl.col2  
  FROM crm_budget_line cbl JOIN crm_lead cl ON cbl.lead_id = cl.ID;  ''')


def migrate(cr, version):
    if not version:
        return
    update_data(cr)