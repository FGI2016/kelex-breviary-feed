#!/usr/bin/env python3

"""
test_office_resolver.py

Verifies the behavior of OfficeResolver.
"""

from types import SimpleNamespace

from office_resolver import OfficeResolver


def test_rank(
    resolver,
    rank
):

    liturgical_day = SimpleNamespace(
        rank=rank
    )

    result = resolver.resolve(
        liturgical_day
    )

    print()
    print(rank.upper())
    print("-" * len(rank))

    for office in (
        "oor",
        "mp",
        "dp",
        "ep",
        "np"
    ):

        print(
            f"{office:>3} : "
            f"{result[office]}"
        )


def main():

    resolver = OfficeResolver()

    print()
    print(
        "Office Resolver Test"
    )
    print(
        "===================="
    )

    for rank in (

        "weekday",
        "memorial",
        "feast",
        "solemnity"

    ):

        test_rank(
            resolver,
            rank
        )


if __name__ == "__main__":

    main()