"""CLI real de la tienda. SQLite es local; importarlo no inicia la aplicación."""
import argparse
import json
import sqlite3


class Store:
    def __init__(self, database):
        self.connection = sqlite3.connect(database)
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS stock (sku TEXT PRIMARY KEY, quantity INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY, sku TEXT NOT NULL,
                quantity INTEGER NOT NULL, total_cents INTEGER NOT NULL
            );
            INSERT OR IGNORE INTO stock VALUES ('book', 5);
        """)
        self.connection.commit()

    def close(self):
        self.connection.close()

    def checkout(self, sku, quantity):
        if type(quantity) is not int or quantity <= 0:
            raise ValueError("quantity must be a positive integer")
        if sku != "book":
            raise ValueError("unknown product")
        with self.connection:
            result = self.connection.execute(
                "UPDATE stock SET quantity = quantity - ? WHERE sku = ? AND quantity >= ?",
                (quantity, sku, quantity),
            )
            if result.rowcount != 1:
                raise ValueError("insufficient stock")
            cursor = self.connection.execute(
                "INSERT INTO orders (sku, quantity, total_cents) VALUES (?, ?, ?)",
                (sku, quantity, quantity * 2500),
            )
        return {"id": cursor.lastrowid, "total_cents": quantity * 2500}

    def summary(self):
        raise NotImplementedError("sales summary pending")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", default="store.db")
    commands = parser.add_subparsers(dest="command", required=True)
    checkout = commands.add_parser("checkout")
    checkout.add_argument("--sku", default="book")
    checkout.add_argument("--quantity", type=int, default=1)
    commands.add_parser("summary")
    args = parser.parse_args()
    store = Store(args.database)
    try:
        result = store.checkout(args.sku, args.quantity) if args.command == "checkout" else store.summary()
        print(json.dumps(result))
    finally:
        store.close()


if __name__ == "__main__":
    main()
