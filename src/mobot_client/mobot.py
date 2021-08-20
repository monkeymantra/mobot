# Copyright (c) 2021 MobileCoin. All rights reserved.


import os
import mobilecoin as mc
import pytz
import logging

from signald_client import Signal

from mobot_client.logger import SignalMessenger
from mobot_client.models import (
    Customer,
    DropSession,
    Drop,
    CustomerStorePreferences,
    BonusCoin,
    ChatbotSettings,
    Order,
    Sku, DropType, OrderStatus
)
from mobot_client.models.states import SessionState

from mobot_client.air_drop_session import AirDropSession
from mobot_client.item_drop_session import ItemDropSession
from mobot_client.payments import Payments, TransactionStatus
from mobot_client.messages.chat_strings import ChatStrings


class MOBot:
    """
    MOBot is the container which holds all of the business logic relevant to a Drop.
    """

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.store = ChatbotSettings.load().store

        signald_address = os.getenv("SIGNALD_ADDRESS", "127.0.0.1")
        signald_port = os.getenv("SIGNALD_PORT", "15432")
        self.signal = Signal(
            self.store.phone_number, socket_path=(signald_address, int(signald_port))
        )
        self.messenger = SignalMessenger(self.signal, self.store)

        fullservice_address = os.getenv("FULLSERVICE_ADDRESS", "127.0.0.1")
        fullservice_port = os.getenv("FULLSERVICE_PORT", "9090")
        fullservice_url = f"http://{fullservice_address}:{fullservice_port}/wallet"
        self.mcc = mc.Client(url=fullservice_url)

        all_accounts_response = self.mcc.get_all_accounts()
        self.account_id = next(iter(all_accounts_response))
        account_obj = all_accounts_response[self.account_id]
        self.public_address = account_obj["main_address"]

        get_network_status_response = self.mcc.get_network_status()
        self.minimum_fee_pmob = int(get_network_status_response["fee_pmob"])
        self.sessions = {}

        self.payments = Payments(
            self.mcc,
            self.minimum_fee_pmob,
            self.account_id,
            self.store,
            self.messenger,
            self.signal,
            public_address=self.public_address
        )

        self.session = ItemDropSession(self.store, self.payments, self.messenger)

        # self.timeouts = Timeouts(self.messenger, self.payments, schedule=30, idle_timeout=60, cancel_timeout=300)

        bot_name = ChatbotSettings.load().name
        bot_avatar_filename = ChatbotSettings.load().avatar_filename
        self.logger.info("bot_avatar_filename", bot_avatar_filename)
        b64_public_address = mc.utility.b58_wrapper_to_b64_public_address(
            self.public_address
        )

        resp = self.signal.set_profile(
            bot_name, b64_public_address, bot_avatar_filename, True
        )
        self.logger.info("set profile response", resp)
        if resp.get('error'):
            self.logger.error(f"Error received setting profile: {resp.get('error')}")
            assert False, resp

        # Chat handlers defined in __init__ so they can be registered with the Signal instance
        @self.signal.payment_handler
        def handle_payment(source, receipt):
            receipt_status = None
            customer, _ = Customer.objects.get_or_create(phone_number=source)

            if isinstance(source, dict):
                source = source["number"]

            self.logger.info("received receipt", receipt)
            payment = self.payments.receive_payment(customer, receipt)
            if payment.drop_session:
                if payment.drop_session.drop.drop_type == DropType.AIRDROP:
                    air_drop = AirDropSession(self.store, self.payments, self.messenger)
                    air_drop.handle_airdrop_payment(payment)
                else:
                    payment = self.payments.handle_item_payment(
                        payment
                    )
                    item_drop_session = DropSession.objects.filter(
                        customer=customer,
                        drop__drop_type=DropType.ITEM,
                        state=SessionState.WAITING_FOR_PAYMENT_OR_BONUS_TX,
                    ).first()
                    if not item_drop_session:
                        self.messenger.log_and_send_message(
                            customer, source, ChatStrings.UNSOLICITED_PAYMENT
                        )
                        self.payments.send_mob_to_customer(customer, source, payment.amount_in_mob, False)
                    else:
                        self.payments.handle_item_payment(payment)
            else:
                self.logger.warning(f"Transaction failed")
                return "The transaction failed!"

        @self.signal.chat_handler("coins")
        def chat_router_coins(message, match):
            active_drop = Drop.objects.get_active_drop()
            if active_drop:
                bonus_coins = BonusCoin.objects.filter(drop=active_drop)
                message_to_send = ""
                for bonus_coin in bonus_coins:
                    number_claimed = DropSession.objects.filter(
                        bonus_coin_claimed=bonus_coin
                    ).count()
                    message_to_send += (
                        f"{number_claimed} / {bonus_coin.number_available_at_start} - {mc.pmob2mob(bonus_coin.amount_pmob).normalize()} claimed\n"
                    )
                return message_to_send
            else:
                return "No active drop to check on coins"

        @self.signal.chat_handler("items")
        def chat_router_items(message, match):
            active_drop = Drop.objects.get_active_drop()
            if active_drop is None:
                return "No active drop to check on items"

            skus = Sku.objects.filter(item=active_drop.item).order_by("sort_order")
            message_to_send = ""
            for sku in skus:
                number_ordered = Order.objects.filter(sku=sku).exclude(status=OrderStatus.CANCELLED).count()
                message_to_send += (
                    f"{sku.identifier} - {number_ordered} / {sku.quantity} ordered\n"
                )
            return message_to_send

        @self.signal.chat_handler("unsubscribe")
        def unsubscribe_handler(message, _match):
            customer, _ = Customer.objects.get_or_create(
                phone_number=message.source["number"]
            )

            store_preferences, _ = CustomerStorePreferences.objects.get_or_create(
                customer=customer, store=self.store
            )

            if store_preferences.allows_contact:
                store_preferences.allows_contact = False
                store_preferences.save()

                self.messenger.log_and_send_message(
                    customer, message.source, ChatStrings.DISABLE_NOTIFICATIONS
                )
            else:
                self.messenger.log_and_send_message(
                    customer, message.source, ChatStrings.NOTIFICATIONS_OFF
                )

        @self.signal.chat_handler("subscribe")
        def subscribe_handler(message, _match):
            customer, _ = Customer.objects.get_or_create(
                phone_number=message.source["number"]
            )
            store_preferences, _ = CustomerStorePreferences.objects.get_or_create(
                customer=customer, store=self.store
            )

            if store_preferences.allows_contact:
                self.messenger.log_and_send_message(
                    customer, message.source, ChatStrings.ALREADY_SUBSCRIBED
                )
                return

            store_preferences.allows_contact = True
            store_preferences.save()

            self.messenger.log_and_send_message(
                customer, message.source, ChatStrings.SUBSCRIBE_NOTIFICATIONS
            )

        @self.signal.chat_handler("")
        def chat_router(message, match):
            # Store the message
            print("\033[1;33m NOW ROUTING CHAT\033[0m", message)
            customer, _ = Customer.objects.get_or_create(
                phone_number=message.source["number"]
            )
            self.messenger.log_received(message, customer, self.store)
                # TODO: @Greg Replace with Custom Manager/QuerySets
            active_drop_session = DropSession.objects.get(
                customer=customer,
                drop__drop_type=DropType.AIRDROP,
                state__gte=SessionState.READY,
                state__lt=SessionState.COMPLETED,
            )

            if active_drop_session:
                self.logger.info(f"found active drop session in state {active_drop_session.state}")

                if not active_drop_session.manual_override:
                    air_drop = AirDropSession(self.store, self.payments, self.messenger)

                    air_drop.handle_active_airdrop_drop_session(
                        message, active_drop_session
                    )
            else:
                active_drop_session = DropSession.objects.filter(
                    customer=customer,
                    drop__drop_type=DropType.ITEM,
                    state__gte=ItemSessionState.WAITING_FOR_PAYMENT,
                    state__lt=ItemSessionState.COMPLETED,
                ).first()
                if active_drop_session:
                    self.logger.info(f"found active drop session in state {active_drop_session.state}")
                elif not active_drop_session.manual_override:
                    item_drop = ItemDropSession(self.store, self.payments, self.messenger)
                    item_drop.handle_active_item_drop_session(message, active_drop_session)
                else:
                    drop_to_advertise = Drop.objects.get_advertising_drop()
                    if drop_to_advertise is not None:
                        if not customer.phone_number.country_code == int(drop_to_advertise.phone_number_restriction):
                            self.messenger.log_and_send_message(
                                customer, message.source, ChatStrings.COUNTRY_RESTRICTED
                            )
                        else:
                            bst_time = drop_to_advertise.start_time.astimezone(
                                pytz.timezone(drop_to_advertise.timezone)
                            )
                            response_message = ChatStrings.STORE_CLOSED.format(
                                date=bst_time.strftime("%A, %b %d"),
                                time=bst_time.strftime("%-I:%M %p %Z"),
                                desc=drop_to_advertise.pre_drop_description
                            )
                            self.messenger.log_and_send_message(
                                customer, message.source, response_message
                            )
                    active_drop = Drop.objects.get_active_drop()
                    if active_drop is None:
                        self.messenger.log_and_send_message(
                            customer, message.source, ChatStrings.STORE_CLOSED_SHORT
                        )
                    else:
                        if active_drop.drop_type == DropType.AIRDROP:
                            air_drop = AirDropSession(self.store, self.payments, self.messenger)
                            air_drop.handle_no_active_airdrop_drop_session(
                                customer, message, active_drop
                            )
                        elif active_drop.drop_type == DropType.ITEM:
                            item_drop = ItemDropSession(self.store, self.payments, self.messenger)
                            item_drop.handle_no_active_item_drop_session(
                                customer, message, active_drop
                            )

    # FIXME: Handler for cancel/help?

    def run_chat(self):
        # print("Starting timeouts thread")
        # t = threading.Thread(target=self.timeouts.process_timeouts, args=(), kwargs={})
        # t.setDaemon(True)
        # t.start()

        print("Now running MOBot chat")
        self.signal.run_chat(True)
