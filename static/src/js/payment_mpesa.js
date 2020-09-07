odoo.define('pos_adyen.payment', function (require) {
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

        send_payment_request: function (cid) {
            this._super.apply(this, arguments);
            // this._reset_state();
            return this._mpesa_pay();
        },
        send_payment_cancel: function (order, cid) {
            this._super.apply(this, arguments);
            // set only if we are polling
            this.was_cancelled = !!this.polling;
            // FIXME: How to cancel mpesa payment
            return this._mpesa_cancel();
        },
        close: function () {
            // QUESTION: What does this do?
            this._super.apply(this, arguments);
        },

        // private methods
        _reset_state: function () {
            // To track if query has been cancelled 
            // QUESTION: How can we set this using the response?
            this.was_cancelled = false;
            this.last_diagnosis_service_id = false;
            // QUESTION: What does this do?
            this.remaining_polls = 2;
            clearTimeout(this.polling);
        },

        _handle_odoo_connection_failure: function (data) {
            // handle timeout
            var line = this.pos.get_order().selected_paymentline;
            if (line) {
                line.set_payment_status('retry');
            }
            this._show_error(_('Could not connect to the Odoo server, please check your internet connection and try again.'));

            return Promise.reject(data); // prevent subsequent onFullFilled's from being called
        },

        _call_mpesa: function (data) {
            var self = this;
            return rpc.query({
                model: 'pos.payment.method',
                method: 'proxy_mpesa_request',
                // FIXME: Remove acq_id
                args: [data],
            }, {
                // When a payment terminal is disconnected it takes Adyen
                // a while to return an error (~6s). So wait 10 seconds
                // before concluding Odoo is unreachable.
                timeout: 10000,
                shadow: true,
            }).catch(this._handle_odoo_connection_failure.bind(this));
        },

        _mpesa_pay_data: function () {
            var order = this.pos.get_order();
            var line = order.selected_paymentline;
            var data = {
                // construct data for mpesa request
                'amount': line.amount,
                'currency_id': this.pos.currency.name,
                // TODO: Capture phone number from interface
                'phone': '',
                'order_id': order.uid, // not sure if that is the id
            }
            return data
        },

        _mpesa_pay: function () {
            var self = this;
            var data = this._mpesa_pay_data();
    
            return this._call_mpesa(data).then(function (data) {
                return self._mpesa_handle_response(data);
            });
        },

        // _mpesa_cancel: function (ignore_error) {
        //     // FIXME: Ignore error may not be for us
        //     // var previous_service_id = this.most_recent_service_id;
        //     var header = {
                
        //     }
    
        //     var data = {
        //         // Add data for mpesa cancel
        //     };
    
        //     return this._call_mpesa(data).then(function (data) {
    
        //         // Only valid response is a 200 OK HTTP response which is
        //         // represented by true.
        //         // FIXME: Make apt for mpesa :: data?
        //         if (! ignore_error && data !== true) {
        //             self._show_error(_('Cancelling the payment failed. Please cancel it manually on the payment terminal.'));
        //         }
        //     });
        // },

        _poll_for_response: function (resolve, reject) {
            var self = this;
            // FIXME: Where is was_cancelled set?
            if (this.was_cancelled) {
                resolve(false);
                return Promise.resolve();
            }
    
            return rpc.query({
                model: 'pos.payment.method',
                method: 'get_latest_mpesa_status',
                args: [
                    this.payment_method.id,
                    // FIXME: Send tx ref or order id
                ],
            }, {
                timeout: 5000,
                shadow: true,
            }).catch(function (data) {
                reject();
                return self._handle_odoo_connection_failure(data);
            }).then(function (status) {
                var status = status.tx_status;
                var transaction_id = status.tx_id;
                var transaction_reference = status.tx_ref;
                var order = self.pos.get_order();
                var line = order.selected_paymentline;
    
                // FIXME: Sort this out
                if (self.status !== 'pending') {
                    self.remaining_polls = 2;
                } else {
                    self.remaining_polls--;
                }
    
                if (self.status !== 'done') {
                    // var response = notification.SaleToPOIResponse.PaymentResponse.Response;
                    // var additional_response = new URLSearchParams(response.AdditionalResponse);
    
                    if (self.status !== 'done') {
                        var config = self.pos.config;
                        // var payment_response = notification.SaleToPOIResponse.PaymentResponse;
                        var customer_receipt = transaction_reference;
    
                        if (customer_receipt) {
                            line.set_receipt_info(self._convert_receipt_info(customer_receipt.OutputContent.OutputText));
                        }
    
                        line.transaction_id = additional_response.get('pspReference');
                        // line.card_type = additional_response.get('cardType');
                        resolve(true);
                    } else {
                        // FIXME: Carry messages from tx to pos interfaces
                        self._show_error(_.str.sprintf(_t('Message from Mpesa: %s'), 'Cancelled'));
    
                        // this means the transaction was cancelled by pressing the cancel button on the device
                        // if (self.status !== 'done')) {
                        //     resolve(false);
                        // } else {
                        //     line.set_payment_status('force_done');
                        //     reject();
                        // }
                    }
                } else if (self.remaining_polls <= 0) {
                    self._show_error(_t('The connection to your payment terminal failed. Please check if it is still connected to the internet.'));
                    self._mpesa_cancel();
                    resolve(false);
                }
            
            });
        },

        _mpesa_handle_response: function (response) {
            var line = this.pos.get_order().selected_paymentline;
    
            if (response.state == 'cancel') {
                this._show_error(_t('Authentication failed. Please check your Mpesa credentials.'));
                line.set_payment_status('force_done');
                return Promise.resolve();
            }
    
            // response = response.SaleToPOIRequest;
            if (response.state == 'cancel') {
                console.error('error from MPesa', response);
    
                var msg = '';
                if (response.state) {
                    // var params = new URLSearchParams(response.EventNotification.EventDetails);
                    msg = params.get('message');
                }
    
                this._show_error(_.str.sprintf(_t('An unexpected error occured. Message from Mpesa: %s'), msg));
                if (line) {
                    line.set_payment_status('force_done');
                }
    
                return Promise.resolve();
            } else {
                line.set_payment_status('waitingCard');
    
                // This is not great, the payment screen should be
                // refactored so it calls render_paymentlines whenever a
                // paymentline changes. This way the call to
                // set_payment_status would re-render it automatically.
                this.pos.chrome.gui.current_screen.render_paymentlines();
    
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
            }
        },
    
        _show_error: function (msg, title) {
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