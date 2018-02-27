"""
Analyzes the dump of kafka data, that was created by benchmark.py.
Results (e.g. a merchant's profit and revenue) are saved to a CSV file.
"""

import argparse
import csv
import datetime
import itertools
import os
import json
from collections import defaultdict

import matplotlib.pyplot as plt


def load_merchant_id_mapping(directory):
    with open(os.path.join(directory, 'merchant_id_mapping.json')) as file:
        return json.load(file)


def analyze_kafka_dump(directory):
    merchant_id_mapping = load_merchant_id_mapping(directory)

    revenue = defaultdict(float)
    with open(os.path.join(directory, 'kafka', 'buyOffer')) as file:
        for event in json.load(file):
            revenue[event['merchant_id']] += event['amount'] * event['price']

    holding_cost = defaultdict(float)
    with open(os.path.join(directory, 'kafka', 'holding_cost')) as file:
        for event in json.load(file):
            holding_cost[event['merchant_id']] += event['cost']

    order_cost = defaultdict(float)
    with open(os.path.join(directory, 'kafka', 'producer')) as file:
        for event in json.load(file):
            order_cost[event['merchant_id']] += event['billing_amount']

    profit = {merchant_id: revenue[merchant_id] - holding_cost[merchant_id] - order_cost[merchant_id]
              for merchant_id in merchant_id_mapping}

    with open(os.path.join(directory, 'results.csv'), 'w') as file:
        writer = csv.writer(file)
        writer.writerow(['name', 'revenue', 'holding_cost', 'order_cost', 'profit'])
        for merchant_id in sorted(merchant_id_mapping, key=merchant_id_mapping.get):
            writer.writerow([merchant_id_mapping[merchant_id], revenue[merchant_id], holding_cost[merchant_id],
                             order_cost[merchant_id], profit[merchant_id]])

    create_inventory_graph(directory, merchant_id_mapping)
    create_price_graph(directory, merchant_id_mapping)


def create_inventory_graph(directory, merchant_id_mapping):
    """
    Calculates inventory levels from orders and sales and generates a graph from it.
    """
    sales = json.load(open(os.path.join(directory, 'kafka', 'buyOffer')))
    orders = json.load(open(os.path.join(directory, 'kafka', 'producer')))
    sales = [sale for sale in sales if sale['http_code'] == 200]
    for sale in sales:
        # TODO: ues better conversion; strptime discards timezone
        sale['timestamp'] = datetime.datetime.strptime(sale['timestamp'], '%Y-%m-%dT%H:%M:%S.%fZ')
    for order in orders:
        # TODO: ues better conversion; strptime discards timezone
        order['timestamp'] = datetime.datetime.strptime(order['timestamp'], '%Y-%m-%dT%H:%M:%S.%fZ')
    sale_index = 0
    order_index = 0
    inventory_progressions = defaultdict(list)

    while sale_index < len(sales) and order_index < len(orders):
        if sale_index >= len(sales):
            order = orders[order_index]
            inventory_progressions[order['merchant_id']].append((order['timestamp'], order['amount']))
            order_index += 1
        elif order_index >= len(orders):
            sale = sales[sale_index]
            inventory_progressions[sale['merchant_id']].append((sale['timestamp'], -1 * sale['amount']))
            sale_index += 1
        elif orders[order_index]['timestamp'] <= sales[sale_index]['timestamp']:
            order = orders[order_index]
            inventory_progressions[order['merchant_id']].append((order['timestamp'], order['amount']))
            order_index += 1
        else: # orders[order_index]['timestamp'] > sales[sale_index]['timestamp']
            sale = sales[sale_index]
            inventory_progressions[sale['merchant_id']].append((sale['timestamp'], -1 * sale['amount']))
            sale_index += 1

    fig, ax = plt.subplots()
    prices = create_price_graph(directory, merchant_id_mapping)
    for merchant_id in inventory_progressions:
        dates, inventory_changes = zip(*inventory_progressions[merchant_id])
        price_dates, prices = zip(*prices[merchant_id])
        inventory_levels = list(itertools.accumulate(inventory_changes))
        ax.plot(dates, inventory_levels, label='Lagerstand')
        ax.plot(price_dates, prices, 'r', label='Preis')
    #plt.ylabel('Inventory Level')
    fig.legend()
    fig.autofmt_xdate()
    fig.savefig(os.path.join(directory, 'inventory_levels'))


def create_price_graph(directory, merchant_id_mapping):
    new_offers = json.load(open(os.path.join(directory, 'kafka', 'addOffer')))
    updated_offers = json.load(open(os.path.join(directory, 'kafka', 'updateOffer')))
    offers = new_offers + updated_offers
    for offer in offers:
        # TODO: ues better conversion; strptime discards timezone
        offer['timestamp'] = datetime.datetime.strptime(offer['timestamp'], '%Y-%m-%dT%H:%M:%S.%fZ')
    offers.sort(key=lambda o: o['timestamp'])

    prices = defaultdict(list)
    # Assumption: each merchant has only one active offer
    for offer in offers:
        prices[offer['merchant_id']].append((offer['timestamp'], offer['price']))

    return prices
    fig, ax = plt.subplots()
    for merchant_id in prices:
        dates, prices = zip(*prices[merchant_id])
        ax.plot(dates, prices, label=merchant_id_mapping[merchant_id])
    plt.ylabel('Price')
    fig.legend()
    fig.autofmt_xdate()
    fig.savefig(os.path.join(directory, 'prices'))



def main():
    parser = argparse.ArgumentParser(description='Analyzes the data generated by benchmark.py')
    parser.add_argument('--directory', '-d', type=str, required=True)
    args = parser.parse_args()
    analyze_kafka_dump(args.directory)


if __name__ == '__main__':
    main()
