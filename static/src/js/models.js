odoo.define('pos_mpesa.models', function (require) {
    var models = require('point_of_sale.models');
    var PaymentMpesa = require('pos_mpesa.payment');
    
    models.register_payment_method('mpesa', PaymentMpesa);
    models.load_fields('pos.payment.method', ['mpesa_secrete_key',
                                        'mpesa_customer_key',
                                        'mpesa_short_code',
                                        'mpesa_pass_key',
                                        'mpesa_test_mode']);
    models.load_fields('pos.payment', ['mpesa_receipt']);
    // TODO: Load the relevant models
    });
    