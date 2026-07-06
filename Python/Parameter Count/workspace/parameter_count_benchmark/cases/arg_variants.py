"""Benchmark case: positional-only, keyword-only, *args, **kwargs."""


def mixed_parameters(pos_only, /, regular, *args, kw_only, **kwargs):
    return pos_only + regular + sum(args) + kw_only + sum(kwargs.values())


def only_varargs(*items):
    return sum(items)


def only_kwargs(**options):
    return len(options)
