# Copyright (c) 2021 MobileCoin. All rights reserved.

from decimal import Decimal

from django.db import models
from django.db.models import F
from django.utils import timezone
from mobot_client.messages.phone_numbers import PhoneNumberField


import mobilecoin as mc

class SessionState(models.IntegerChoices):
    CANCELLED = -1, 'cancelled'
    READY_TO_RECEIVE_INITIAL = 0, 'ready_to_receive_initial'
    WAITING_FOR_BONUS_TRANSACTION = 1, 'waiting_for_bonus_tx'
    ALLOW_CONTACT_REQUESTED = 2, 'allow_contact_requested'
    COMPLETED = 3, 'completed'

    @staticmethod
    def active_states():
        return {
            SessionState.READY_TO_RECEIVE_INITIAL,
            SessionState.WAITING_FOR_BONUS_TRANSACTION,
            SessionState.ALLOW_CONTACT_REQUESTED,
        }


class Store(models.Model):
    name = models.TextField()
    phone_number = PhoneNumberField()
    description = models.TextField()
    privacy_policy_url = models.TextField()

    def __str__(self):
        return f"{self.name} ({self.phone_number})"


class Item(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="items")
    name = models.TextField()
    price_in_pmob = models.PositiveIntegerField(default=None, blank=True, null=True)
    description = models.TextField(default=None, blank=True, null=True)
    short_description = models.TextField(default=None, blank=True, null=True)
    image_link = models.TextField(default=None, blank=True, null=True)

    @property
    def price_in_mob(self) -> Decimal:
        return mc.pmob2mob(self.price_in_pmob)

    def __str__(self):
        return f"{self.name}"


class AvailableSkuManager(models.Manager):
    def get_queryset(self) -> models.QuerySet:
        return super().get_queryset().annotate(
            number_ordered=models.Count('orders'),
            available=F('quantity') - models.Count('orders')
        )


class Sku(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="skus")
    identifier = models.TextField()
    quantity = models.PositiveIntegerField(default=0)
    sort_order = models.PositiveIntegerField(default=0)

    def __str__(self) -> str:
        return f"{self.item.name} - {self.identifier}"

    def number_available(self) -> int:
        return self.quantity - self.orders.count()


class DropType(models.IntegerChoices):
    AIRDROP = 0, 'airdrop'
    ITEM = 1, 'item'


class DropQuerySet(models.QuerySet):
    def advertising_drops(self) -> models.QuerySet:
        return self.filter(
            dvertisment_start_time__lte=timezone.now(),
            start_time__gt=timezone.now()
        )

    def active_drops(self) -> models.QuerySet:
        return self.filter(
            start_time__lte=timezone.now(),
            end_time__gte=timezone.now()
        )


class DropManager(models.Manager.from_queryset(DropQuerySet)):
    def advertising_drops(self) -> DropQuerySet:
        return self.get_queryset().advertising_drops()

    def get_advertising_drop(self):
        return self.advertising_drops().first()

    def active_drops(self) -> DropQuerySet:
        return self.get_queryset().active_drops()

    def get_active_drop(self):
        return self.active_drops().first()


class Drop(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    drop_type = models.IntegerField(choices=DropType.choices, default=DropType.AIRDROP)
    pre_drop_description = models.TextField()
    advertisment_start_time = models.DateTimeField()
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='drops')
    number_restriction = models.TextField()
    timezone = models.TextField()
    initial_coin_amount_pmob = models.PositiveIntegerField(default=0)
    initial_coin_limit = models.PositiveIntegerField(default=0)
    conversion_rate_mob_to_currency = models.FloatField(default=1.0)
    currency_symbol = models.TextField(default="$")
    country_code_restriction = models.TextField(default="GB")
    country_long_name_restriction = models.TextField(default="United Kingdom")
    max_refund_transaction_fees_covered = models.PositiveIntegerField(default=0)

    objects = DropManager()

    def value_in_currency(self, amount):
        return amount * self.conversion_rate_mob_to_currency

    def __str__(self):
        return f"{self.store.name} - {self.item.name}"


class BonusCoin(models.Model):
    drop = models.ForeignKey(Drop, on_delete=models.CASCADE, related_name='bonus_coins')
    amount_pmob = models.PositiveIntegerField(default=0)
    number_available = models.PositiveIntegerField(default=0)

    def number_remaining(self) -> int:
        return self.number_available - self.drop.drop_sessions.filter(bonus_coin_claimed=self).count()


class Customer(models.Model):
    phone_number = PhoneNumberField(primary_key=True)
    received_sticker_pack = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.phone_number}"


class CustomerStorePreferences(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="customer_store_preferences")
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="customer_store_preferences")
    allows_contact = models.BooleanField()


class CustomerDropRefunds(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="drop_refunds")
    drop = models.ForeignKey(Drop, on_delete=models.CASCADE, related_name="drop_refunds")
    number_of_times_refunded = models.PositiveIntegerField(default=0)


class DropSessionManager(models.Manager):

    def under_drop_quota(drop: Drop) -> bool:
        number_initial_drops_finished = DropSession.objects.filter(
            drop=drop, state__gt=SessionState.READY_TO_RECEIVE_INITIAL
        ).count()
        return number_initial_drops_finished < drop.initial_coin_limit


    def active_sessions(self):
        self.get_queryset().filter(active=True)


class DropSession(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="drop_sessions")
    drop = models.ForeignKey(Drop, on_delete=models.CASCADE, related_name="drop_sessions")
    state = models.IntegerField(choices=SessionState.choices, default=SessionState.READY_TO_RECEIVE_INITIAL)
    manual_override = models.BooleanField(default=False)
    bonus_coin_claimed = models.ForeignKey(
        BonusCoin, on_delete=models.CASCADE, default=None, blank=True, null=True, related_name="drop_sessions"
    )

    objects = DropSessionManager()

    def under_quota(self) -> bool:
        return DropSession.objects.filter(drop=self.drop)\
            .aggregate(models.Sum('bonus_coin_claimed__amount_pmob'))


class MessageDirection(models.IntegerChoices):
    RECEIVED = 0, 'received'
    SENT = 1, 'sent'


class Message(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="messages")
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    text = models.TextField()
    date = models.DateTimeField(auto_now_add=True)
    direction = models.PositiveIntegerField(choices=MessageDirection.choices)


class OrderStatus(models.IntegerChoices):
    STARTED = 0, 'started'
    CONFIRMED = 1, 'confirmed'
    SHIPPED = 2, 'shipped'
    CANCELLED = 3, 'cancelled'


class OrderQuerySet(models.QuerySet):
    def active_orders(self) -> models.QuerySet:
        return self.filter(status__in=(OrderStatus.STARTED, OrderStatus.CONFIRMED, OrderStatus.SHIPPED))


class OrdersManager(models.Manager):
    def __init__(self, sku: Sku = None, active: bool = True, *args, **kwargs):
        self._sku = sku
        self._active = active
        super().__init__(*args, **kwargs)

    def get_queryset(self) -> models.QuerySet:
        return OrderQuerySet(
            model=self.model,
            using=self._db,
            hints=self._hints
        ).active_orders()



class Order(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="orders")
    drop_session = models.OneToOneField(DropSession, on_delete=models.CASCADE, blank=False, null=False, related_name='order')
    sku = models.ForeignKey(Sku, on_delete=models.CASCADE, related_name="orders")
    date = models.DateTimeField(auto_now_add=True)
    shipping_address = models.TextField(default=None, blank=True, null=True)
    shipping_name = models.TextField(default=None, blank=True, null=True)
    status = models.IntegerField(default=0, choices=OrderStatus.choices)
    conversion_rate_mob_to_currency = models.FloatField(default=0.0)

    active_orders = OrdersManager(None, True)
    objects = models.Manager()

    class Meta:
        base_manager_name = 'active_orders'


# ------------------------------------------------------------------------------------------


class SingletonModel(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.pk = 1
        super(SingletonModel, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj


class ChatbotSettings(SingletonModel):
    store = models.ForeignKey(Store, null=True, on_delete=models.SET_NULL)
    name = models.TextField()
    avatar_filename = models.TextField()

    def __str__(self):
        return "Global settings"


class ItemSessionState(models.IntegerChoices):
    IDLE_AND_REFUNDABLE = -4
    IDLE = -3
    REFUNDED = -2
    CANCELLED = -1
    NEW = 0
    WAITING_FOR_PAYMENT = 1
    WAITING_FOR_SIZE = 2
    WAITING_FOR_NAME = 3
    WAITING_FOR_ADDRESS = 4
    SHIPPING_INFO_CONFIRMATION = 5
    ALLOW_CONTACT_REQUESTED = 6
    COMPLETED = 7

    @staticmethod
    @property
    def active_states():
        return {
            ItemSessionState.NEW,
            ItemSessionState.WAITING_FOR_PAYMENT,
            ItemSessionState.WAITING_FOR_SIZE,
            ItemSessionState.WAITING_FOR_NAME,
            ItemSessionState.WAITING_FOR_ADDRESS,
            ItemSessionState.SHIPPING_INFO_CONFIRMATION,
            ItemSessionState.ALLOW_CONTACT_REQUESTED
        }

    @staticmethod
    @property
    def refundable_states():
        return {
            ItemSessionState.IDLE_AND_REFUNDABLE,
            ItemSessionState.WAITING_FOR_SIZE,
            ItemSessionState.WAITING_FOR_ADDRESS,
            ItemSessionState.WAITING_FOR_ADDRESS,
            ItemSessionState.WAITING_FOR_NAME,
            ItemSessionState.SHIPPING_INFO_CONFIRMATION
        }
