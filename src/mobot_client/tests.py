# Copyright (c) 2021 MobileCoin. All rights reserved.
from typing import List

from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
import factory
import factory.random


factory.random.reseed_random('mobot cleanup')

from mobot_client.models import Drop, DropSession, Item, Sku, Customer, Store, DropType, SessionState, BonusCoin, ItemSessionState, Order


class StoreFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Store

    name = factory.Sequence(lambda n: f"Mobot Store #{n}")
    phone_number = factory.Sequence(lambda n: f"+44 2211 %06d" % n)
    description = factory.Faker('sentence', nb_words=50)
    privacy_policy_url = factory.Faker('url')


class DropFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Drop

    store = factory.SubFactory(StoreFactory)
    id = factory.Sequence(lambda n: n)
    pre_drop_description = factory.Sequence(lambda n: f"Item drop {n}")
    advertisment_start_time = timezone.now()
    start_time = timezone.now()
    end_time = timezone.now()
    item = factory.SubFactory('mobot_client.tests.ItemFactory')
    number_restriction = factory.Iterator(['+44', '+1'])
    timezone = 'PST'
    initial_coin_amount_pmob = 4 * 1e12
    initial_coin_limit = 2 * 1e12


class ItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Item

    store = factory.SubFactory(StoreFactory)
    name = factory.Faker('name')
    price_in_pmob = 5*1e12
    description = factory.Faker('sentence', nb_words=50)
    short_description = factory.Faker('sentence', nb_words=10)
    image_link = factory.Sequence(lambda n: f"https://img.com/image{n}")


class CustomerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Customer

    phone_number = factory.Sequence(lambda n: f"+44 7911 %06d" % n)
    drop_sessions = factory.RelatedFactoryList('mobot_client.tests.DropSessionFactory', factory_related_name='customer')


class BonusCoinFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BonusCoin

    drop = factory.SubFactory


class DropSessionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DropSession

    customer = factory.SubFactory(CustomerFactory)
    drop = factory.RelatedFactory(DropFactory)

    


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
        Store.objects.all().delete()
        Drop.objects.all().delete()
        DropSession.objects.all().delete()
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
        self.air_drop = Drop.objects.create(
            store=self.store,
            drop_type=DropType.AIRDROP,
            pre_drop_description="A drop",
            advertisment_start_time=timezone.now(),
            start_time=timezone.now(),
            end_time=timezone.now(),
            item=self.item,
            number_restriction='+44',
            timezone='PST',
            initial_coin_amount_pmob=4*1e12,
            initial_coin_limit=2*1e12,
        )
        self.item_drop = Drop.objects.create(
            store=self.store,
            drop_type=DropType.ITEM,
            pre_drop_description="An item drop",
            advertisment_start_time=timezone.now(),
            start_time=timezone.now(),
            end_time=timezone.now(),
            item=self.item,
            number_restriction='+44',
            timezone='PST',
            initial_coin_amount_pmob=4 * 1e12,
            initial_coin_limit=2 * 1e12,
        )

        self.customer = Customer.objects.create(
            phone_number="+14045564883",
        )

    def tearDown(self) -> None:
        pass

    # def test_bonus_coin_available_works(self):
    #     drop_sessions = self.make_session(customer=self.customer, drop=self.air_drop, num=20)
    #     for session in drop_sessions:
    #         print(session.under_quota())

    def test_items_available(self):
        store = StoreFactory.create()
        item = ItemFactory.create(store=store)
        drop = DropFactory.create(drop_type=DropType.ITEM, item=item, store=store)

        drop_sessions = DropSessionFactory.create_batch(1, state=ItemSessionState.NEW, drop=drop)
        skus = {
            variation: Sku.objects.create(
                item=self.item,
                identifier=variation,
                quantity=10,
            ) for variation in ('s', 'm', 'l')}
        for sku in skus.values():
            self.assertEqual(sku.number_available(), 10)
        for drop_session in drop_sessions:
            drop_session.state = ItemSessionState.COMPLETED



