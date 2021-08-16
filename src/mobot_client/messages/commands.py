# Copyright (c) 2021 MobileCoin. All rights reserved.

from . import CaseInsensitiveEnum


class CustomerChatCommands(CaseInsensitiveEnum):
    YES = 'yes', 'y'
    NO = 'no', 'n', 'cancel'
    PAY = 'pay'
    DESCRIBE = 'describe'
    HELP = 'help', '?'
    PRIVACY = 'p', 'privacy'
    REFUND = 'refund'

    @classmethod
    def default(cls):
        return cls.HELP
