# Copyright (c) 2021 MobileCoin. All rights reserved.
from typing import List

from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
import factory



from mobot_client.models import Drop, DropSession, Item, Sku, Customer, Store, DropType, SessionState, BonusCoin


class ModelTests(TestCase):

    def _make_drop_sessions(self, customer: Customer, drop: Drop, num: int = 1):
        bonus_coin = BonusCoin.objects.create(
            drop=drop,
            amount_pmob=10 * 1e12,
            number_available=10
        )
        for i in range(num):
            yield DropSession.objects.create(
                customer=customer,
                drop =drop,
                bonus_coin_claimed = bonus_coin
            )


    def setUp(self):
        self.store = Store.objects.create(
            name="Test Store",
            phone_number='+18054412653',
            description='My Store',
            privacy_policy_url='https://example.com'
        )
        self.item = Item.objects.create(
            store=self.store,
            name='TestItem',
            price_in_pmob=20000000,
            description='My item',
            short_description='MI',
            image_link='https://example.com'
        )
        self.drop = Drop.objects.create(
            store=self.store,
            drop_type=DropType.ITEM,
            pre_drop_description = "A drop",
            advertisment_start_time = timezone.now(),
            start_time=timezone.now(),
            end_time=timezone.now(),
            item=self.item,
            number_restriction='+44',
            timezone='PST',
            initial_coin_amount_pmob=4*1e12,
            initial_coin_limit=2*1e12,
        )
        self.customer = Customer.objects.create(
            phone_number="+14045564883",
        )

    def test_makes_models(self):
        drop_sessions = self._make_drop_sessions(customer=self.customer, drop=self.drop, num=5)
        for session in drop_sessions:
            print(session.under_quota())

