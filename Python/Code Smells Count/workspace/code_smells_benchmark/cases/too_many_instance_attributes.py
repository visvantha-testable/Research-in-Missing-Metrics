"""Benchmark case: too-many-instance-attributes (R0902)."""


class TooManyAttributes:
    def __init__(self):
        self.attr01 = 1
        self.attr02 = 2
        self.attr03 = 3
        self.attr04 = 4
        self.attr05 = 5
        self.attr06 = 6
        self.attr07 = 7
        self.attr08 = 8
        self.attr09 = 9
        self.attr10 = 10
