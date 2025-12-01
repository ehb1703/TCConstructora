# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api, _

def update_data(cr):
    cr.execute('''CREATE OR REPLACE FUNCTION public.carga_partidas(character varying, integer)
RETURNS text
LANGUAGE plpgsql
AS $function$

DECLARE    
    
    lead ALIAS FOR $1;
    user ALIAS FOR $2;
    x RECORD;
    y RECORD;
    counter INTEGER = 1;
    i INTEGER;
    num INTEGER;
    cad CHARACTER VARYING;
    idpart INTEGER;
   
BEGIN
    --raise notice ' % %', num, cad;

    UPDATE crm_budget_line SET NO_CHAR = LENGTH(COL1) WHERE LEAD_ID = lead;

    UPDATE crm_budget_line cbl SET NO_CHAR = t1.NUM 
      FROM (SELECT NO_CHAR, ROW_NUMBER() OVER (ORDER BY NO_CHAR) NUM FROM crm_budget_line cbl WHERE LEAD_ID = lead GROUP BY 1 ORDER BY 1) as t1
     WHERE  cbl.no_char = t1.no_char; 
    
    SELECT MAX(NO_CHAR) INTO i FROM crm_budget_line WHERE LEAD_ID = lead; 
    
    -- Padre
    WHILE counter < i LOOP
        FOR x IN (SELECT * FROM crm_budget_line WHERE LEAD_ID = lead AND NO_CHAR = counter) LOOP
            num = x.NO_CHAR + 1;
            UPDATE crm_budget_line SET parent = x.ID WHERE LEAD_ID = x.LEAD_ID AND SUBSTRING(col1, 1, LENGTH(x.COL1)) = x.COL1 AND NO_CHAR = num;
        END LOOP;
        counter = counter + 1;
    END LOOP;

    FOR x IN (SELECT * FROM crm_budget_line WHERE LEAD_ID = lead AND PARENT IS NULL) LOOP
        INSERT INTO product_budget_item (CREATE_UID, WRITE_UID, CREATE_DATE, WRITE_DATE, LEVEL, CODE, NAME, ACTIVE)
            VALUES (user, user, NOW(), NOW(), x.NO_CHAR, x.COL1, x.COL2, True)
        RETURNING ID INTO idpart;
        UPDATE crm_budget_line SET BUDGET_ID = idpart WHERE ID = x.ID;
    END LOOP; 

    counter = 1;
    
    WHILE counter < i LOOP
        FOR x IN (SELECT * FROM crm_budget_line WHERE lead_id = 3 AND no_char = counter) LOOP
            FOR y IN (SELECT * FROM crm_budget_line WHERE PARENT = x.ID) LOOP
                INSERT INTO product_budget_item (CREATE_UID, WRITE_UID, CREATE_DATE, WRITE_DATE, LEVEL, CODE, NAME, PARENT_ID, ACTIVE)
                    VALUES (2, 2, NOW(), NOW(), y.NO_CHAR, y.COL1, y.COL2, x.BUDGET_ID, True)
                RETURNING ID INTO idpart;
                UPDATE crm_budget_line SET BUDGET_ID = idpart where ID = y.ID;
            END LOOP;
        END LOOP;
        counter = counter + 1;
    END LOOP;
     
    RETURN 'OK';
END;
    $function$
;   ''')


def migrate(cr, version):
    if not version:
        return
    update_data(cr)