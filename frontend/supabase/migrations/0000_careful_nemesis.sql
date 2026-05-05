CREATE TABLE "orders" (
	"id" serial PRIMARY KEY NOT NULL,
	"order_id" varchar(64) NOT NULL,
	"product" text NOT NULL,
	"quantity" integer NOT NULL,
	"address" text NOT NULL,
	"status" varchar(32) DEFAULT 'Processing' NOT NULL,
	"created_at" timestamp DEFAULT now() NOT NULL
);
