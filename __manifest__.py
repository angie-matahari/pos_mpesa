# -*- coding: utf-8 -*-
{
    'name': "POS MPesa",

    'summary': """
        Integrate your POS with an MPesa payment terminal""",

    'description': """
        Allows customer to pay for POS Order using MPesa 
        stk push.
    """,

    'author': "Kylix Technologies Ltd",
    'website': "http://www.kylix.online",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/13.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Point of Sale',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': [
        'base',
        'point_of_sale',
    ],

    # always loaded
    'data': [
        'views/pos_config_views.xml',
        'views/pos_payment_method_views.xml',
        'views/point_of_sale_assets.xml',
    ],
    # only loaded in demonstration mode
    'qweb': ['static/src/xml/pos.xml'],
    'installable': True,
    'license': 'OEEL-1',
}
