# -*- coding: utf-8 -*-


def post_init_hook(env):
    """Registra como permitidas las combinaciones categoría-familia que ya usan los insumos y deja la secuencia después de la clave más alta."""
    Combo = env['catalogo.categoria.familia']
    usados = env['product.template'].with_context(active_test=False).search([('categoria_insumo_id', '!=', False), ('familia_insumo_id', '!=', False)])
    for cat, fam in {(p.categoria_insumo_id.id, p.familia_insumo_id.id) for p in usados}:
        if not Combo.search_count([('categoria_id', '=', cat), ('familia_id', '=', fam)]):
            Combo.create({'categoria_id': cat, 'familia_id': fam})
    env['catalogo.importador']._ajustar_secuencia()
