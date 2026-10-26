import csv
def totals(path):
    with open(path) as f:
        for row in csv.DictReader(f):
            yield row["customer_id"], row.customer_id
