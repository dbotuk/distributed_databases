use('e_shop')

// 1) Створіть декілька товарів з різним набором властивостей Phone/TV/Smart Watch/ .... 
db.products.insertMany([
  {
    category: "Phone",
    model: "iPhone 6",
    producer: "Apple",
    price: 600
  },
  {
    category: "Phone",
    model: "Galaxy S23",
    producer: "Samsung",
    price: 999
  },
  {
    category: "TV",
    model: "Bravia X90J",
    producer: "Sony",
    price: 1200
  },
  {
    category: "TV",
    model: "OLED C2",
    producer: "LG",
    price: 1500
  },
  {
    category: "Smart Watch",
    model: "Apple Watch Series 8",
    producer: "Apple",
    price: 399
  }
]);

// 2) Напишіть запит, який виводіть усі товари (відображення у JSON)
db.products.find().pretty();

// 3) Підрахуйте скільки товарів у певної категорії
db.products.countDocuments({ category: "Phone" });

// 4) Підрахуйте скільки є різних категорій товарів
db.products.distinct("category").length;

// 5) Виведіть список всіх виробників товарів без повторів
db.products.distinct("producer");

// 6) Напишіть запити, які вибирають товари за різними критеріям і їх сукупності: 
// a) категорія та ціна (в проміжку) - конструкція $and, 
db.products.find({
  $and: [
    { category: "Phone" },
    { price: { $gte: 500, $lte: 1000 } }
  ]
}).pretty();

// b) модель чи одна чи інша - конструкція $or,
db.products.find({
  $or: [
    { model: "iPhone 6" },
    { model: "Galaxy S23" }
  ]
}).pretty();

// c) виробники з переліку - конструкція $in
db.products.find({
  producer: { $in: ["Apple", "Samsung"] }
}).pretty();

// 7) Оновить запитом (updateMany) певні товари, змінивши існуючі значення і додайте нові властивості (характеристики) усім товарам за певним критерієм
db.products.updateMany(
  { category: "Phone" },
  {
    $set: {
      price: 700,
      warranty: "24 months",
      inStock: true
    }
  }
);

// 8) Знайдіть товари у яких є (присутнє поле) певні властивості
db.products.find({
  warranty: { $exists: true }
}).pretty();

// 9) Для знайдених товарів збільшіть їх вартість на певну суму
db.products.updateMany(
  { category: "Phone" },
  { $inc: { price: 50 } }
);

// 10) Створіть кілька замовлень з різними наборами товарів, але так щоб один з товарів був у декількох замовленнях
const sharedItem = db.products.findOne({}, { _id: 1, price: 1 });
const item2 = db.products.findOne({ _id: { $ne: sharedItem._id } }, { _id: 1, price: 1 });
const item3 = db.products.findOne({ _id: { $nin: [sharedItem._id, item2._id] } }, { _id: 1, price: 1 });

db.orders.insertMany([
  {
    order_number: 201513,
    date: new Date("2026-02-05"),
    customer: {
      name: "Andrii",
      surname: "Rodionov",
      phones: [9876543, 1234567],
      address: "PTI, Peremohy 37, Kyiv, UA"
    },
    payment: { card_owner: "Andrii Rodionov", cardId: 12345678 },
    items_id: [sharedItem._id, item2._id],
    total_sum: sharedItem.price + item2.price
  },
  {
    order_number: 201514,
    date: new Date("2026-02-22"),
    customer: {
      name: "Denys",
      surname: "Botuk",
      phones: [2223334],
      address: "Khreshchatyk 1, Kyiv, UA"
    },
    payment: { card_owner: "Denys Botuk", cardId: 87654321 },
    items_id: [sharedItem._id, item3._id],
    total_sum: sharedItem.price + item3.price
  }
]);

// 11) Виведіть всі замовлення
db.orders.find().pretty();

// 12) Виведіть замовлення з вартістю більше певного значення
db.orders.find({ total_sum: { $gt: 1600 } }).pretty();

// 13) Знайдіть замовлення зроблені одним замовником
db.orders.find({
  "customer.name": "Andrii",
  "customer.surname": "Rodionov"
}).pretty();

// 14) Знайдіть всі замовлення з певним товаром (товарами) (шукати можна по ObjectId)
db.orders.find({ items_id: sharedItem._id }).pretty();

// 15) Додайте в усі замовлення з певним товаром ще один товар і збільште існуючу вартість замовлення на деяке значення Х
db.orders.updateMany(
  { items_id: sharedItem._id },
  {
    $addToSet: { items_id: item2._id },
    $inc: { total_sum: 50 }
  }
);

// 16) Виведіть тільки інформацію про кастомера і номери кредитної карт, для замовлень вартість яких перевищує певну суму
db.orders.find(
  { total_sum: { $gt: 1600 } },
  { _id: 0, order_number: 1, customer: 1, "payment.cardId": 1 }
).pretty();

// 17) Видаліть товар з замовлень, зроблених за певний період дат
db.orders.updateMany(
  { date: { $gte: new Date("2026-02-05"), $lt: new Date("2026-02-15") } },
  { $pull: { items_id: sharedItem._id } }
);

// 18) Перейменуйте у всіх замовлення ім'я (прізвище) замовника
db.orders.updateMany(
  {},
  { $set: { "customer.surname": "Renamed" } }
);

// 19) Для певного замовлення виведіть прізвище кастомера та товари у замовлені підставивши замість ref/ObjectId("***") назви товарів та їх вартість (аналог join-а між таблицями orders та items).
db.orders.aggregate([
  { $match: { order_number: 201514 } },
  {
    $lookup: {
      from: "products",
      localField: "items_id",
      foreignField: "_id",
      as: "items"
    }
  },
  {
    $project: {
      _id: 0,
      order_number: 1,
      customer_surname: "$customer.surname",
      items: {
        $map: {
          input: "$items",
          as: "p",
          in: { model: "$$p.model", price: "$$p.price", category: "$$p.category", producer: "$$p.producer" }
        }
      },
      total_sum: 1
    }
  }
]).pretty();

// 20) Створіть Сapped collection яка б містила 5 останніх відгуків на наш інтернет-магазин. Структуру запису визначіть самостійно.
db.createCollection("reviews", {
  capped: true,
  size: 4096,
  max: 5
});

db.reviews.insertMany([
  { createdAt: new Date(), customerName: "User1", rating: 5, text: "Great shop!" },
  { createdAt: new Date(), customerName: "User2", rating: 4, text: "Fast delivery." },
  { createdAt: new Date(), customerName: "User3", rating: 3, text: "Ok service." },
  { createdAt: new Date(), customerName: "User4", rating: 5, text: "Nice prices." },
  { createdAt: new Date(), customerName: "User5", rating: 2, text: "Packaging damaged." },
  { createdAt: new Date(), customerName: "User6", rating: 5, text: "Will buy again!" }
]);

// 21) Перевірте що при досягненні обмеження старі відгуки будуть затиратись
db.reviews.find().sort({ $natural: 1 }).pretty()
