import { pgTable, serial, text, varchar, integer, timestamp } from 'drizzle-orm/pg-core';

export const orders = pgTable('orders', {
	id: serial('id').primaryKey(),
	order_id: varchar('order_id', { length: 64 }).notNull(),
	product: text('product').notNull(),
	quantity: integer('quantity').notNull(),
	address: text('address').notNull(),
	status: varchar('status', { length: 32 }).notNull().default('Processing'),
	created_at: timestamp('created_at').notNull().defaultNow(),
});

export type Orders = typeof orders;
