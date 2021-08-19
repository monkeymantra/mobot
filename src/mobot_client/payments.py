# Copyright (c) 2021 MobileCoin. All rights reserved.
import enum
from typing import Optional, Dict
import time
from decimal import Decimal


import mobilecoin as mc
import logging

from django.db.models.signals import post_save

from mobot_client.models.phone_numbers import PhoneNumberWithRFC3966 as PhoneNumber

from mobilecoin.client import Client as MobileCoinClient

from mobot_client.models import (
    Order,
    Sku, )
from mobot_client.models.states import SessionState
from mobot_client.logger import SignalMessenger
from signald_client.main import Signal
from mobot_client.messages.chat_strings import ChatStrings
from mobot_client.models import Store, Payment, DropSession, Customer


class TransactionStatus(str, enum.Enum):
    TRANSACTION_PENDING = "TransactionPending"
    TRANSACTION_SUCCESS = "TransactionSuccess"


class PaymentResponder:

    def __init__(self, signal: Signal, messenger: SignalMessenger):
        self.signal = Signal
        self.messenger = messenger

    def handle_payment_without_customer_address(self, payment: Payment):
        if not payment.payment_address and payment.direction is Payment.PaymentDirection.TO_CUSTOMER:
            payment.status = Payment.PaymentStatus.NO_ADDRESS
            if not payment.status == Payment.PaymentStatus.FAILURE:
                self.messenger.log_and_send_message_to_customer(
                    payment.drop_session.customer,
                    ChatStrings.PAYMENTS_DEACTIVATED.format(number=self.store.phone_number),
                )


class Payments:
    """The Payments class handles the logic relevant to sending MOB and handling receipts."""

    def __init__(
            self,
            mobilecoin_client: MobileCoinClient,
            minimum_fee_pmob: int,
            account_id: str,
            store: Store,
            messenger: SignalMessenger,
            signal: Signal,
    ):
        self.mcc = mobilecoin_client
        self.minimum_fee_pmob = minimum_fee_pmob
        self.account_id = account_id
        self.store = store
        self.signal = signal
        self.messenger = messenger
        self.logger = logging.getLogger(self.__class__.__name__)
        self.responder = PaymentResponder(self.signal, self.messenger)

    def get_payments_address(self, dest: PhoneNumber):
        customer_signal_profile = self.signal.get_profile(dest.rfc3966, True)
        self.logger.info(customer_signal_profile)
        return customer_signal_profile.get("mobilecoin_address")

    def send_mob_to_customer(self, drop_session: DropSession, amount_mob: Decimal, cover_transaction_fee: bool) -> Payment:
        customer = drop_session.customer
        customer_payments_address = self.get_payments_address(customer.phone_number)

        payment = Payment.objects.create(
            drop_session=drop_session,
            direction=Payment.PaymentDirection.TO_CUSTOMER,
            amount_in_mob=amount_mob,
            status=Payment.PaymentStatus.NOT_STARTED,
            payment_address=customer_payments_address,
        )
        if not payment.payment_address:
            self.responder.handle_payment_without_customer_address(payment)
        else:
            if not cover_transaction_fee:
                amount_mob = amount_mob - Decimal(mc.pmob2mob(self.minimum_fee_pmob))
            else:
                amount_mob = amount_mob + Decimal(mc.pmob2mob(self.minimum_fee_pmob))
            if amount_mob > 0:
                self.send_mob_to_address(
                    str(customer.phone_number), self.account_id, amount_mob, payment.payment_address
                )
                payment.PaymentStatus = Payment.PaymentStatus.SUCCEEDED
            elif amount_mob <= 0:
                payment.PaymentStatus = Payment.PaymentStatus.NOT_NECESSARY

        payment.save()
        return payment

    def check_txo(self, txo_id: str, dest: str, retries: int = 10, retry_sleep: float = 1.0) -> bool:
        for _ in range(retries):
            try:
                txo = self.mcc.get_txo(txo_id)
                self.logger.debug(f"Transaction Landed: {txo}")
                return True
            except Exception:
                self.logger.exception("TxOut did not land yet, id: " + txo_id)
            time.sleep(retry_sleep)
        else:
            return False

    def send_mob_to_address(
            self, dest: str, account_id: str, payment: Payment) -> Payment:
        # customer_payments_address is b64 encoded, but full service wants a b58 address
        customer_payments_address = mc.utility.b64_public_address_to_b58_wrapper(
            payment.payment_address
        )

        tx_proposal = self.mcc.build_transaction(
            account_id, payment.amount_in_mob, customer_payments_address
        )
        txo_id = self.submit_transaction(tx_proposal, account_id)
        payment.status = Payment.PaymentStatus.IN_PROGRESS
        payment_succeeded = self.check_txo(txo_id)
        payment.status = Payment.PaymentStatus.SUCCEEDED if payment_succeeded else Payment.PaymentStatus.FAILURE
        if payment_succeeded:
            self.send_payment_receipt(dest, tx_proposal)
        payment.save()
        return payment

    def submit_transaction(self, tx_proposal, account_id):
        # retry up to 10 times in case there's some failure with a 1 sec timeout in between each
        transaction_log = self.mcc.submit_transaction(tx_proposal, account_id)
        list_of_txos = transaction_log["output_txos"]

        if len(list_of_txos) > 1:
            raise ValueError(
                "Found more than one txout for this chat bot-initiated transaction."
            )

        return list_of_txos[0]["txo_id_hex"]

    def send_payment_receipt(self, source, tx_proposal) -> dict:
        receiver_receipt = self.create_receiver_receipt(tx_proposal)
        receiver_receipt = mc.utility.full_service_receipt_to_b64_receipt(
            receiver_receipt
        )
        resp = self.signal.send_payment_receipt(source, receiver_receipt, "Refund")
        self.logger.info("Send receipt", receiver_receipt, "to", source, ":", resp)
        return resp

    def create_receiver_receipt(self, tx_proposal):
        receiver_receipts = self.mcc.create_receiver_receipts(tx_proposal)
        # I'm assuming there will only be one receiver receipt (not including change tx out).
        if len(receiver_receipts) > 1:
            raise ValueError(
                "Found more than one txout for this chat bot-initiated transaction."
            )
        return receiver_receipts[0]

    def get_unspent_pmob(self):
        account_amount_response = self.mcc.get_balance_for_account(self.account_id)
        unspent_pmob = int(account_amount_response["unspent_pmob"])
        return unspent_pmob

    def get_minimum_fee_pmob(self):
        return self.minimum_fee_pmob

    def receive_payment(self, customer: Customer, receipt) -> Payment:
        receipt = mc.utility.full_service_receipt_to_b64_receipt(receipt)
        transaction_status = TransactionStatus.TRANSACTION_PENDING
        drop_session = DropSession.objects.filter(
            customer=customer,
            state=SessionState.WAITING_FOR_PAYMENT_OR_BONUS_TX,
        ).first()
        payment = Payment(
            status=Payment.PaymentStatus.IN_PROGRESS,
            payment_type=Payment.PaymentType.PAYMENT,
            direction=Payment.PaymentDirection.TO_STORE,
            drop_session=drop_session,
        )

        while transaction_status == TransactionStatus.TRANSACTION_PENDING:
            receipt_status = self.mcc.check_receiver_receipt_status(
                self.public_address, receipt
            )
            transaction_status = receipt_status["receipt_transaction_status"]
            self.logger.info("Waiting for", receipt, receipt_status)

        if transaction_status == TransactionStatus.TRANSACTION_SUCCESS:
            amount_paid_mob = mc.pmob2mob(receipt_status["txo"]["value_pmob"])
            payment.amount_in_mob = amount_paid_mob
            payment.status = Payment.PaymentStatus.SUCCEEDED
        else:
            payment.status = Payment.PaymentStatus.FAILURE

        payment.save()
        return payment

    def handle_item_payment(self, payment: Payment) -> Payment:
        drop_session = payment.drop_session
        item_cost_mob = drop_session.drop.item.price_in_mob
        customer = drop_session.customer

        if payment.amount_in_mob < item_cost_mob:
            refund_amount = mc.pmob2mob(
                mc.mob2pmob(payment.amount_in_mob) - self.minimum_fee_pmob
            )
            if refund_amount > 0:
                self.messenger.log_and_send_message_to_customer(
                    customer,
                    ChatStrings.NOT_ENOUGH_MOB_SENDING_REFUND.format(amount_paid=refund_amount.normalize())
                )
                self.send_mob_to_customer(customer, amount_paid_mob, False)
            else:
                self.messenger.log_and_send_message_to_customer(
                    drop_session.customer,
                    ChatStrings.NOT_ENOUGH
                )
        elif (
                mc.mob2pmob(amount_paid_mob)
                > mc.mob2pmob(item_cost_mob) + self.minimum_fee_pmob
        ):
            excess = amount_paid_mob - item_cost_mob
            net_excess = mc.pmob2mob(mc.mob2pmob(excess) - self.minimum_fee_pmob)
            self.messenger.log_and_send_message_to_customer(
                customer,
                ChatStrings.EXCESS_PAYMENT.format(refund=net_excess.normalize())
            )
            self.send_mob_to_customer(customer, excess, False)
        else:
            self.messenger.log_and_send_message_to_customer(
                customer,
                f"We received {amount_paid_mob.normalize()} MOB"
            )

        available_options = []
        skus = Sku.objects.filter(item=drop_session.drop.item).order_by("sort_order")

        for sku in skus:
            number_ordered = Order.objects.filter(sku=sku).count()
            if number_ordered < sku.quantity:
                available_options.append(sku)

        if len(available_options) == 0:
            self.messenger.log_and_send_message_to_customer(
                customer,
                ChatStrings.OUT_OF_STOCK_REFUND
            )
            self.send_mob_to_customer(drop_session, item_cost_mob, True)
            drop_session.state = SessionState.REFUNDED
            drop_session.save()
            return

        message_to_send = (
            ChatStrings.WAITING_FOR_SIZE_PREFIX + ChatStrings.get_options(available_options, capitalize=True)
        )

        self.messenger.log_and_send_message_to_customer(customer, message_to_send)
        drop_session.state = SessionState.WAITING_FOR_SIZE
        drop_session.save()

        return

