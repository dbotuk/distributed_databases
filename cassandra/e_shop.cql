CREATE KEYSPACE IF NOT EXISTS shop
WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};

USE shop;

CREATE TABLE IF NOT EXISTS items (
  category text,
  price decimal,
  item_id uuid,
  name text,
  producer text,
  description text,
  attributes map<text, text>,
  PRIMARY KEY ((category), price, item_id)
) WITH CLUSTERING ORDER BY (price ASC);

CREATE INDEX IF NOT EXISTS items_name_idx     ON items (name);
CREATE INDEX IF NOT EXISTS items_producer_idx ON items (producer);
CREATE INDEX IF NOT EXISTS items_attr_keys_idx ON items (KEYS(attributes));
CREATE INDEX IF NOT EXISTS items_attr_entries_idx ON items (ENTRIES(attributes));

INSERT INTO items (category, price, item_id, name, producer, description, attributes)
VALUES ('Phone', 999.00, now(), 'Galaxy S23', 'Samsung', 'Flagship Android phone',
        {'ram':'8GB','storage':'256GB','color':'Black','nfc':'yes','os':'Android'});
INSERT INTO items (category, price, item_id, name, producer, description, attributes)
VALUES ('Phone', 1199.00, now(), 'iPhone 15 Pro', 'Apple', 'Premium iPhone',
        {'ram':'8GB','storage':'256GB','color':'Titanium','nfc':'yes','os':'iOS','esim':'yes'});
INSERT INTO items (category, price, item_id, name, producer, description, attributes)
VALUES ('Phone', 399.00, now(), 'Redmi Note 13', 'Xiaomi', 'Budget-friendly phone',
        {'ram':'6GB','storage':'128GB','color':'Blue','nfc':'no','os':'Android'});
INSERT INTO items (category, price, item_id, name, producer, description, attributes)
VALUES ('TV', 1200.00, now(), 'Bravia X90J', 'Sony', '4K LED TV',
        {'size':'55','resolution':'4K','panel':'LED','hdr':'yes','hdmi_ports':'4'});
INSERT INTO items (category, price, item_id, name, producer, description, attributes)
VALUES ('TV', 1500.00, now(), 'OLED C2', 'LG', '4K OLED TV',
        {'size':'55','resolution':'4K','panel':'OLED','hdr':'yes','refresh_rate':'120'});
INSERT INTO items (category, price, item_id, name, producer, description, attributes)
VALUES ('Smart Watch', 399.00, now(), 'Apple Watch Series 8', 'Apple', 'Smart watch',
        {'case_size':'45','gps':'yes','lte':'no','color':'Midnight','water_resistant':'50m'});
INSERT INTO items (category, price, item_id, name, producer, description, attributes)
VALUES ('Smart Watch', 299.00, now(), 'Galaxy Watch 6', 'Samsung', 'Wear OS watch',
        {'case_size':'44','gps':'yes','lte':'optional','color':'Silver','water_resistant':'50m'});

DESCRIBE TABLE shop.items;

SELECT category, price, item_id, name, producer, description, attributes
FROM items
WHERE category = 'Phone'
ORDER BY price ASC;

SELECT category, price, item_id, name, producer, attributes
FROM items
WHERE category = 'Phone'
  AND name = 'iPhone 15 Pro';

SELECT category, price, item_id, name, producer, attributes
FROM items
WHERE category = 'Phone'
  AND price >= 400.00
  AND price <= 1300.00;

SELECT category, price, item_id, name, producer, attributes
FROM items
WHERE category = 'TV'
  AND price >= 1000.00
  AND price <= 1600.00
  AND producer = 'LG';

SELECT category, price, item_id, name, producer, attributes
FROM items
WHERE category = 'Phone'
  AND attributes CONTAINS KEY 'nfc';

SELECT category, price, item_id, name, producer, attributes
FROM items
WHERE category = 'Phone'
  AND attributes['color'] = 'Black';

UPDATE items
SET description = 'Updated description: premium iPhone (2026)'
WHERE category = 'Phone'
  AND price = 1199.00
  AND item_id = 26db3e90-1040-11f1-8f83-2f072e51e983;
SELECT description
FROM items
WHERE category = 'Phone'
  AND price = 1199.00
  AND item_id = 26db3e90-1040-11f1-8f83-2f072e51e983;

UPDATE items
SET attributes['storage'] = '512GB'
WHERE category = 'Phone'
  AND price = 1199.00
  AND item_id = 26db3e90-1040-11f1-8f83-2f072e51e983;
SELECT attributes['storage']
FROM items
WHERE category = 'Phone'
  AND price = 1199.00
  AND item_id = 26db3e90-1040-11f1-8f83-2f072e51e983;

DELETE attributes['esim']
FROM items
WHERE category = 'Phone'
  AND price = 1199.00
  AND item_id = 26db3e90-1040-11f1-8f83-2f072e51e983;
SELECT attributes['esim']
FROM items
WHERE category = 'Phone'
  AND price = 1199.00
  AND item_id = 26db3e90-1040-11f1-8f83-2f072e51e983;

CREATE TABLE IF NOT EXISTS orders (
  customer_name text,
  order_time timestamp,
  order_id uuid,

  item_ids set<uuid>,
  total_cost decimal,
  currency text,
  status text,
  created_at timestamp,

  PRIMARY KEY ((customer_name), order_time, order_id)
) WITH CLUSTERING ORDER BY (order_time ASC);
CREATE INDEX IF NOT EXISTS orders_item_ids_idx ON orders (item_ids);

INSERT INTO orders (customer_name, order_time, order_id, item_ids, total_cost, currency, status, created_at)
VALUES (
  'Andrii Rodionov',
  '2026-02-05T12:10:00Z',
  now(),
  {11111111-1111-1111-1111-111111111111, 22222222-2222-2222-2222-222222222222},
  1550.00,
  'USD',
  'PAID',
  toTimestamp(now())
);
INSERT INTO orders (customer_name, order_time, order_id, item_ids, total_cost, currency, status, created_at)
VALUES (
  'Andrii Rodionov',
  '2026-02-01T12:10:00Z',
  now(),
  {11111111-1111-1111-1111-111111111111, 22222222-2222-2222-2222-222222222222},
  650.00,
  'UAH',
  'PAID',
  toTimestamp(now())
);
INSERT INTO orders (customer_name, order_time, order_id, item_ids, total_cost, currency, status, created_at)
VALUES (
  'Denys Botuk',
  '2026-03-01 14:30:00+0000',
  now(),
  {
    33333333-3333-3333-3333-333333333333,
    44444444-4444-4444-4444-444444444444
  },
  2200.00,
  'USD',
  'PAID',
  '2026-03-01 14:30:00+0000'
);

DESCRIBE TABLE orders;

SELECT customer_name, order_time, order_id, total_cost, currency, status, item_ids
FROM orders
WHERE customer_name = 'Andrii Rodionov';

SELECT customer_name, order_time, order_id, total_cost, item_ids
FROM orders
WHERE customer_name = 'Andrii Rodionov'
  AND item_ids CONTAINS 11111111-1111-1111-1111-111111111111;

SELECT order_time, order_id, total_cost, item_ids, count(*)
FROM orders
WHERE customer_name = 'Andrii Rodionov'
  AND order_time >= '2026-02-01T00:00:00Z'
  AND order_time <= '2026-02-04T23:59:59Z';

SELECT sum(total_cost)
FROM orders
WHERE customer_name = 'Andrii Rodionov';
SELECT sum(total_cost)
FROM orders
WHERE customer_name = 'Denys Botuk';

SELECT order_time, order_id, total_cost, item_ids
FROM orders
WHERE customer_name = 'Andrii Rodionov'
ORDER BY order_time DESC;

SELECT max(total_cost)
FROM orders
WHERE customer_name = 'Andrii Rodionov';
SELECT max(total_cost)
FROM orders
WHERE customer_name = 'Denys Botuk';

UPDATE orders
SET item_ids = item_ids + {33333333-3333-3333-3333-333333333333},
    total_cost = 1750.00
WHERE customer_name = 'Andrii Rodionov'
  AND order_time = '2026-02-05T12:10:00.000Z'
  AND order_id = 3af0d460-1047-11f1-8f83-2f072e51e983;
SELECT item_ids, total_cost
FROM orders
WHERE customer_name = 'Andrii Rodionov'
  AND order_time = '2026-02-05T12:10:00.000Z'
  AND order_id = 3af0d460-1047-11f1-8f83-2f072e51e983;

SELECT customer_name, order_time, order_id, total_cost, WRITETIME(total_cost)
FROM orders
WHERE customer_name = 'Andrii Rodionov';

INSERT INTO orders (customer_name, order_time, order_id, item_ids, total_cost, currency, status, created_at)
VALUES (
  'Andrii Rodionov',
  '2026-02-10T09:00:00Z',
  now(),
  {11111111-1111-1111-1111-111111111111},
  600.00,
  'USD',
  'NEW',
  toTimestamp(now())
) USING TTL 3600;
SELECT customer_name, order_time, order_id, total_cost, currency, status, item_ids
FROM orders
WHERE customer_name = 'Andrii Rodionov'