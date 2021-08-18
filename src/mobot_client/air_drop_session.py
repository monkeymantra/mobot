# Copyright (c) 2021 MobileCoin. All rights reserved.

import random

from decimal import Decimal
from mobot_client.drop_session import BaseDropSession
from mobot_client.models import (
    DropSession, Drop,
    BonusCoin, SessionState, Message
)

import mobilecoin as mc
from mobot_client.messages.chat_strings import ChatStrings
from mobot_client.messages.commands import CustomerChatCommands


class AirDropSession(BaseDropSession):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def is_minimum_coin_available(self, drop: Drop) -> bool:
        unspent_pmob = self.payments.get_unspent_pmob()
        return unspent_pmob >= (
                drop.initial_coin_amount_pmob + int(self.payments.get_minimum_fee_pmob())
        )

    def _check_drop_can_fulfill(self, drop: Drop):
        return super(AirDropSession, self)._check_drop_can_fulfill(drop) and self.is_minimum_coin_available(drop)

    def handle_airdrop_payment(self, source, customer, amount_paid_mob, drop_session):
        if not self.is_minimum_coin_available(drop_session.drop):
            self.messenger.log_and_send_message(
                customer,
                source,
                ChatStrings.AIRDROP_SOLD_OUT_REFUND.format(amount=amount_paid_mob.normalize())
            )
            self.send_mob_to_customer(customer, source, amount_paid_mob, True)
            return

        bonus_coin_objects_for_drop = BonusCoin.objects.filter(drop=drop_session.drop)
        bonus_coins = []

        for bonus_coin in bonus_coin_objects_for_drop:
            number_claimed = DropSession.objects.filter(
                drop=drop_session.drop, bonus_coin_claimed=bonus_coin
            ).count()
            number_remaining = bonus_coin.number_available - number_claimed
            bonus_coins.extend([bonus_coin] * number_remaining)

        if len(bonus_coins) <= 0:
            self.messenger.log_and_send_message(
                customer,
                source,
                ChatStrings.BONUS_SOLD_OUT_REFUND.format(amount=amount_paid_mob.normalize())
            )
            self.send_mob_to_customer(customer, source, amount_paid_mob, True)
        else:
            initial_coin_amount_mob = mc.pmob2mob(
                drop_session.drop.initial_coin_amount_pmob
            )
            random_index = random.randint(0, len(bonus_coins) - 1)
            amount_in_mob = mc.pmob2mob(bonus_coins[random_index].amount_pmob)
            amount_to_send_mob = (
                    amount_in_mob
                    + amount_paid_mob
                    + mc.pmob2mob(self.payments.get_minimum_fee_pmob())
            )
            self.payments.send_mob_to_customer(customer, source, amount_to_send_mob, True)
            drop_session.bonus_coin_claimed = bonus_coins[random_index]
            total_prize = Decimal(initial_coin_amount_mob + amount_in_mob)
            self.messenger.log_and_send_message(
                customer,
                source,
                ChatStrings.REFUND_SENT.format(amount=amount_to_send_mob.normalize(), total_prize=total_prize.normalize())
            )
            self.messenger.log_and_send_message(
                customer, source, ChatStrings.PRIZE.format(prize=total_prize.normalize())
            )
            self.messenger.log_and_send_message(
                customer,
                source,
                ChatStrings.AIRDROP_COMPLETED
            )

            # This is an exception-free, django-friendly way of finding out if a customer has store preferences
            if hasattr(customer, 'customer_store_preferences'):
                self.messenger.log_and_send_message(
                    customer, source, ChatStrings.BYE
                )
                drop_session.state = SessionState.COMPLETED
            else:
                self.messenger.log_and_send_message(
                    customer, source, ChatStrings.NOTIFICATIONS_ASK
                )
                drop_session.state = SessionState.ALLOW_CONTACT_REQUESTED
        drop_session.save()

    def handle_drop_session_waiting_for_bonus_transaction(self, message, drop_session):
        print("----------------WAITING FOR BONUS TRANSACTION------------------")
        command = CustomerChatCommands[message.text]
        # CustomerChatCommands falls back to HELP
        if command == CustomerChatCommands.HELP:
            self.log_and_send_message_to_customer(drop_session, ChatStrings.AIRDROP_COMMANDS)
        elif command == CustomerChatCommands.PAY:
            self.log_and_send_message_to_customer(drop_session, ChatStrings.PAY_HELP)
        elif command == CustomerChatCommands.DESCRIBE:
            self.log_and_send_message_to_customer(drop_session, ChatStrings.AIRDROP_INSTRUCTIONS)

        amount_in_mob = mc.pmob2mob(drop_session.drop.initial_coin_amount_pmob)

        value_in_currency = amount_in_mob * Decimal(
            drop_session.drop.conversion_rate_mob_to_currency
        )

        self.log_and_send_message_to_customer(
            drop_session,
            ChatStrings.AIRDROP_RESPONSE.format(
                amount=amount_in_mob.normalize(),
                symbol=drop_session.drop.currency_symbol,
                value=value_in_currency
            )
        )

    def handle_drop_cannot_fulfill(self, drop_session: DropSession):
        self.log_and_send_message_to_customer(
            drop_session.customer,
            ChatStrings.AIRDROP_OVER
        )
        drop_session.state = SessionState.COMPLETED


    def handle_drop_session_ready_to_receive(self, message, drop_session: DropSession):
        command = CustomerChatCommands[message.text]
        if command is CustomerChatCommands.NO:
            drop_session.state = SessionState.CANCELLED
            drop_session.save()
            self.messenger.log_and_send_message(
                drop_session.customer,
                message.source,
                ChatStrings.SESSION_CANCELLED
            )
        elif command is CustomerChatCommands.YES:
            if not self.under_drop_quota(drop_session.drop):
                self.messenger.log_and_send_message(
                    drop_session.customer,
                    message.source,
                    ChatStrings.AIRDROP_OVER
                )
                drop_session.state = SessionState.COMPLETED
            if not self._check_drop_can_fulfill(drop_session.drop):
                self.handle_drop_cannot_fulfill(drop_session)
            else:
                amount_in_mob = mc.pmob2mob(drop_session.drop.initial_coin_amount_pmob)
                value_in_currency = Decimal(drop_session.drop.value_in_currency(amount_in_mob))
                self.payments.send_mob_to_customer(drop_session.customer, message.source, amount_in_mob, True)
                self.log_and_send_message_to_customer(
                    drop_session.customer,
                    ChatStrings.AIRDROP_INITIALIZE.format(
                        amount=amount_in_mob.normalize(),
                        symbol=drop_session.drop.currency_symbol,
                        value=value_in_currency
                    )
                )
                self.log_and_send_message_to_customer(drop_session.customer, ChatStrings.PAY_HELP)
                drop_session.state = SessionState.WAITING_FOR_PAYMENT_OR_BONUS_TX
        else:
            self.log_and_send_message_to_customer(
                drop_session.customer,
                ChatStrings.YES_NO_HELP
            )
        drop_session.save()

    def handle_active_airdrop_drop_session(self, message, drop_session):
        # TODO @Greg: Replace with signal/handler pattern for each state
        if drop_session.state == SessionState.READY:
            self.handle_drop_session_ready_to_receive(message, drop_session)
        elif drop_session.state == SessionState.WAITING_FOR_PAYMENT_OR_BONUS_TX:
            self.handle_drop_session_waiting_for_bonus_transaction(message, drop_session)
        elif drop_session.state == SessionState.ALLOW_CONTACT_REQUESTED:
            self.handle_drop_session_allow_contact_requested(message, drop_session)

    def handle_no_active_airdrop_drop_session(self, customer, message, drop):
        customer_payments_address = self.payments.get_payments_address(message.source)
        if self.customer_has_completed_airdrop(customer, drop):
            self.messenger.log_and_send_message(
                customer,
                message.source,
                ChatStrings.AIRDROP_SUMMARY
            )
        elif not customer.phone_number.country_code == int(drop.number_restriction):
            self.messenger.log_and_send_message(
                customer,
                message.source,
                ChatStrings.COUNTRY_RESTRICTED
            )
        elif not self.under_drop_quota(drop):
            self.log_and_send_message_to_customer(
                customer, ChatStrings.OVER_QUOTA
            )
        elif not self.is_minimum_coin_available(drop):
            self.log_and_send_message_to_customer(
                customer, ChatStrings.NO_COIN_LEFT
            )
        elif not customer_payments_address:
            self.log_and_send_message_to_customer(
                customer,
                ChatStrings.PAYMENTS_ENABLED_HELP.format(item_desc=drop.item.description),
            )
        else:
            new_drop_session, _ = DropSession.objects.get_or_create(
                customer=customer,
                drop=drop,
                state=SessionState.READY,
            )

            self.log_and_send_message_to_customer(
                customer,
                ChatStrings.AIRDROP_DESCRIPTION
            )
            self.log_and_send_message_to_customer(
                customer,
                ChatStrings.AIRDROP_INSTRUCTIONS,
            )
            self.log_and_send_message_to_customer(customer, ChatStrings.READY)
