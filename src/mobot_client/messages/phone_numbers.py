#  Copyright (c) 2021 MobileCoin. All rights reserved.
from phonenumbers import PhoneNumber


class MonkeyPatch():
    def new_str(self):
        return f"+{self.country_code}{self.national_number}"

    PhoneNumber.__str__ = new_str
