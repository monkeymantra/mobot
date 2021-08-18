# Copyright (c) 2021 MobileCoin. All rights reserved.

from django.db.models import IntegerChoices

from mobot_client.models import Message, MessageDirection, Customer, Store


class SignalMessenger:
    def __init__(self, signal, store: Store):
        self.signal = signal
        self.store = store

    def log_and_send_message(self, customer: Customer, source: dict, text: str, attachments=[]):
        if isinstance(source, dict):
            destination = source["number"]
        else:
            destination = str(customer.phone_number)

        Message.objects.create(
            customer=customer,
            store=self.store,
            text=text,
            direction=MessageDirection.SENT,
        )
        self.signal.send_message(destination, text, attachments=attachments)

    def log_and_send_message_to_customer(self, customer: Customer, text: str, attachments=[]):
        self.log_and_send_message(customer, None, text, attachments)

    @staticmethod
    def log_received(message: Message, customer: Customer, store: Store):
        Message.objects.create(customer=customer, store=store, text=message.text,
                           direction=MessageDirection.RECEIVED)
