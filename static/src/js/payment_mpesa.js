odoo.define('pos_mpesa.payment', function (require) {
    "use strict";

    var core = require('web.core');
    var rpc = require('web.rpc');
    var PaymentInterface = require('point_of_sale.PaymentInterface');
    
    var _t = core._t;

    // QUESTION: What are the circumstances in which one would have to 
    // cancel a tx 
    // TODO: Write the tx_id on the pos.order.payment
    var PaymentMpesa = PaymentInterface.extend({
        // Consider an init to support reversals
        // How to call a funct in js and where to call
        // enable_reversals()
        init: function (pos, payment_method) {
            var self = this;
            this._super(pos, payment_method);
            this.phone = null;
            this.mpesa_terminal = true;
        },
        set_phone: function (phone) {
            this.phone = phone;
        },
        send_payment_request: function (cid) {
            console.log('send payment request')
            this._super.apply(this, arguments);
            this._reset_state();
            if (this.phone === null) {
                this._show_error(_.str.sprintf(_t('Please put in a phone number.')));
                line.set_payment_status('retry');
                // TODO: Add a return similar to what _mpesa_pay would return, just opposite
            }
            else {
                return this._mpesa_pay();
            }
            
        },
        send_payment_cancel: function (order, cid) {
            this._super.apply(this, arguments);
            // set only if we are polling
            this.was_cancelled = !!this.polling;
            return Promise.resolve(true);
        },
        close: function () {
            // QUESTION: What does this do?
            console.log('close')
            this._super.apply(this, arguments);
        },

        // private methods
        _reset_state: function () {
            console.log('reset state')
            // To track if query has been cancelled 
            // QUESTION: How can we set this using the response?
            this.was_cancelled = false;
            // QUESTION: What does this do?
            this.remaining_polls = 2;
            clearTimeout(this.polling);
        },

        _handle_odoo_connection_failure: function (data) {
            // handle timeout
            console.log('handle odoo connection failure')
            var line = this.pos.get_order().selected_paymentline;
            if (line) {
                line.set_payment_status('retry');
            }
            this._show_error(_('Could not connect to the Odoo server, please check your internet connection and try again.'));

            return Promise.reject(data); // prevent subsequent onFullFilled's from being called
        },

        _call_mpesa: function (data) {
            console.log("call mpesa rpc query")
            console.log('test mode: %s', this.payment_method.mpesa_test_mode)
            var self = this;
            return rpc.query({
                model: 'pos.payment.method',
                method: 'mpesa_stk_push',
                // FIXME: Remove acq_id
                args: [data, this.payment_method.mpesa_test_mode, 
                        this.payment_method.mpesa_secrete_key,
                        this.payment_method.mpesa_customer_key,
                        this.payment_method.mpesa_short_code,
                        this.payment_method.mpesa_pass_key],
            }, {
                // When a payment terminal is disconnected it takes Adyen
                // a while to return an error (~6s). So wait 10 seconds
                // before concluding Odoo is unreachable.
                timeout: 10000,
                shadow: true,
            }).catch(this._handle_odoo_connection_failure.bind(this));
        },

        _mpesa_get_account_reference: function () {
            var config = this.pos.config;
            console.log('mpesa get account reference')
            return _.str.sprintf('%s (ID: %s)', config.display_name, config.id);
        },

        _mpesa_pay_data: function () {
            console.log('mpesa pay data')
            var config = this.pos.config;
            var order = this.pos.get_order();
            var line = order.selected_paymentline;
            var data = {
                // construct data for mpesa request
                'amount': line.amount,
                'currency_id': this.pos.currency.name,
                // TODO: Capture phone number from interface
                'phone': this.phone,
                'order_id': order.uid, // not sure if that is the id
                'shop_name': this._mpesa_get_account_reference(config)
            };
            return data;
        },

        _mpesa_pay: function () {
            console.log('mpesa pay')
            var self = this;
            var data = this._mpesa_pay_data();
    
            return this._call_mpesa(data).then(function (data) {
                return self._mpesa_handle_response(data);
            });
        },

        _poll_for_response: function (resolve, reject) {
            console.log('poll for response')
            var self = this;

            // QUESTION: Where is was_cancelled set?
            if (this.was_cancelled) {
                resolve(false);
                return Promise.resolve();
            }
            
            var line = this.pos.get_order().selected_paymentline;
            return rpc.query({
                model: 'pos.payment.method',
                method: 'get_latest_mpesa_status',
                args: [
                    this.payment_method.id,
                    this.payment_method.mpesa_short_code,
                    this.payment_method.mpesa_pass_key,
                    line.transaction_id
                    // FIXME: Send tx ref or order id
                ],
            }, {
                timeout: 5000,
                shadow: true,
            }).catch(function (data) {
                reject();
                return self._handle_odoo_connection_failure(data);
            }).then(function (status) {
                
                var order = self.pos.get_order();
                var result_code = status.ResultCode
                
                // FIXME: Sort this out :: Condition to shift/set polling
                // if () {
                //     self.remaining_polls = 2;
                // } else {
                //     self.remaining_polls--;
                // }
    
                if (result_code === 0 || result_code === '0') {
                    // TODO: Set mpesa_receipt_number here
                    // TODO: Set client here
                    // QUESTION: How do we find our mpesa payment
                    resolve(true);
                    // QUESTION: Set the line to paid,how? where?
                } else if (self.remaining_polls <= 0) {
                    self._show_error(_t('The connection to your payment terminal failed. Please check if it is still connected to the internet.'));
                    // FIXME: How important is _mpesa_cancel
                    // self._mpesa_cancel();
                    resolve(false);
                }
            
            });
        },

        _mpesa_handle_response: function (response) {
            console.log('mpesa handle response')
            var line = this.pos.get_order().selected_paymentline;
    
            if (response.ResponseCode === '0') {
                line.set_payment_status('waitingCard');
    
                // This is not great, the payment screen should be
                // refactored so it calls render_paymentlines whenever a
                // paymentline changes. This way the call to
                // set_payment_status would re-render it automatically.
                this.pos.chrome.gui.current_screen.render_paymentlines();
                console.log(response);
                console.log('CheckoutRequestId: %s', response.CheckoutRequestID);
                line.transaction_id = response.get('CheckoutRequestID');
                var self = this;
                var res = new Promise(function (resolve, reject) {
                    // clear previous intervals just in case, otherwise
                    // it'll run forever
                    clearTimeout(self.polling);
    
                    self.polling = setInterval(function () {
                        self._poll_for_response(resolve, reject);
                    }, 3000);
                });

                // make sure to stop polling when we're done
                res.finally(function () {
                    self._reset_state();
                });
    
                return res;
                
            } else {
                
                console.error('error from MPesa', response.errorMessage);
    
                var msg = '';
                if (response.errorMessage) {
                    msg = response.errorMessage;
                }
    
                this._show_error(_.str.sprintf(_t('An unexpected error occured. Message from Mpesa: %s'), msg));
                if (line) {
                    line.set_payment_status('force_done');
                }
    
                return Promise.resolve();
            }
        },
    
        _show_error: function (msg, title) {
            console.log('show error')
            if (!title) {
                title =  _t('MPesa Error');
            }
            this.pos.gui.show_popup('error',{
                'title': title,
                'body': msg,
            });
        },

    });

    return PaymentMpesa;
});