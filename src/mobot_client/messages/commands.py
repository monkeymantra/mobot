# Copyright (c) 2021 MobileCoin. All rights reserved.

from . import CaseInsensitiveEnum


class CustomerChatCommands(CaseInsensitiveEnum):
    YES = 'yes', 'y'
    NO = 'no', 'n', 'cancel', 'c'
    PAY = 'pay'
    DESCRIBE = 'describe'
    HELP = 'help', '?'
    PRIVACY = 'p', 'privacy', 'privacy policy'
    REFUND = 'refund'
    CHART = 'chart'
    INFO = 'info'
    TERMS = 'terms'
    NAME = 'name'

    @classmethod
    def default(cls):
        return cls.HELP
