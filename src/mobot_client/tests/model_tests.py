# Copyright (c) 2021 MobileCoin. All rights reserved.
from typing import List, Iterator, Dict
from collections import defaultdict

from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
import factory
import factory.random
from mobot_client.tests.factories import *
from django.db import transaction
import random


factory.random.reseed_random('mobot cleanup')

from mobot_client.models import Drop, DropSession, Item, Sku, Customer, Store, DropType, SessionState, BonusCoin, Order, OrderStatus
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

    def test_bonus_coin_available_works(self):
        drop_sessions = self.make_session(customer=self.customer, drop=self.air_drop, num=20)
        for session in drop_sessions:
            print(session.under_quota())

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

        print(sku_to_sell_out.number_available())
        self.assertFalse(sku_to_sell_out.in_stock())

    def test_airdrop_inventory(self):
        store = StoreFactory.create()
        drop = DropFactory.create(drop_type=DropType.AIRDROP, store=store)
        bonus_coin = BonusCoinFactory.create(drop=drop)
        drop_sessions = DropSessionFactory.create_batch(size=5, drop=drop, bonus_coin_claimed=bonus_coin)
        self.assertEqual(bonus_coin.number_remaining(), 5)