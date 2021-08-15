from aenum import MultiValueEnum


class CaseInsensitiveEnum(MultiValueEnum):
    @classmethod
    def _missing_name_(cls, name):
        for member in cls:
            if member.name.lower() == name.lower():
                return member

