import os
import logging
import random
from pathlib import Path
from dotenv import load_dotenv
import warnings

# Suppress the FutureWarning from google.generativeai
with warnings.catch_warnings():
    warnings.simplefilter("ignore", category=FutureWarning)
    try:
        import google.generativeai as genai
    except ImportError:
        genai = None

try:
    from pinecone import Pinecone
except ImportError:
    Pinecone = None

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

GEMINI_API_KEY      = os.getenv("GEMINI_API_KEY", "").strip()
PINECONE_API_KEY    = (os.getenv("PINECONE_API_KEY") or os.getenv("PINECONE_KEY") or "").strip()
PINECONE_INDEX_NAME = "autoserve"

# --- In-Memory Database for Order Management ---
orders_db = {}

def place_order(product_name: str, quantity: int, customer_address: str) -> str:
    """Places a new order for a product and returns the tracking Order ID."""
    order_id = f"ORD-{random.randint(1000, 9999)}"
    orders_db[order_id] = {
        "status": "Processing",
        "product": product_name,
        "quantity": quantity,
        "address": customer_address
    }
    return f"SUCCESS: Order placed. Order ID is {order_id}."

def cancel_order(order_id: str) -> str:
    """Cancels an existing order using the Order ID."""
    if order_id in orders_db:
        orders_db[order_id]["status"] = "Cancelled"
        return f"SUCCESS: Order {order_id} has been cancelled."
    return f"ERROR: Order {order_id} not found."

def track_order(order_id: str) -> str:
    """Checks the status of an existing order using the Order ID."""
    if order_id in orders_db:
        order = orders_db[order_id]
        return f"STATUS: {order['status']} - {order['quantity']}x {order['product']} shipping to {order['address']}."
    return f"ERROR: Order {order_id} not found."

# --- Main Chat Model ---
class GeminiChatModel:
    def __init__(self):
        self.ready = False
        self.error = ""
        self.pc = None
        self.index = None
        self.embedding_model = None
        self.sessions = {} # Dictionary to store chat sessions by user phone number
        self._initialize()

    def _initialize(self) -> None:
        if genai is None:
            self.error = "google-generativeai not installed."
            logger.error(self.error)
            return

        if not GEMINI_API_KEY:
            self.error = "GEMINI_API_KEY missing. Add it to your .env file."
            logger.error(self.error)
            return

        try:
            genai.configure(api_key=GEMINI_API_KEY)
            
            # Initialize Pinecone
            if Pinecone is not None and PINECONE_API_KEY:
                try:
                    self.pc = Pinecone(api_key=PINECONE_API_KEY)
                    available_indexes = [i.name for i in self.pc.list_indexes()]
                    if PINECONE_INDEX_NAME in available_indexes:
                        self.index = self.pc.Index(name=PINECONE_INDEX_NAME)
                        if SentenceTransformer is not None:
                            self.embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
                        logger.info("✅ Pinecone connected successfully")
                    else:
                        logger.warning("⚠️ Pinecone index not found, skipping")
                except Exception as e:
                    logger.warning("⚠️ Pinecone init failed: %s", e)
            
            self.ready = True
            logger.info("✅ GeminiChatModel ready!")
        except Exception as e:
            self.error = str(e)
            self.ready = False
            logger.error("❌ Initialization failed: %s", e)

    def _search_pinecone_products(self, query: str, limit: int = 3) -> list:
        if not self.embedding_model or not self.index:
            return []

        try:
            vector = self.embedding_model.encode(query, convert_to_numpy=True).tolist()
            results = self.index.query(vector=vector, top_k=limit, include_metadata=True)

            matches = []
            if isinstance(results, dict) and "matches" in results:
                matches = results["matches"] or []
            elif hasattr(results, "matches"):
                matches = getattr(results, "matches") or []

            products = []
            for match in matches:
                meta = match.metadata if hasattr(match, "metadata") else match.get("metadata", {})
                products.append({
                    "name": meta.get("name") or meta.get("text") or meta.get("title") or meta.get("item") or "Unknown Item",
                    "price": meta.get("discount_price") or meta.get("price") or meta.get("cost") or "N/A",
                    "category": meta.get("main_category") or meta.get("category") or meta.get("type") or "",
                    "description": meta.get("description") or meta.get("details") or ""
                })
            return products
        except Exception as e:
            logger.warning("Pinecone search error: %s", e)
            return []

    def _format_context(self, products: list) -> str:
        if not products:
            return ""
        lines = ["\n[DATABASE CONTEXT - Items Available]"]
        for i, p in enumerate(products, 1):
            details = [f"{p['name']}"]
            if p['price'] and p['price'] != "N/A": details.append(f"Price: {p['price']}")
            if p['category']: details.append(f"Category: {p['category']}")
            if p['description']: details.append(f"Info: {p['description'][:100]}")
            lines.append(f"{i}. " + " | ".join(details))
        return "\n".join(lines)

    def get_or_create_session(self, sender_number: str):
        if sender_number not in self.sessions:
            system_instruction = (
                "You are Zara, a helpful and polite AI assistant for our local business. "
                "Your goal is to help customers find what they need from our catalog, answer their questions, and help them place, cancel, or track orders. "
                "When a user asks to place an order, ALWAYS ask for: 1. The exact item name(s) 2. Quantity 3. Delivery/Shipping Address. "
                "Do NOT place the order until you have collected all three pieces of information from the user. "
                "When you have all the information, use the place_order tool. "
                "Keep your responses friendly, very concise (max 2 sentences), and in plain text."
            )
            model = genai.GenerativeModel(
                model_name="gemini-flash-latest",
                system_instruction=system_instruction,
                tools=[place_order, cancel_order, track_order]
            )
            # Enable automatic function calling so Gemini runs the python tools automatically!
            self.sessions[sender_number] = model.start_chat(enable_automatic_function_calling=True)
        return self.sessions[sender_number]

    def generate(self, sender_number: str, user_input: str) -> str:
        if not self.ready:
            return f"Model not ready: {self.error}"
        if genai is None:
            return "Gemini API not available."

        try:
            # Get matching products to provide context to Gemini
            products = self._search_pinecone_products(user_input)
            context = self._format_context(products)

            # Combine the user's message with the database context silently
            prompt = f"{context}\n\nUser Message: {user_input}" if context else user_input

            # Send message to the user's specific stateful chat session
            chat_session = self.get_or_create_session(sender_number)
            response = chat_session.send_message(prompt)

            reply = getattr(response, "text", None)
            if not reply and hasattr(response, "candidates"):
                try:
                    reply = response.candidates[0].content.parts[0].text
                except Exception:
                    reply = None

            return reply.strip() if reply else "I'm here to help! What electronics or gadgets are you looking for?"

        except Exception as e:
            logger.error("Generation error: %s", e, exc_info=True)
            return "Something went wrong. Please try again."


# Create global instance
chat_model = GeminiChatModel()

def initialize_model() -> bool:
    global chat_model
    if chat_model.ready:
        logger.info("✅ Chat model initialized successfully")
        return True
    else:
        logger.warning("⚠️ Chat model failed to initialize: %s", chat_model.error)
        return False

def get_chat_response(sender_number: str, msg: str) -> str:
    # Use sender_number to track conversation state per user
    return chat_model.generate(sender_number, msg)


if __name__ == "__main__":
    if initialize_model():
        test_sender = "123456789"
        test = "Do you have any smartphones under 20000?"
        print(f"\nUser: {test}")
        print(f"Bot : {get_chat_response(test_sender, test)}")
