# Copyright (c) 2021 MobileCoin. All rights reserved.

from typing import List

import mobilecoin as mc
import googlemaps
from googlemaps.client import urlencode_params
import pytz

from django.conf import settings

from mobot_client.drop_session import BaseDropSession
from mobot_client.models import (
    DropSession,
    CustomerStorePreferences,
    Order,
    Item,
    Sku,
    CustomerDropRefunds, ItemSessionState, OrderStatus,
)
from mobot_client.messages.chat_strings import ChatStrings
from mobot_client.messages.commands import CustomerChatCommands


class ItemDropSession(BaseDropSession):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.gmaps = googlemaps.Client(key=settings.GMAPS_CLIENT_KEY)
        self.vat_id = settings.VAT_ID


    def drop_item_get_available(self, drop_item: Item):
        available_options = []
        skus = [] if not hasattr(drop_item, 'skus') else drop_item.skus

        for sku in skus:
            if sku.available:
                available_options.append(sku)

        return available_options

    def send_item_availability(self, drop_session: DropSession, message_to_send: str = ""):
        available_options = self.drop_item_get_available(drop_session.drop.item)
        message_to_send += "\n\n" + ChatStrings.get_options(available_options, capitalize=True)
        message_to_send += "\n\n" + ChatStrings.ITEM_WHAT_SIZE_OR_CANCEL

        self.log_and_send_message_to_customer(
            drop_session.customer,
            message_to_send
        )

    def handle_item_drop_session_waiting_for_size(self, message, drop_session: DropSession):
        command = CustomerChatCommands[message.text]
        drop_item = drop_session.drop.item

        if command in (CustomerChatCommands.REFUND, CustomerChatCommands.NO):
            self.handle_cancel_and_refund(message, drop_session, None)
        elif command is CustomerChatCommands.HELP:
            available_options = self.drop_item_get_available(drop_session.drop.item)
            self.log_and_send_message_to_customer(
                drop_session.customer,
                ChatStrings.ITEM_OPTION_HELP + "\n\n" + ChatStrings.get_options(available_options, capitalize=True)
            )
        elif command is CustomerChatCommands.PRIVACY:
            privacy_policy_url = drop_session.drop.store.privacy_policy_url
            self.log_and_send_message_to_customer(
                drop_session.customer,
                ChatStrings.PRIVACY_POLICY.format(url=privacy_policy_url),
            )
            self.send_item_availability(drop_session)
        elif command in (CustomerChatCommands.CHART, CustomerChatCommands.INFO):

            item_description_text = drop_item.name if not drop_item.short_description else drop_item.short_description

            if not drop_item.image_link:
                self.log_and_send_message_to_customer(
                    drop_session.customer,
                    ChatStrings.ITEM_OPTION_NO_CHART.format(description=drop_item.short_description)
                )
            else:
                attachments = [
                    "/signald/attachments/" + attachment.strip()
                    for attachment in drop_item.image_link.split(",")
                ]
                self.log_and_send_message_to_customer(
                    drop_session.customer,
                    item_description_text,
                    attachments=attachments,
                )

            self.send_item_availability(drop_session)
        if not self.drop_item_get_available(drop_item):
            sku = Sku.objects.filter(item=drop_item, identifier__iexact=message.text).first()

            if not sku:
                message_to_send = ChatStrings.MISSING_SIZE.format(size=message.text)
                self.send_item_availability(drop_session, message_to_send=message_to_send)
            elif not sku.available:
                message_to_send = ChatStrings.ITEM_SOLD_OUT
                self.send_item_availability(drop_session, message_to_send=message_to_send)
            else:
                Order.objects.create(
                    customer=drop_session.customer,
                    drop_session=drop_session,
                    sku=sku,
                    conversion_rate_mob_to_currency=drop_session.drop.conversion_rate_mob_to_currency
                )

                drop_session.state = ItemSessionState.WAITING_FOR_NAME

                self.messenger.log_and_send_message(
                    drop_session.customer, message.source, ChatStrings.NAME_REQUEST
                )

        drop_session.save()

    def handle_item_drop_session_waiting_for_payment(self, message, drop_session: DropSession):
        price_in_mob = mc.pmob2mob(drop_session.drop.item.price_in_pmob)
        command = CustomerChatCommands[message.text]
        if command is CustomerChatCommands.HELP:
            self.log_and_send_message_to_customer(
                drop_session.customer, ChatStrings.ITEM_HELP
            )
        elif command is CustomerChatCommands.NO:
            drop_session.state = ItemSessionState.CANCELLED
            self.log_and_send_message_to_customer(
                drop_session.customer,
                ChatStrings.SESSION_CANCELLED
            )
        elif command is CustomerChatCommands.PAY:
            self.log_and_send_message_to_customer(
                drop_session.customer,
                ChatStrings.PAY.format(amount=price_in_mob.normalize()),
            )
        elif command is CustomerChatCommands.PRIVACY:
            privacy_policy_url = drop_session.drop.store.privacy_policy_url
            self.log_and_send_message_to_customer(
                drop_session.customer,
                ChatStrings.PRIVACY_POLICY.format(url=privacy_policy_url),
            )
        elif command is CustomerChatCommands.INFO:
            drop_item = drop_session.drop.item

            item_description_text = drop_item.description or drop_item.short_description or drop_item.name

            attachments = [
                "/signald/attachments/" + attachment.strip()
                for attachment in drop_item.image_link.split(",")
            ] if drop_item.image_link else None
            self.log_and_send_message_to_customer(drop_session.customer, item_description_text, attachements=attachments)
        else:
            self.log_and_send_message_to_customer(
                drop_session.customer, ChatStrings.ITEM_HELP_SHORT
            )

        # Re-display available sizes and request payment
        drop_item = drop_session.drop.item
        available_options = self.drop_item_get_available(drop_item)
        if len(available_options) == 0:
            self.log_and_send_message_to_customer(
                drop_session.customer, ChatStrings.OUT_OF_STOCK
            )
            drop_session.state = ItemSessionState.CANCELLED
        else:
            message_to_send = f"{drop_item.name} in " + ChatStrings.get_options(available_options)
            price_in_mob = mc.pmob2mob(drop_item.price_in_pmob)
            message_to_send += "\n\n" + ChatStrings.PAYMENT_REQUEST.format(price=price_in_mob.normalize())
            self.messenger.log_and_send_message(
                drop_session.customer,
                message_to_send
            )
        drop_session.save()


    def handle_cancel_and_refund(self, message, drop_session, order):
        self.messenger.log_and_send_message(
            drop_session.customer, message.source, ChatStrings.ITEM_OPTION_CANCEL
        )
        price_in_mob = mc.pmob2mob(drop_session.drop.item.price_in_pmob)

        customer_drop_refunds, _ = CustomerDropRefunds.objects.get_or_create(customer=drop_session.customer, drop=drop_session.drop)
        
        should_refund_transaction_fee = False

        if customer_drop_refunds.number_of_times_refunded < drop_session.drop.max_refund_transaction_fees_covered:
            should_refund_transaction_fee = True
            customer_drop_refunds.number_of_times_refunded = customer_drop_refunds.number_of_times_refunded + 1
            customer_drop_refunds.save()

        self.payments.send_mob_to_customer(drop_session.customer, message.source, price_in_mob, should_refund_transaction_fee)
        
        if order is not None:
            order.status = OrderStatus.CANCELLED
            order.save()

        drop_session.state = ItemSessionState.REFUNDED
        drop_session.save()

    def get_country_for_address(self, address) -> str:
        address_components = address[0]['address_components']
        return [component for component in address_components[0] if 'country' in component['types']][0]['short_name']

    def handle_item_drop_session_waiting_for_address(self, message, drop_session: DropSession):
        order = None if not hasattr(drop_session, 'order') else drop_session.order
        command = None
        if not order:
            self.log_and_send_message_to_customer(
                drop_session.customer, ChatStrings.MISSING_ORDER
            )
        else:
            command = CustomerChatCommands[message.text]
            address = self.gmaps.geocode(message.text, region=drop_session.drop.country_code_restriction)
            if not address:
                self.log_and_send_message_to_customer(
                    drop_session.customerChatStrings.ADDRESS_NOT_FOUND
                )
            elif command is CustomerChatCommands.HELP:
                self.log_and_send_message_to_customer(
                    drop_session.customer,
                    ChatStrings.ADDRESS_HELP.format(item=drop_session.drop.item.name)
                )
            elif command is CustomerChatCommands.NO:
                self.handle_cancel_and_refund(message, drop_session, order)
            else:
                country = self.get_country_for_address(address)
                if country == drop_session.drop.country_code_restriction:
                    order.shipping_address = address[0]["formatted_address"]
                    drop_session.state = ItemSessionState.SHIPPING_INFO_CONFIRMATION

                    self.log_and_send_message_to_customer(
                        drop_session.customer,
                        ChatStrings.VERIFY_SHIPPING.format(
                            name=order.shipping_name, address=order.shipping_address
                        ),
                    )
                else:
                    order.status = OrderStatus.CANCELLED
                    self.log_and_send_message_to_customer(
                        drop_session.customer,
                        ChatStrings.ADDRESS_RESTRICTION.format(drop_session.drop.country_code_restriction)
                    )
            order.save()
            drop_session.save()


    def handle_item_drop_session_waiting_for_name(self, message, drop_session):
        command = CustomerChatCommands[message.text]
        order = Order.objects.filter(drop_session=drop_session).first()
        if order:
            self.messenger.log_and_send_message(
                drop_session.customer, message.source, ChatStrings.MISSING_ORDER
            )
            if command is CustomerChatCommands.HELP:
                self.messenger.log_and_send_message(
                    drop_session.customer, message.source,
                    ChatStrings.NAME_HELP
                )
            elif command is CustomerChatCommands.NO:
                self.handle_cancel_and_refund(message, drop_session, order)
            else:
                order.shipping_name = message.text
                order.save()

                drop_session.state = ItemSessionState.WAITING_FOR_ADDRESS
                drop_session.save()

                self.log_and_send_message_to_customer(
                    drop_session.customer, ChatStrings.ADDRESS_REQUEST
                )
        else:
            self.log_and_send_message_to_customer(
                drop_session.customer, ChatStrings.MISSING_ORDER
            )

    def send_order_confirmation(self, order: Order):
        drop_session = order.drop_session
        item = drop_session.drop.item
        price_in_mob = mc.pmob2mob(item.price_in_pmob)
        price_local_fiat = float(price_in_mob) * drop_session.drop.conversion_rate_mob_to_currency
        vat = price_local_fiat * 1 / 6
        tz = pytz.timezone(drop_session.drop.timezone)
        self.log_and_send_message_to_customer(
            drop_session.customer,
            ChatStrings.ORDER_CONFIRMATION.format(
                order_id=order.id,
                today=order.date.astimezone(tz).strftime("%b %d, %Y %I:%M %p %Z"),
                item_name=item.name,
                sku_name=order.sku.identifier,
                price=price_in_mob.normalize(),
                ship_name=order.shipping_name,
                ship_address=order.shipping_address,
                vat=vat,
                vat_id=self.vat_id,
                store_name=drop_session.drop.store.name,
                store_contact="hello@mobilecoin.com"
            ),
        )

    def handle_item_drop_session_shipping_confirmation(self, message, drop_session):
        order = Order.objects.filter(drop_session=drop_session).first()
        command = CustomerChatCommands[message.text]

        if not order:
            self.log_and_send_message_to_customer(
                drop_session.customer, ChatStrings.MISSING_ORDER
            )
        if command is CustomerChatCommands.NAME:
            drop_session.state = ItemSessionState.WAITING_FOR_NAME
            self.log_and_send_message_to_customer(
                drop_session.customer, ChatStrings.NAME_REQUEST
            )
        elif command is CustomerChatCommands.PRIVACY:
            privacy_policy_url = drop_session.drop.store.privacy_policy_url
            self.log_and_send_message_to_customer(
                drop_session.customer,
                ChatStrings.PRIVACY_POLICY.format(url=privacy_policy_url),
            )
        elif command in {CustomerChatCommands.NO, CustomerChatCommands.REFUND}:
            self.handle_cancel_and_refund(message, drop_session, order)
        elif command is CustomerChatCommands.YES:
            self.log_and_send_message_to_customer(
                drop_session.customer,
                ChatStrings.SHIPPING_CONFIRMATION_HELP.format(
                    name=order.shipping_name, address=order.shipping_address
                )
            )
        else:
            order.status = OrderStatus.CONFIRMED
            self.send_order_confirmation(order)

            if drop_session.customer.customer_store_preferences.filter(store=drop_session.drop.store).first():
                drop_session.state = ItemSessionState.COMPLETED
                self.log_and_send_message_to_customer(
                    drop_session.customer, ChatStrings.BYE
                )
            else:
                drop_session.state = ItemSessionState.ALLOW_CONTACT_REQUESTED
                self.log_and_send_message_to_customer(
                    drop_session.customer, message.source, ChatStrings.FUTURE_NOTIFICATIONS
                )
        order.save()
        drop_session.save()


    def handle_item_drop_session_allow_contact_requested(self, message, drop_session):
        command = CustomerChatCommands[message.lower]
        if command is CustomerChatCommands.NO:
            self.set_customer_store_preferences(drop_session, False)
            self.log_and_send_message_to_customer(
                drop_session.customer, ChatStrings.BYE
            )
            drop_session.state = ItemSessionState.COMPLETED

        elif command is CustomerChatCommands.YES:
            self.set_customer_store_preferences(drop_session, True)
            self.log_and_send_message_to_customer(drop_session.customer, ChatStrings.BYE)
            drop_session.state = ItemSessionState.COMPLETED

        elif command is CustomerChatCommands.PRIVACY:
            privacy_policy_url = drop_session.drop.store.privacy_policy_url
            self.messenger.log_and_send_message(
                drop_session.customer,
                message.source,
                ChatStrings.PRIVACY_POLICY_REPROMPT.format(url=privacy_policy_url),
            )


        self.messenger.log_and_send_message(
            drop_session.customer, message.source, ChatStrings.HELP
        )

    def handle_active_item_drop_session(self, message, drop_session):
        print(drop_session.state)
        if drop_session.state == ItemSessionState.WAITING_FOR_PAYMENT:
            self.handle_item_drop_session_waiting_for_payment(message, drop_session)
            return

        if drop_session.state == ItemSessionState.WAITING_FOR_SIZE:
            self.handle_item_drop_session_waiting_for_size(message, drop_session)
            return

        if drop_session.state == ItemSessionState.WAITING_FOR_ADDRESS:
            self.handle_item_drop_session_waiting_for_address(message, drop_session)
            return

        if drop_session.state == ItemSessionState.WAITING_FOR_NAME:
            self.handle_item_drop_session_waiting_for_name(message, drop_session)
            return

        if drop_session.state == ItemSessionState.SHIPPING_INFO_CONFIRMATION:
            self.handle_item_drop_session_shipping_confirmation(message, drop_session)
            return

        if drop_session.state == ItemSessionState.ALLOW_CONTACT_REQUESTED:
            self.handle_item_drop_session_allow_contact_requested(message, drop_session)
            return

    def handle_no_active_item_drop_session(self, customer, message, drop):
        if not customer.phone_number.startswith(drop.number_restriction):
            self.messenger.log_and_send_message(
                customer, message.source, ChatStrings.COUNTRY_RESTRICTED
            )
            return

        customer_payments_address = self.payments.get_payments_address(message.source)
        if customer_payments_address is None:
            self.messenger.log_and_send_message(
                customer,
                message.source,
                ChatStrings.PAYMENTS_ENABLED_HELP.format(
                    item_desc=drop.item.short_description
                ),
            )
            return

        # Greet the user
        message_to_send = ChatStrings.ITEM_DROP_GREETING.format(
            store_name=drop.store.name,
            store_description=drop.store.description,
            item_description=drop.item.short_description
        )

        available_options = self.drop_item_get_available(drop.item)
        if len(available_options) == 0:
            self.messenger.log_and_send_message(
                customer, message.source, ChatStrings.OUT_OF_STOCK
            )
            return

        message_to_send += "\n\n"+ChatStrings.get_options(available_options, capitalize=True)

        price_in_mob = mc.pmob2mob(drop.item.price_in_pmob)
        message_to_send += "\n\n"+ChatStrings.ITEM_DISCOUNT.format(
            price=price_in_mob.normalize(),
            country=drop.country_long_name_restriction
        )

        self.messenger.log_and_send_message(customer, message.source, message_to_send)
        self.messenger.log_and_send_message(
            customer,
            message.source,
            ChatStrings.PAYMENT_REQUEST.format(price=price_in_mob.normalize()),
        )

        new_drop_session, _ = DropSession.objects.get_or_create(
            customer=customer,
            drop=drop,
            state=ItemSessionState.WAITING_FOR_PAYMENT,
        )
