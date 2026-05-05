import { pgTable, serial, text, varchar } from "drizzle-orm/pg-core";

export const users = pgTable('users', {
  id: serial('id').primaryKey(),
  fullName: text('full_name'),
  phone: varchar('phone', { length: 256 }),
});

export const orders = pgTable('orders', {
  id: serial('id').primaryKey(),
  orderId: text('order_id'),
  product: text('product'),
  quantity: text('quantity'),
  address: text('address'),
  status: text('status'),
});
