CREATE CONSTRAINT customer_id_unique IF NOT EXISTS
FOR (c:Customer)
REQUIRE c.id IS UNIQUE;

CREATE CONSTRAINT item_id_unique IF NOT EXISTS
FOR (i:Item)
REQUIRE i.id IS UNIQUE;

CREATE CONSTRAINT order_id_unique IF NOT EXISTS
FOR (o:Order)
REQUIRE o.id IS UNIQUE;

CREATE INDEX item_name_idx IF NOT EXISTS
FOR (i:Item)
ON (i.name);

CREATE INDEX customer_name_idx IF NOT EXISTS
FOR (c:Customer)
ON (c.name);

CREATE (c1:Customer {id:'cust_001', name:'Andrii'})
CREATE (c2:Customer {id:'cust_002', name:'Denys'});

CREATE (i1:Item {id:'item_001', name:'Phone', price:600.00, currency:'USD'});
CREATE (i2:Item {id:'item_002', name:'TV',    price:1200.00, currency:'USD'});
CREATE (i3:Item {id:'item_003', name:'Watch', price:399.00, currency:'USD'});

CREATE (o1:Order {id:'ord_001', createdAt:datetime(), status:'CREATED'});
CREATE (o2:Order {id:'ord_002', createdAt:datetime(), status:'PAID'});
CREATE (o3:Order {id:'ord_003', createdAt:datetime(), status:'PAID'});
CREATE (o4:Order {id:'ord_004', createdAt:datetime(), status:'PAID'});

MATCH (c1:Customer {id:'cust_001'}), (o1:Order {id:'ord_001'}), (o2:Order {id:'ord_002'})
CREATE (c1)-[:MADE]->(o1),
       (c1)-[:MADE]->(o2);

MATCH (c1:Customer {id:'cust_002'}), (o1:Order {id:'ord_003'}), (o2:Order {id:'ord_004'})
CREATE (c1)-[:MADE]->(o1),
       (c1)-[:MADE]->(o2);

MATCH (o1:Order {id:'ord_001'}), (o2:Order {id:'ord_002'}), (o3:Order {id:'ord_003'}), (o4:Order {id:'ord_004'}),
      (i1:Item {id:'item_001'}), (i2:Item {id:'item_002'}), (i3:Item {id:'item_003'})
CREATE (o1)-[:CONTAINS {qty: 1, unitPriceAtPurchase: i1.price, addedAt: datetime()}]->(i1),
       (o1)-[:CONTAINS {qty: 2, unitPriceAtPurchase: i3.price, addedAt: datetime()}]->(i3),
       (o2)-[:CONTAINS {qty: 1, unitPriceAtPurchase: i2.price, addedAt: datetime()}]->(i2),
       (o2)-[:CONTAINS {qty: 1, unitPriceAtPurchase: i1.price, addedAt: datetime()}]->(i1),
       (o3)-[:CONTAINS {qty: 1, unitPriceAtPurchase: i2.price, addedAt: datetime()}]->(i2),
       (o3)-[:CONTAINS {qty: 1, unitPriceAtPurchase: i3.price, addedAt: datetime()}]->(i3),
       (o4)-[:CONTAINS {qty: 1, unitPriceAtPurchase: i3.price, addedAt: datetime()}]->(i3);

MATCH (c2:Customer {id:'cust_002'}), (i1:Item {id:'item_001'}), (i2:Item {id:'item_002'})
CREATE (c2)-[:VIEWED {at: datetime()}]->(i1),
       (c2)-[:VIEWED {at: datetime()}]->(i2);

// 1) Знайти Items які входять в конкретний Order
MATCH (o:Order {id:'ord_001'})-[r:CONTAINS]->(i:Item)
RETURN i, r;

// 2) Підрахувати вартість конкретного Order
MATCH (o:Order {id:'ord_001'})-[r:CONTAINS]->(:Item)
RETURN o.id AS orderId, sum(r.qty * r.unitPriceAtPurchase) AS total;

// 3) Знайти всі Orders конкретного Customer
MATCH (c:Customer {id:'cust_001'})-[:MADE]->(o:Order)
RETURN o
ORDER BY o.createdAt DESC;

// 4) Знайти всі Items куплені конкретним Customer (через Order)
MATCH (c:Customer {id:'cust_001'})-[:MADE]->(:Order)-[:CONTAINS]->(i:Item)
RETURN DISTINCT i;

// 5) Знайти кількість Items куплені конкретним Customer (через Order)  (сума qty)
MATCH (c:Customer {id:'cust_001'})-[:MADE]->(:Order)-[r:CONTAINS]->(:Item)
RETURN c.id AS customerId, sum(r.qty) AS itemsQty;

// 6) Знайти для Customer на яку суму він придбав товарів (через Order)
MATCH (c:Customer {id:'cust_001'})-[:MADE]->(:Order)-[r:CONTAINS]->(:Item)
RETURN c.id AS customerId, sum(r.qty * r.unitPriceAtPurchase) AS totalSpent;

// 7) Знайти скільки разів кожен товар був придбаний, відсортувати за цим значенням
MATCH (:Order)-[r:CONTAINS]->(i:Item)
RETURN i.id AS itemId, i.name AS name, sum(r.qty) AS timesPurchased
ORDER BY timesPurchased DESC;

// 8) Знайти всі Items переглянуті (view) конкретним Customer
MATCH (c:Customer {id:'cust_002'})-[v:VIEWED]->(i:Item)
RETURN i, v
ORDER BY v.at DESC;

// 9) Знайти інші Items що купувались разом з конкретним Item
MATCH (i:Item {id:'item_001'})<-[:CONTAINS]-(o:Order)-[:CONTAINS]->(other:Item)
WHERE other.id <> i.id
RETURN DISTINCT other;

// 10) Знайти Customers які купили даний конкретний Item
MATCH (c:Customer)-[:MADE]->(:Order)-[:CONTAINS]->(i:Item {id:'item_001'})
RETURN DISTINCT c;

// 11) Знайти для певного Customer товари, які він переглядав, але не купив
MATCH (c:Customer {id:'cust_002'})-[:VIEWED]->(i:Item)
WHERE NOT EXISTS {
  MATCH (c)-[:MADE]->(:Order)-[:CONTAINS]->(i)
}
RETURN DISTINCT i;