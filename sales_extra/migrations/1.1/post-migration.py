# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api, _

def update_data(cr):
    cr.execute('''INSERT INTO product_budget_item_line (item_id, company_id, lead_id, name)
SELECT cbl.budget_id, cl.company_id, cl.id, cbl.col2  
  FROM crm_budget_line cbl JOIN crm_lead cl ON cbl.lead_id = cl.ID;

UPDATE product_template SET budget_id = null WHERE id IN (SELECT pt.id FROM product_template pt JOIN product_budget_item pbi ON pt.budget_id = pbi.id 
 WHERE NOT EXISTS(SELECT * FROM product_budget_item_line pbil WHERE pbi.id = pbil.item_id));

DELETE FROM product_budget_item pbi 
 WHERE NOT EXISTS(SELECT * FROM product_budget_item_line pbil WHERE pbi.id = pbil.item_id) 
   AND NOT EXISTS(SELECT * FROM product_template pt WHERE pbi.id = pt.budget_id); ''')


def migrate(cr, version):
    if not version:
        return
    update_data(cr)
