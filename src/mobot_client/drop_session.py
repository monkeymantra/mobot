# Copyright (c) 2021 MobileCoin. All rights reserved.

from typing import Optional

from decimal import Decimal
from django.utils import timezone
import mobilecoin as mc

from mobot_client.messages.chat_strings import ChatStrings
from mobot_client.messages.commands import CustomerChatCommands
from mobot_client.models import DropSession, Drop, CustomerStorePreferences, ItemSessionState, SessionState, Customer


class BaseDropSession:
    def __init__(self, store, payments, messenger):
        self.store = store
        self.payments = payments
        self.messenger = messenger

    def _check_drop_can_fulfill(self, drop: Drop) -> bool:
        return self.under_drop_quota(drop)

    @staticmethod
    def get_advertising_drop() -> Optional[Drop]:
        return Drop.objects.get_advertising_drop()

    @staticmethod
    def under_drop_quota(drop: Drop) -> bool:
        number_initial_drops_finished = DropSession.objects.filter(
            drop=drop, state__gt=SessionState.READY_TO_RECEIVE_INITIAL
        ).count()
        return number_initial_drops_finished < drop.initial_coin_limit

    def customer_has_store_preferences(self, customer: Customer) -> bool:
        return CustomerStorePreferences.objects.count(customer=customer, store=self.store) > 0

    @staticmethod
    def customer_has_completed_airdrop(customer: Customer, drop: Drop) -> bool:
        return customer.drop_sessions.filter(drop=drop, state=SessionState.COMPLETED).count() > 0

    @staticmethod
    def customer_has_completed_item_drop(customer: Customer, drop: Drop) -> bool:
        return customer.drop_sessions.filter(drop=drop, state=ItemSessionState.COMPLETED).count() > 0

    def log_and_send_message_to_customer(self, customer: Customer, message: str, attachements=None):
        self.messenger.log_and_send_message(
            customer,
            str(customer.phone_number),
            message,
            attachements=attachements
        )

    def handle_drop_session_allow_contact_requested(self, message, drop_session):
        command = CustomerChatCommands[message.text]
        if command is CustomerChatCommands.YES:
            CustomerStorePreferences.objects.create(
                customer=drop_session.customer, store=self.store, allows_contact=True
            )
            drop_session.state = SessionState.COMPLETED
            self.log_and_send_message_to_customer(drop_session, ChatStrings.BYE)

        elif command is CustomerChatCommands.NO:
            customer_prefs = CustomerStorePreferences(
                customer=drop_session.customer, store=self.store, allows_contact=False
            )
            customer_prefs.save()
            drop_session.state = SessionState.COMPLETED
            self.log_and_send_message_to_customer(drop_session, ChatStrings.BYE)
        elif command is CustomerChatCommands.PRIVACY:
            self.log_and_send_message_to_customer(drop_session, ChatStrings.PRIVACY_POLICY_REPROMPT.format(url=self.store.privacy_policy_url))
        else:
            self.log_and_send_message_to_customer(drop_session, ChatStrings.HELP)
        drop_session.save()

    def handle_number_restriction(self, drop_session: DropSession, source: str):
        customer = drop_session.customer
        drop = drop_session.drop
        if not customer.phone_number.startswith(drop.number_restriction):
            self.messenger.log_and_send_message(
                customer,
                str(customer.phone_number),
                ChatStrings.COUNTRY_RESTRICTED
            )
        else:
            customer_payments_address = self.payments.get_payments_address(str(customer.phone_number))
            if customer_payments_address is None:
                self.messenger.log_and_send_message(
                    customer,
                    str(customer.phone_number),
                    ChatStrings.PAYMENTS_ENABLED_HELP.format(item_desc=drop.item.description),
                )

    def set_customer_store_preferences(self, drop_session: DropSession, allows_contact=True):
        customer = drop_session.customer
        customer_store_preferences, _ = customer.customer_store_preferences.get_or_create(store=drop_session.store)
        customer_store_preferences.allows_contact = allows_contact
        customer_store_preferences.save()