# Copyright (c) 2021 MobileCoin. All rights reserved.
from typing import List, Dict
from collections import defaultdict

from django.test import TestCase
import factory.random
from mobot_client.tests.factories import *
from django.db import transaction
import random

factory.random.reseed_random('mobot cleanup')

from mobot_client.models import (Drop,
                                 DropSession,
                                 Item,
                                 Sku,
                                 Customer,
                                 Store,
                                 DropType,
                                 BonusCoin,
                                 Order,
                                 OrderStatus)
from mobot_client.models.states import SessionState


class ModelTests(TestCase):

    def make_session(self, customer: Customer, drop: Drop, bonus_coin: BonusCoin = None, state=None, num=1):
        bonus_coin = BonusCoin.objects.create(
            drop=drop,
            amount_pmob=10 * 1e12,
            number_available=10
        )
        for _ in range(num):
            yield DropSession.objects.create(
                customer=customer,
                drop=drop,
                bonus_coin_claimed=bonus_coin)

    def setUp(self):
        with transaction.atomic():
            Store.objects.all().delete()
            Drop.objects.all().delete()
            DropSession.objects.all().delete()

    def tearDown(self) -> None:
        pass

    def test_items_available(self):
        store = StoreFactory.create()
        item = ItemFactory.create(store=store)
        drop = DropFactory.create(drop_type=DropType.ITEM, store=store, item=item)
        skus: Dict[str, Sku] = {sku.identifier: sku for sku in SkuFactory.create_batch(size=3, item=item, quantity=10)}

        for sku in skus.values():
            self.assertEqual(sku.number_available(), 10)

        self.assertEqual(item.drops.count(), 1)

        print("Creating sessions...")
        drop_sessions: List[DropSession] = list(DropSessionFactory.create_batch(size=10, drop=drop))
        for drop_session in drop_sessions:
            self.assertEqual(drop_session.drop, drop)

        orders = defaultdict(list)

        for count, drop_session in enumerate(drop_sessions):
            print(f"Creating order for drop session {drop_session.pk}")
            order = Order.objects.create(
                customer=drop_session.customer,
                drop_session=drop_session,
                sku=list(skus.values())[count % 3],
                status=OrderStatus.CONFIRMED,
            )
            orders[sku.identifier].append(order)

        for sku in skus.values():
            self.assertEqual(sku.number_available(), (sku.quantity - sku.orders.count()))
            print("Cancelling an order to see if it affects sku availability")
            num_available_before_cancellation = sku.number_available()
            first_order = sku.orders.first()
            first_order.status = OrderStatus.CANCELLED
            first_order.save()
            print(f"Order for sku {sku.identifier} cancelled by customer {order.customer}")
            self.assertEqual(sku.number_available(), num_available_before_cancellation + 1)

        print("Attempting to sell out a SKU...")

        new_sessions = list(DropSessionFactory.create_batch(size=7, drop=drop))
        sku_to_sell_out = list(skus.values())[0]
        for session in new_sessions:
            order = Order.objects.create(
                customer=session.customer,
                drop_session=session,
                sku=sku_to_sell_out,
                status=OrderStatus.CONFIRMED,
            )
            print(f"Order confirmed. Inventory remaining for sku: {sku_to_sell_out.number_available()}")

        print(f"Asserting {sku_to_sell_out} no longer in stock...")
        self.assertFalse(sku_to_sell_out.in_stock())


    def test_airdrop_inventory(self):
        store = StoreFactory.create()
        drop = DropFactory.create(drop_type=DropType.AIRDROP, store=store)
        bonus_coin_1, bonus_coin_2, bonus_coin_3 = list(BonusCoinFactory.create_batch(size=3, drop=drop))
        sessions_by_coin = defaultdict(list)
        for session_id in range(10):
            session = DropSessionFactory.create(id=session_id, drop=drop, bonus_coin_claimed=random.choice([
                bonus_coin_1, bonus_coin_2, bonus_coin_3]), state=SessionState.READY)
            sessions_by_coin[session.bonus_coin_claimed].append(session)
        print(sessions_by_coin)

        for coin, sessions in sessions_by_coin.items():
            print(f"Asserting all coins still available for {coin}...")
            self.assertEqual(coin.number_remaining(), coin.number_available_at_start)
            for session in sessions:
                session.state = SessionState.WAITING_FOR_PAYMENT_OR_BONUS_TX
                session.save()
            self.assertEqual(coin.number_remaining(), coin.number_available_at_start - len(sessions))
            print(f"{coin.number_remaining} out of the original {coin.number_available_at_start}")
            self.assertEqual(coin.number_claimed(), len(sessions))
            print(f"Number claimed matches number of active sessions.")
