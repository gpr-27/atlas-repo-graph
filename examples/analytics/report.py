import csv


def customers(path: str) -> set[str]:
    with open(path, newline="") as f:
        return {row["customer_id"] for row in csv.DictReader(f)}
