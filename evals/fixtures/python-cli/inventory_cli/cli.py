"""Command parsing and local inventory operations."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from . import store


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage an inventory in a local JSON file")
    parser.add_argument("--data", type=Path, default=Path(".inventory.json"))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="List items without changing the data file")
    add = commands.add_parser("add", help="Add a quantity to an item")
    add.add_argument("name")
    add.add_argument("quantity", type=int)
    remove = commands.add_parser("remove", help="Remove an item entirely")
    remove.add_argument("name")
    args = parser.parse_args(argv)
    try:
        items = store.load(args.data)
        if args.command == "list":
            for name, quantity in items.items():
                print(f"{name}\t{quantity}")
        elif args.command == "add":
            if not args.name.strip() or args.quantity <= 0:
                raise ValueError("Item name must be non-empty and quantity must be positive")
            items[args.name] = items.get(args.name, 0) + args.quantity
            store.save(args.data, items)
            print(f"{args.name}\t{items[args.name]}")
        else:
            if args.name not in items:
                raise ValueError(f"Unknown item: {args.name}")
            del items[args.name]
            store.save(args.data, items)
            print(f"Removed {args.name}")
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0

