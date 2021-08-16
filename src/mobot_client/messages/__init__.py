# Copyright (c) 2021 MobileCoin. All rights reserved.

from aenum import MultiValueEnum


class CaseInsensitiveEnum(MultiValueEnum):
    """An enum with case-sensitive member searches and a default"""
    DEFAULT = 'default'

    @classmethod
    def default(cls):
        """Override this to set a default"""
        return cls.DEFAULT

    @classmethod
    def _missing_name_(cls, name):
        for member in cls:
            if member.name.lower() == name.lower():
                return member
        else:
            return cls.default()
