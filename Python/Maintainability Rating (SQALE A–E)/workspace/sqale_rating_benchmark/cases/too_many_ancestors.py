"""Benchmark case: too-many-ancestors (R0901)."""


class Base01:
    pass


class Base02(Base01):
    pass


class Base03(Base02):
    pass


class Base04(Base03):
    pass


class Base05(Base04):
    pass


class Base06(Base05):
    pass


class Base07(Base06):
    pass


class DeepChild(Base07):
    pass
