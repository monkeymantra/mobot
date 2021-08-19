# Copyright (c) 2021 MobileCoin. All rights reserved.
from typing import List, Iterator

from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
import factory
import factory.random
from mobot_client.tests.factories import *
from django.db import transaction


factory.random.reseed_random('mobot cleanup')

from mobot_client.models import Drop, DropSession, Item, Sku, Customer, Store, DropType, SessionState, BonusCoin, Order
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
        item = ItemFactory.create(store=store, store_id=store.id)
        drop = DropFactory.create(drop_type=DropType.ITEM, store=store, item=item)
        skus: Iterator[Sku] = SkuFactory.create_batch(size=3, item=item, quantity=10)

        for sku in skus:
            self.assertEqual(sku.number_available(), 10)

        self.assertEqual(item.drops.count(), 1)

        print("Creating sessions...")
        drop_sessions: Iterator[DropSession] = DropSessionFactory.create_batch(size=10, drop=drop)
        for drop_session in drop_sessions:
            self.assertEqual(drop_session.drop, drop)

        print("Creating some orders...")
        

        # skus = {
        #     variation: Sku.objects.create(
        #         item=self.item,
        #         identifier=variation,
        #         quantity=10,
        #     ) for variation in ('s', 'm', 'l')}
        # for sku in skus.values():
        #     self.assertEqual(sku.number_available(), 10)
        # for drop_session in drop_sessions:
        #     drop_session.state = ItemSessionState.COMPLETED
        #
        #
        #
