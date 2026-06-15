import os
import logging
import random
import csv
import re
from pathlib import Path
from typing import Any
from dotenv import load_dotenv
import warnings

with warnings.catch_warnings():
    warnings.simplefilter("ignore", category=FutureWarning)
    try:
        import google.generativeai as genai
    except ImportError:
        genai = None

try:
    from pinecone import Pinecone
except Exception as e:
    Pinecone = None
    print(f"Warning: Pinecone import failed: {e}")

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv()


def _get_env_value(*names: str) -> str:
    for name in names:
        value = (os.getenv(name) or "").strip().strip('"').strip("'")
        if value:
            return value
    return ""


GEMINI_API_KEY      = _get_env_value("GEMINI_API_KEY", "GOOGLE_API_KEY", "API_KEY")
GEMINI_MODEL_NAME   = _get_env_value("GEMINI_MODEL", "GEMINI_MODEL_NAME") or "models/gemini-2.5-flash"
PINECONE_API_KEY    = (os.getenv("PINECONE_API_KEY") or os.getenv("PINECONE_KEY") or "").strip()
PINECONE_INDEX_NAME = "autoserve"

# ---------------------------------------------------------------------------
orders_db = {}


def _frontend_api_base() -> str:
    return _get_env_value("FRONTEND_API_URL", "FRONTEND_URL") or "http://localhost:3000"


def _frontend_get(path: str, params: dict[str, str] | None = None):
    import requests

    url = f"{_frontend_api_base().rstrip('/')}{path}"
    return requests.get(url, params=params or {}, timeout=5)


def place_order(product_name: str, quantity: int, customer_address: str) -> str:
    order_id = f"ORD-{random.randint(1000, 9999)}"
    orders_db[order_id] = {
        "status":   "Processing",
        "product":  product_name,
        "quantity": quantity,
        "address":  customer_address,
    }

    # Try to persist order to frontend API if available
    try:
        import requests
        url = f"{_frontend_api_base().rstrip('/')}/api/orders"
        payload = {
            "order_id": order_id,
            "product": product_name,
            "quantity": quantity,
            "address": customer_address,
            "status": "Processing",
        }
        resp = requests.post(url, json=payload, timeout=5)
        if resp.ok:
            logger.info("Order persisted to frontend: %s", order_id)
    except Exception as e:
        logger.warning("Could not persist order to frontend API: %s", e)

    return f"SUCCESS: Order placed. Order ID is {order_id}."


def cancel_order(order_id: str) -> str:
    if order_id in orders_db:
        orders_db[order_id]["status"] = "Cancelled"
        return f"SUCCESS: Order {order_id} has been cancelled."
    return f"ERROR: Order {order_id} not found."


def track_order(order_id: str) -> str:
    if order_id in orders_db:
        o = orders_db[order_id]
        return f"STATUS: {o['status']} — {o['quantity']}x {o['product']} shipping to {o['address']}."
    try:
        resp = _frontend_get("/api/orders", {"order_id": order_id})
        if resp.ok:
            payload = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            order = payload.get("order") if isinstance(payload, dict) else None
            if isinstance(order, dict):
                return (
                    f"STATUS: {order.get('status') or 'Unknown'} — "
                    f"{order.get('quantity') or '1'}x {order.get('product') or 'Unknown'} shipping to {order.get('address') or 'Not shared'}."
                )
    except Exception as exc:
        logger.warning("Backend order tracking failed for %s: %s", order_id, exc)
    return f"ERROR: Order {order_id} not found."


# ---------------------------------------------------------------------------
# Price helpers
# ---------------------------------------------------------------------------

def _is_zero_or_empty(value: str) -> bool:
    v = (value or "").strip()
    if not v or v.upper() == "N/A":
        return True
    cleaned = v.replace("₹", "").replace("$", "").replace(",", "").strip()
    try:
        return float(cleaned) <= 0
    except ValueError:
        return False


def _clean_price(value: str) -> str:
    v = (value or "").strip()
    if _is_zero_or_empty(v):
        return "Price not listed"
    if "₹" in v or "$" in v:
        return v
    try:
        num = float(v.replace(",", ""))
        return f"₹{int(num):,}" if num == int(num) else f"₹{num:,.2f}"
    except ValueError:
        return v


def _is_quota_error_text(err_text: str) -> bool:
    t = (err_text or "").lower()
    markers = [
        "resourceexhausted",
        "quota",
        "exceeded",
        "429",
        "rate limit",
        "retry_delay",
        "generativelanguage.googleapis.com/generate_content",
    ]
    return any(m in t for m in markers)


def _savings_line(disc: str, actual: str) -> str:
    try:
        d = float(disc.replace("₹", "").replace("$", "").replace(",", "").strip())
        a = float(actual.replace("₹", "").replace("$", "").replace(",", "").strip())
        if a > d > 0:
            pct   = round((a - d) / a * 100)
            saved = f"₹{int(a - d):,}"
            return f"  🏷️  Save {pct}% ({saved} off MRP)"
    except Exception:
        pass
    return ""


def _meta_to_product(meta: dict) -> dict:
    """
    Convert a Pinecone metadata dict into a normalised product dict.
    Every field that is stored in Pinecone is extracted here.
    Prices stored as 0 / 0.0 are treated as 'not listed'.
    """
    def _price(key: str) -> str:
        raw = str(meta.get(key) or "").strip()
        return "" if _is_zero_or_empty(raw) else raw

    return {
        "name":           str(meta.get("name") or meta.get("title") or "Unknown").strip(),
        "main_category":  str(meta.get("main_category") or meta.get("category") or "").strip(),
        "sub_category":   str(meta.get("sub_category") or "").strip(),
        "image":          str(meta.get("image") or meta.get("image_url") or "").strip(),
        "link":           str(meta.get("link") or meta.get("url") or "").strip(),
        "ratings":        str(meta.get("ratings") or "N/A").strip(),
        "no_of_ratings":  str(meta.get("no_of_ratings") or "N/A").strip(),
        "discount_price": _price("discount_price"),
        "actual_price":   _price("actual_price"),
    }


# ===========================================================================
class GeminiChatModel:

    FETCH_BATCH = 200   # Pinecone fetch() accepts up to 1000 IDs at once

    def __init__(self):
        self.ready              = False
        self.error              = ""
        self.pc                 = None
        self.index              = None
        self.embedding_model    = None
        self.sessions           = {}
        self.catalog_offsets    = {}

        # Master product list — populated from Pinecone on first catalog request
        # and falls back to CSV if Pinecone is unavailable.
        self.all_products: list[dict] = []
        self.products_loaded          = False          # True once we've done a full fetch

        self.catalog_file       = Path(__file__).resolve().parent / "cleaned_electronics.csv"
        self.catalog_page_size  = 20

        self._load_csv_fallback()   # always load CSV so we have a safety net
        self._initialize()

    # ── 1. CSV fallback loader ───────────────────────────────────────────────
    def _load_csv_fallback(self) -> None:
        """Load ALL products from the local CSV into self.all_products."""
        if not self.catalog_file.exists():
            logger.warning("Catalog CSV not found: %s", self.catalog_file)
            return
        try:
            items = []
            with self.catalog_file.open("r", encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f):
                    name = (row.get("name") or "").strip()
                    if not name:
                        continue
                    items.append({
                        "name":           name,
                        "main_category":  (row.get("main_category") or "").strip(),
                        "sub_category":   (row.get("sub_category")  or "").strip(),
                        "image":          (row.get("image")         or "").strip(),
                        "link":           (row.get("link")          or "").strip(),
                        "ratings":        (row.get("ratings")       or "N/A").strip(),
                        "no_of_ratings":  (row.get("no_of_ratings") or "N/A").strip(),
                        "discount_price": (row.get("discount_price")or "").strip(),
                        "actual_price":   (row.get("actual_price")  or "").strip(),
                    })
            self.all_products = items
            logger.info("✅ CSV fallback loaded — %d products", len(items))
        except Exception as exc:
            logger.warning("CSV load failed: %s", exc)

    # ── 2. Fetch EVERY product from Pinecone using list() + fetch() ──────────
    def _load_all_from_pinecone(self) -> bool:
        """
        Use Pinecone's list() iterator to get ALL vector IDs, then fetch()
        them in batches to retrieve their full metadata.

        list() + fetch() is the ONLY correct way to get every record from
        Pinecone — query() only returns top-K nearest neighbours.

        Returns True if we successfully loaded at least one product.
        """
        if not self.index:
            return False

        try:
            logger.info("Fetching ALL product IDs from Pinecone via list()…")

            # ── Step 1: collect every vector ID ──────────────────────────────
            all_ids: list[str] = []

            # The Pinecone v3 client exposes index.list() as a paginated iterator.
            # Each page yields a list of IDs (strings).
            list_response: Any = self.index.list()            # returns a generator / iterator

            # Handle both iterator-of-pages and iterator-of-id-strings
            for page in list_response:
                # Defensive handling: page may be many shapes depending on SDK
                if isinstance(page, str):
                    all_ids.append(page)
                    continue

                if isinstance(page, dict):
                    ids = page.get("ids")
                    if isinstance(ids, (list, tuple)):
                        all_ids.extend([str(i) for i in ids])
                        continue
                    vectors = page.get("vectors")
                    if isinstance(vectors, dict):
                        all_ids.extend([str(i) for i in vectors.keys()])
                        continue

                # object-like pages (SDK classes)
                ids_attr = getattr(page, "ids", None)
                if isinstance(ids_attr, (list, tuple)):
                    all_ids.extend([str(i) for i in ids_attr])
                    continue

                vectors_attr = getattr(page, "vectors", None)
                if isinstance(vectors_attr, dict):
                    all_ids.extend([str(i) for i in vectors_attr.keys()])
                    continue
                if isinstance(vectors_attr, (list, tuple)):
                    all_ids.extend([str(i) for i in vectors_attr])
                    continue

                if isinstance(page, (list, tuple)):
                    all_ids.extend([str(i) for i in page])
                    continue

                # Final fallback: try to iterate the page
                try:
                    for item in page:  # type: ignore
                        all_ids.append(str(item))
                except Exception:
                    all_ids.append(str(page))

            logger.info("Found %d vector IDs in Pinecone", len(all_ids))

            if not all_ids:
                logger.warning("Pinecone list() returned 0 IDs")
                return False

            # ── Step 2: fetch metadata in batches ────────────────────────────
            products: list[dict] = []
            batch_size = self.FETCH_BATCH

            for batch_start in range(0, len(all_ids), batch_size):
                batch_ids = all_ids[batch_start: batch_start + batch_size]

                fetch_response: Any = self.index.fetch(ids=batch_ids)

                # fetch() returns an object with a .vectors dict {id: Vector}
                vectors_dict = {}
                if hasattr(fetch_response, "vectors"):
                    vectors_dict = fetch_response.vectors or {}
                elif isinstance(fetch_response, dict):
                    vectors_dict = fetch_response.get("vectors", {})

                for vid, vector_obj in vectors_dict.items():
                    meta = {}
                    if hasattr(vector_obj, "metadata"):
                        meta = getattr(vector_obj, "metadata", {}) or {}
                    elif isinstance(vector_obj, dict):
                        meta = vector_obj.get("metadata", {}) or {}
                    else:
                        # unknown vector object shape
                        continue

                    if meta:
                        products.append(_meta_to_product(meta))

                logger.info(
                    "Fetched batch %d–%d → %d products so far",
                    batch_start + 1,
                    min(batch_start + batch_size, len(all_ids)),
                    len(products),
                )

            if products:
                self.all_products    = products
                self.products_loaded = True
                logger.info("✅ Loaded ALL %d products from Pinecone", len(products))
                return True

            logger.warning("Pinecone fetch returned no metadata — keeping CSV data")
            return False

        except Exception as exc:
            logger.error("Pinecone list/fetch failed: %s", exc, exc_info=True)
            return False

    # ── 3. Ensure products are loaded (lazy, cached) ─────────────────────────
    def _ensure_products_loaded(self) -> None:
        """Load all products from Pinecone the first time they're needed."""
        if self.products_loaded:
            return
        if self.index:
            success = self._load_all_from_pinecone()
            if not success:
                logger.info("Pinecone load failed — using CSV data (%d items)", len(self.all_products))
        else:
            logger.info("No Pinecone index — using CSV data (%d items)", len(self.all_products))

    # ── 4. Semantic search via Pinecone query() — for specific queries ────────
    def _search_products(self, query: str, limit: int = 20) -> list:
        """
        For specific customer queries (e.g. 'smartphones under 20000'):
        use Pinecone's vector search to find the most relevant products.
        Falls back to keyword search over all_products when unavailable.
        """
        if not self.embedding_model or not self.index:
            return self._keyword_search(query, limit)

        try:
            vector = self.embedding_model.encode(query, convert_to_numpy=True).tolist()
            results: Any = self.index.query(vector=vector, top_k=limit, include_metadata=True)

            # Normalize matches from various SDK shapes
            matches = []
            if isinstance(results, dict):
                matches = results.get("matches", []) or []
            else:
                attr = getattr(results, "matches", None)
                if attr is None:
                    # sometimes the SDK returns a plain list
                    if isinstance(results, (list, tuple)):
                        matches = list(results)
                    else:
                        matches = []
                else:
                    matches = list(attr)

            products = []
            for match in matches:
                # match may be an object or a dict
                if hasattr(match, "metadata"):
                    meta = getattr(match, "metadata", {}) or {}
                elif isinstance(match, dict):
                    meta = match.get("metadata", {}) or {}
                else:
                    meta = {}

                # score may be attribute or dict key
                if hasattr(match, "score"):
                    try:
                        score = float(getattr(match, "score", 0) or 0)
                    except Exception:
                        score = 0.0
                elif isinstance(match, dict):
                    try:
                        score = float(match.get("score", 0) or 0)
                    except Exception:
                        score = 0.0
                else:
                    score = 0.0

                product = _meta_to_product(meta)
                product["_score"] = round(score, 3)
                products.append(product)

            logger.info("Pinecone query → %d results for: '%s'", len(products), query)
            return products

        except Exception as exc:
            logger.warning("Pinecone query failed (%s) — using keyword search", exc)
            return self._keyword_search(query, limit)

    def _keyword_search(self, query: str, limit: int = 20) -> list:
        """Simple keyword search over self.all_products."""
        stop = {
            "do", "you", "have", "any", "i", "want", "a", "an", "the", "for",
            "me", "us", "show", "find", "list", "get", "under", "below",
            "above", "less", "more", "than", "and", "or", "in", "what",
            "are", "is", "can", "price", "rs", "rupees",
        }
        keywords = [w for w in re.findall(r"\w+", query.lower())
                    if w not in stop and len(w) > 2]
        if not keywords:
            return self.all_products[:limit]

        scored = []
        for item in self.all_products:
            hay  = f"{item['name']} {item['main_category']} {item['sub_category']}".lower()
            hits = sum(1 for kw in keywords if kw in hay)
            if hits:
                scored.append((hits, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:limit]]

    # ── 5. Format context block for Gemini ───────────────────────────────────
    def _format_context(self, products: list) -> str:
        if not products:
            return ""

        lines = [
            "╔══════════════════════════════════════════════════════════╗",
            "║              MATCHED PRODUCTS FROM DATABASE              ║",
            "╚══════════════════════════════════════════════════════════╝",
            "Present EVERY product below with ALL details shown.\n",
        ]

        for i, p in enumerate(products, 1):
            disc_raw   = p.get("discount_price", "")
            actual_raw = p.get("actual_price", "")
            disc_str   = _clean_price(disc_raw)
            actual_str = _clean_price(actual_raw)
            savings    = _savings_line(disc_raw, actual_raw)
            cat        = p.get("main_category", "")
            sub        = p.get("sub_category", "")
            cat_str    = f"{cat} › {sub}" if sub and sub.lower() not in cat.lower() else cat
            link       = p.get("link", "") or "N/A"
            image      = p.get("image", "")

            if disc_str == "Price not listed":
                price_display = "Price not listed (check Amazon link)"
            elif actual_str not in ("Price not listed", disc_str):
                price_display = f"{disc_str}  (MRP: {actual_str}){savings}"
            else:
                price_display = disc_str

            lines += [
                f"┌─ Product {i} {'─'*50}",
                f"│  📦 Name        : {p.get('name', 'N/A')}",
                f"│  🏷️  Category    : {cat_str or 'N/A'}",
                f"│  💰 Price       : {price_display}",
                f"│  ⭐ Rating      : {p.get('ratings','N/A')} / 5  ({p.get('no_of_ratings','N/A')} reviews)",
                f"│  🔗 Buy here    : {link}",
            ]
            if image:
                lines.append(f"│  🖼️  Image       : {image}")
            lines.append(f"└{'─'*62}\n")

        return "\n".join(lines)

    # ── 6. Catalog paging ────────────────────────────────────────────────────
    def _is_catalog_request(self, text: str) -> bool:
        txt = text.strip().lower()
        return any(p in txt for p in [
            "catalog", "all products", "all product", "all the products",
            "product list", "show products", "show me products",
            "what products", "available products", "show me the catalog",
            "show all", "list all", "view all", "see all", "browse",
            "what do you have", "what do you sell", "what items",
            "what are your products", "show everything", "all items",
        ])

    def _is_more_catalog_request(self, sender: str, text: str) -> bool:
        txt = text.strip().lower()
        return sender in self.catalog_offsets and txt in {
            "more", "show more", "next", "next page", "more products",
            "continue", "keep going", "go on", "next batch", "load more",
        }

    def _is_order_tracking_intent(self, text: str) -> bool:
        """Detect if the user is asking about order status / tracking."""
        txt = text.lower().strip()
        order_intent_phrases = [
            "order status", "my order", "track order", "order i placed",
            "about the order", "about my order", "where is my order",
            "what happened to my order", "check order", "order update",
            "know about order", "know about the order", "status of my order",
            "status of order", "order tracking", "track my order",
            "check my order", "order i made", "previous order",
        ]
        return any(p in txt for p in order_intent_phrases)

    def _is_simple_product_query(self, text: str) -> bool:
        """Detect simple product searches that DON'T need Gemini (saves quota)."""
        txt = text.lower().strip()
        # Exclude order tracking intent
        if self._is_order_tracking_intent(txt):
            return False
        # Exclude catalog requests (need pagination)
        if self._is_catalog_request(txt):
            return False
        # Exclude order/complex queries
        exclude_phrases = ["place", "order", "cancel", "track", "how", "why", "what is", "tell me", "explain"]
        if any(p in txt for p in exclude_phrases):
            return False
        # Must be asking about products
        product_phrases = [
            "do you have", "show me", "find", "search for", "looking for",
            "what products", "available", "price", "cost", "budget"
        ]
        return any(p in txt for p in product_phrases)

    def _detect_order_type(self, text: str) -> str:
        """Detect order request type: 'place', or empty string. (Tracking and Cancellation are delegated to the AI native tools)."""
        txt = text.lower().strip()
        
        # If an order ID is present, it is definitely tracking or cancelling, delegate to AI
        import re as regex
        has_ord = bool(regex.search(r"ord-\d+", txt))
        if has_ord:
            return ""
            
        place_phrases = ["place", "buy", "purchase", "want to", "get me", "send me"]
        # If it contains tracking or AI switching keywords, don't treat as 'place'
        ignore_keywords = ["track", "status", "check", "where is", "happen", "talk to", "assistant", "chatbot", "human"]
        if any(p in txt for p in place_phrases) and not any(tk in txt for tk in ignore_keywords):
            return "place"
        
        # Detect structured order input: "product, quantity, address" format
        # even without explicit keywords
        import re as regex
        comma_count = text.count(",")
        has_number = bool(regex.search(r"\d+", text))
        has_unit_keyword = any(kw in txt for kw in ["unit", "piece", "qty", "quantity"])
        # Address keywords suggest delivery
        has_address_keyword = any(
            kw in txt for kw in 
            ["street", "block", "lahore", "karachi", "islamabad", "city", "address", 
             "avenue", "road", "lane", "plaza", "apartment", "apt", "flat", "house"]
        )
        
        # If it has 2+ commas, numbers, and looks like an address, treat as order
        if comma_count >= 2 and has_number and (has_unit_keyword or has_address_keyword):
            return "place"
        
        return ""

    def _parse_order_details(self, user_input: str) -> dict:
        """
        Parse order details from user input.
        Expected formats: 'product name, quantity, address'
        Returns dict with 'product_name', 'quantity', 'address', 'complete' keys.
        """
        result = {"product_name": "", "quantity": 0, "address": "", "complete": False}
        
        import re as regex
        
        # Try pattern 1: "product, quantity, address" (comma-separated)
        parts = [p.strip() for p in user_input.split(",")]
        if len(parts) >= 3:
            product = parts[0].strip()
            qty_str = parts[1].strip()
            address = ", ".join(parts[2:]).strip()
            
            # Extract quantity from "5 units", "1 piece", etc.
            qty_match = regex.search(r"\d+", qty_str)
            if qty_match and product and address:
                result["product_name"] = product
                result["quantity"] = int(qty_match.group(0))
                result["address"] = address
                result["complete"] = True
                return result
        
        # Try pattern 2: "quantity unit(s) of product to address"
        match = regex.search(r"(\d+)\s*(units?|pieces?|items?)?\s+of\s+(.+?)\s+(?:to|deliver|ship|send)\s+(.+)$", user_input, regex.IGNORECASE)
        if match:
            qty = int(match.group(1))
            product = match.group(3).strip()
            address = match.group(4).strip()
            if qty > 0 and product and address:
                result["product_name"] = product
                result["quantity"] = qty
                result["address"] = address
                result["complete"] = True
                return result
        
        return result

    def _handle_order_request(self, sender: str, order_type: str, user_input: str) -> str:
        """
        Handle order placement, cancellation, and tracking.
        For now, we collect order context from user input and provide guidance.
        """
        if order_type == "track":
            # Extract order ID from message if present
            import re as regex
            match = regex.search(r"ORD-\d{4,}", user_input)
            if match:
                order_id = match.group(0)
                return track_order(order_id)
            else:
                return "📦 To track your order, please provide the Order ID (e.g., ORD-1234).\nYou can find it in your order confirmation email."
        
        elif order_type == "cancel":
            # Extract order ID from message if present
            import re as regex
            match = regex.search(r"ORD-\d{4,}", user_input)
            if match:
                order_id = match.group(0)
                return cancel_order(order_id)
            else:
                return "❌ To cancel your order, please provide the Order ID (e.g., ORD-1234).\nYou can find it in your order confirmation email."
        
        elif order_type == "place":
            # Try to parse complete order details from user input
            order_details = self._parse_order_details(user_input)
            
            if order_details["complete"]:
                # All details provided — place the order immediately
                product_name = order_details["product_name"]
                quantity = order_details["quantity"]
                address = order_details["address"]
                
                try:
                    result = place_order(product_name, quantity, address)
                    logger.info(
                        "Order placed: Product=%s, Qty=%d, Address=%s | Result=%s",
                        product_name, quantity, address, result
                    )
                    return (
                        f"✅ *Order Placed Successfully!*\n\n"
                        f"{result}\n\n"
                        f"📍 *Delivery Address:* {address}\n"
                        f"📦 *Product:* {product_name}\n"
                        f"🔢 *Quantity:* {quantity}\n\n"
                        f"An order confirmation email has been sent to support.\n"
                        f"You can track your order using the Order ID above."
                    )
                except Exception as e:
                    logger.error("Order placement failed: %s", e)
                    return f"❌ Order placement failed: {str(e)}\nPlease try again or contact support."
            
            # Not all details provided — search for products and ask for details
            products = self._search_products(user_input, limit=5)
            if not products:
                return (
                    "🛍️ Let\'s get you set up! Here\'s what I need:\n\n"
                    "1. *Product name* — which item would you like?\n"
                    "2. *Quantity* — how many?\n"
                    "3. *Delivery address* — where should we ship it?\n\n"
                    "Example: *Smartphone, 2 units, 123 Main St, City 12345*"
                )
            else:
                # Show products and ask user to provide all details
                lines = ["🛍️ *Products Available for Order*\n"]
                for i, p in enumerate(products, 1):
                    name = p.get("name", "Unknown")
                    disc = _clean_price(p.get("discount_price", ""))
                    lines.append(f"*{i}. {name}*")
                    lines.append(f"   💰 {disc}\n")
                lines.append(
                    "*To place your order, reply with:*\n"
                    "**Product name, Quantity, Delivery address**\n\n"
                    "Example: *Smartphone, 1 unit, 123 Main St, City, ZIP*"
                )
                return "\n".join(lines).strip()
        
        return "I\'m here to help with your order. What would you like to do?"

    def _direct_product_response(self, user_input: str) -> str:
        """Return product search results from Pinecone WITHOUT calling Gemini (quota-free)."""
        try:
            products = self._search_products(user_input, limit=5)
            if not products:
                return f"No products found for '{user_input}'. Try: phones, earbuds, smartwatches, or mouse pads."
            
            lines = ["🛍️ *Products Found*\n"]
            for i, p in enumerate(products, 1):
                name = p.get("name", "Unknown")
                disc = _clean_price(p.get("discount_price", ""))
                cat = p.get("main_category", "")
                rating = p.get("ratings", "N/A")
                link = p.get("link", "")
                
                lines.append(f"*{i}. {name}*")
                lines.append(f"   💰 {disc}  |  ⭐ {rating}/5")
                lines.append(f"   📍 {cat}")
                if link:
                    lines.append(f"   🔗 {link}")
                lines.append("")
            
            lines.append("Would you like to order any of these?")
            return "\n".join(lines).strip()
        except Exception as e:
            logger.warning("Direct product search failed: %s", e)
            return "Search unavailable. Please try again."

    def _quota_fallback_response(self, user_input: str) -> str:
        """Graceful fallback when Gemini quota is exhausted."""
        txt_lower = user_input.strip().lower()
        greetings = ("hello", "hi", "hey", "salam", "assalam o alaikum", "good morning", "good evening")
        if txt_lower in greetings:
            return "Hi there! (System is currently very busy, so AI is temporarily unavailable, but I am still here to help with your orders!)"
        
        # Don't search products for order tracking requests
        if self._is_order_tracking_intent(user_input):
            return "Sure! Please share your *Order ID* (e.g. ORD-1234) and I'll check the status for you right away."
        
        # Don't search products for general conversational questions
        general_starters = [
            "what is", "who is", "where is", "when is", "why is", "how is",
            "what are", "who are", "how do", "how does", "how can",
            "tell me about", "explain", "define", "can you tell", "do you know",
            "thank you", "thanks", "okay", "ok", "great", "good", "nice",
            "bye", "goodbye", "see you", "take care",
        ]
        if any(p in txt_lower for p in general_starters):
            return "I'm here to help! Our AI is currently very busy, but feel free to ask me about products or your order status. 😊"
            
        search_reply = self._direct_product_response(user_input)
        return search_reply

    def _build_catalog_page(self, sender: str, reset: bool) -> str:
        """Page through self.all_products — fully loaded from Pinecone or CSV."""
        products = self.all_products
        if not products:
            return "Catalog is currently unavailable. Please try again."

        total = len(products)
        start = 0 if reset else self.catalog_offsets.get(sender, 0)

        if start >= total:
            self.catalog_offsets.pop(sender, None)
            return "You have reached the end of the catalog. Reply *catalog* to start again."

        end        = min(start + self.catalog_page_size, total)
        page_items = products[start:end]

        lines = [
            "📦 *Electronics Catalog*",
            f"Showing *{start + 1}–{end}* of *{total}* products\n",
            "─" * 50,
        ]

        for idx, item in enumerate(page_items, start + 1):
            disc_raw   = item.get("discount_price", "")
            actual_raw = item.get("actual_price", "")
            disc_str   = _clean_price(disc_raw)
            actual_str = _clean_price(actual_raw)
            savings    = _savings_line(disc_raw, actual_raw)
            cat        = item.get("main_category", "")
            sub        = item.get("sub_category", "")
            cat_str    = f"{cat} › {sub}" if sub and sub.lower() not in cat.lower() else cat

            if disc_str == "Price not listed":
                price_str = "Price not listed — check link"
            elif actual_str not in ("Price not listed", disc_str):
                price_str = f"{disc_str}  (MRP: {actual_str}){savings}"
            else:
                price_str = disc_str

            lines += [
                f"*{idx}. {item.get('name', 'N/A')}*",
                f"   🏷️  Category  : {cat_str or 'N/A'}",
                f"   💰 Price     : {price_str}",
                f"   ⭐ Rating    : {item.get('ratings','N/A')} / 5  ({item.get('no_of_ratings','N/A')} reviews)",
                f"   🔗 Buy here  : {item.get('link','N/A') or 'N/A'}",
            ]
            if item.get("image"):
                lines.append(f"   🖼️  Image     : {item['image']}")
            lines.append("─" * 50)

        lines.append(f"\nShowing {start + 1}–{end} of {total} products.")
        if end < total:
            self.catalog_offsets[sender] = end
            lines.append(f"Reply *more* to see the next {self.catalog_page_size} products.")
        else:
            self.catalog_offsets.pop(sender, None)
            lines.append("✅ You've seen all products! Reply *catalog* to start again.")

        return "\n".join(lines).strip()

    # ── 7. Gemini init ───────────────────────────────────────────────────────
    def _initialize(self) -> None:
        if genai is None:
            self.error = "google-generativeai not installed."
            return
        if not GEMINI_API_KEY:
            self.error = "GEMINI_API_KEY missing."
            return
        try:
            cfg = getattr(genai, "configure", None)
            if callable(cfg):
                cfg(api_key=GEMINI_API_KEY)

            if Pinecone and PINECONE_API_KEY:
                try:
                    self.pc = Pinecone(api_key=PINECONE_API_KEY)
                    indexes = [i.name for i in self.pc.list_indexes()]
                    if PINECONE_INDEX_NAME in indexes:
                        self.index = self.pc.Index(name=PINECONE_INDEX_NAME)
                        if SentenceTransformer:
                            self.embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
                        logger.info("✅ Pinecone connected")
                    else:
                        logger.warning("⚠️ Pinecone index '%s' not found", PINECONE_INDEX_NAME)
                except Exception as exc:
                    logger.warning("⚠️ Pinecone init failed: %s", exc)

            self.ready = True
            logger.info("✅ GeminiChatModel ready")
        except Exception as exc:
            self.error = str(exc)
            logger.error("❌ Init failed: %s", exc)

    # ── 8. Session management ────────────────────────────────────────────────
    def _get_or_create_session(self, sender: str):
        if sender in self.sessions:
            return self.sessions[sender]
        if genai is None:
            return None

        system_instruction = """
You are Zara, a helpful electronics shopping assistant for AutoServe.

━━━ RETURNING CUSTOMER BEHAVIOR ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
When a CUSTOMER CONTEXT block is included in the prompt:
1. Greet the returning customer WARMLY and by name if their name is known.
2. Mention their most recent order (product name, order ID, status).
3. If status is "Processing"  → tell them it is being prepared.
   If status is "Dispatched"  → tell them it is on its way.
   If status is "Delivered"   → congratulate them and ask how they like it.
4. Proactively RECOMMEND a related or complementary product from the catalog.
5. If the customer is NEW (no prior order) — introduce yourself and ask how you can help.

━━━ ORDER STATUS LOOKUP ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
When the customer asks about an order (e.g. "I want to know about this order ORD-5821", "what happened to my order", "where is my package", "what is my order status"):
1. If the ORDER ID is provided in their message (e.g. ORD-5821) → you MUST use the `track_order` tool.
   This tool will fetch the order data from the order table in the database.
2. If NO order ID is given → ask the customer to share their Order ID.
3. Reply to the user about the status of their order according to the `status` column returned from the order table. If it says 'Processing', tell them it is being prepared. If 'Dispatched', it is on the way.

━━━ PRODUCT LISTING RULES ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
When a PRODUCT DATABASE is included in the prompt:
1. List EVERY single product — never skip, summarise, or say "and more".
2. For each product show ALL of these fields as a numbered card:
   • Full product name
   • Discounted price + original MRP + savings % (if available)
   • If price is "Price not listed" — tell customer to check the link
   • Category › Sub-category
   • Star rating + number of customer reviews
   • Full purchase link
3. After listing all products, ask if the customer wants to order any.
4. NEVER invent or guess any product details.

━━━ ORDERS ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Collect product name, quantity, and delivery address before calling place_order.
Use cancel_order / track_order as needed.

━━━ RECOMMENDATIONS ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
After helping a customer, always suggest 1–2 related products they might like
based on what they previously ordered or what they are asking about.

━━━ GENERAL ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Be warm, friendly and concise.
2. For "out of the box" or off-topic questions (unrelated to shopping or electronics):
   - Answer the question politely using your general knowledge.
   - Maintain your persona as Zara from AutoServe.
   - Example: "That's an interesting question! While I'm usually busy helping with electronics here at AutoServe, I can tell you that [Answer]. Is there anything else you'd like to know, or perhaps a gadget I can help you find?"
3. If no products are found for a search, say so politely and ask the customer to rephrase.
""".strip()

        ModelClass = getattr(genai, "GenerativeModel", None) or getattr(genai, "ChatModel", None)
        if ModelClass is None:
            return None

        try:
            model = ModelClass(
                model_name=GEMINI_MODEL_NAME,
                system_instruction=system_instruction,
                tools=[place_order, cancel_order, track_order],
            )
        except TypeError:
            try:
                model = ModelClass(name=GEMINI_MODEL_NAME, system_instruction=system_instruction)
            except TypeError:
                model = ModelClass(GEMINI_MODEL_NAME)

        try:
            self.sessions[sender] = model.start_chat(enable_automatic_function_calling=True)
        except TypeError:
            self.sessions[sender] = model.start_chat()

        return self.sessions[sender]

    # ── 9. Main generate ─────────────────────────────────────────────────────
    def generate(self, sender: str, user_input: str, context_text: str = "") -> str:

        try:
            # ── ORDER TRACKING INTENT (highest priority) ──────────────────────────
            # If user asks about order status, skip ALL product logic and go to AI
            if self._is_order_tracking_intent(user_input):
                import re as regex
                has_ord = bool(regex.search(r"ORD-\d+", user_input.upper()))
                if has_ord:
                    # Has order ID — let AI handle with track_order tool
                    pass  # Fall through to AI section below
                else:
                    # No order ID — ask for it immediately
                    return "Sure! Please share your *Order ID* (e.g. ORD-1234) and I'll check the status for you right away. 📦"

            # ── Catalog / show-all request ────────────────────────────────────────
            if not self._is_order_tracking_intent(user_input):
                if self._is_catalog_request(user_input):
                    # Load ALL products from Pinecone the first time (lazy + cached)
                    self._ensure_products_loaded()
                    return self._build_catalog_page(sender, reset=True)

                if self._is_more_catalog_request(sender, user_input):
                    return self._build_catalog_page(sender, reset=False)

            # ── ORDER HANDLING (place/cancel/track) ────────────────────────────────
            order_type = self._detect_order_type(user_input)
            if order_type:
                return self._handle_order_request(sender, order_type, user_input)

            # ── QUOTA SAVER: Simple product queries (Pinecone only, no Gemini) ────
            if self._is_simple_product_query(user_input):
                return self._direct_product_response(user_input)

            # ── Model readiness check ─────────────────────────────────────────────
            if not self.ready:
                load_dotenv(PROJECT_ROOT / ".env", override=True)
                load_dotenv(override=True)
                global GEMINI_API_KEY
                GEMINI_API_KEY = _get_env_value("GEMINI_API_KEY", "GOOGLE_API_KEY", "API_KEY")
                self._initialize()

            if not self.ready:
                return f"Model not ready: {self.error}"
            if genai is None:
                return "Gemini API not available."

            # ── Specific product search (semantic via Pinecone) ───────────────
            txt_lower = user_input.strip().lower()
            greetings = ("hello", "hi", "hey", "salam", "assalam o alaikum", "good morning", "good evening")
            
            # Detect if user is asking about order tracking / status
            order_intent_phrases = [
                "order status", "my order", "track order", "order i placed",
                "about the order", "about my order", "where is my order",
                "what happened to my order", "check order", "order update",
                "know about order", "know about the order", "status of my order",
                "status of order", "order tracking", "track my order"
            ]
            is_order_intent = any(p in txt_lower for p in order_intent_phrases)
            
            # Detect general/conversational questions that are NOT about products
            general_question_starters = [
                "what is", "who is", "where is", "when is", "why is", "how is",
                "what are", "who are", "where are", "when are", "why are", "how are",
                "what was", "who was", "how do", "how does", "how can", "how much is",
                "tell me about", "explain", "define", "meaning of",
                "can you tell", "do you know", "what do you think",
                "thank you", "thanks", "okay", "ok", "great", "good", "nice",
                "bye", "goodbye", "see you", "take care",
            ]
            is_general_question = any(txt_lower.startswith(p) or p in txt_lower for p in general_question_starters)
            # Don't mark as general if it's clearly about products
            product_signals = ["show me", "find", "search", "looking for", "price", "buy", "purchase", "product"]
            if any(ps in txt_lower for ps in product_signals):
                is_general_question = False
            
            products = []
            if txt_lower not in greetings and not is_order_intent and not is_general_question:
                products = self._search_products(user_input, limit=20)
                
            context = self._format_context(products)

            if is_order_intent:
                # Pure order tracking: skip products entirely, let AI use track_order tool
                prompt = (
                    f"Customer Context:\n{context_text}\n\n"
                    f"Customer question: {user_input}\n\n"
                    "The customer is asking about an order. If they provided an Order ID (like ORD-1234), "
                    "use the track_order tool to fetch the status. If they did NOT provide an Order ID, "
                    "politely ask them to share it so you can look it up."
                )
            elif is_general_question:
                # General conversation: let AI answer naturally without product context
                prompt = (
                    f"Customer Context:\n{context_text}\n\n"
                    f"Customer question: {user_input}\n\n"
                    "Answer this question naturally and helpfully using your general knowledge. "
                    "Stay in character as Zara from AutoServe. Be friendly and concise. "
                    "After answering, you may gently ask if they need help with any electronics or orders."
                )
            elif context:
                prompt = (
                    f"{context}\n\n"
                    f"Customer Context:\n{context_text}\n\n"
                    f"Customer question: {user_input}\n\n"
                    "List ALL products above as numbered cards only when the question is about products. Each card must include: "
                    "name, price (discounted + MRP + savings, or 'Price not listed'), "
                    "category, rating with review count, and the full purchase link."
                )
            else:
                prompt = f"Customer Context:\n{context_text}\n\nCustomer question: {user_input}" if context_text else user_input

            session = self._get_or_create_session(sender)
            if session is None:
                return "Session unavailable right now."

            try:
                response = session.send_message(prompt)
            except Exception as send_err:
                err_str = str(send_err)
                if _is_quota_error_text(err_str):
                    return self._quota_fallback_response(user_input)
                logger.warning("Session send failed, recreating: %s", send_err)
                self.sessions.pop(sender, None)
                session  = self._get_or_create_session(sender)
                if session is None:
                    return "Session unavailable right now."
                try:
                    response = session.send_message(prompt)
                except Exception as retry_err:
                    retry_text = str(retry_err)
                    if _is_quota_error_text(retry_text):
                        return self._quota_fallback_response(user_input)
                    raise

            reply = getattr(response, "text", None)
            if not reply and hasattr(response, "candidates"):
                try:
                    reply = response.candidates[0].content.parts[0].text
                except Exception:
                    reply = None

            if reply:
                return reply.strip()

            # Last-resort non-stateful fallback
            try:
                MC = getattr(genai, "GenerativeModel", None) or getattr(genai, "ChatModel", None)
                if MC:
                    try:
                        m = MC(model_name=GEMINI_MODEL_NAME)
                    except TypeError:
                        m = MC(GEMINI_MODEL_NAME)
                    fb  = m.generate_content(prompt)
                    txt = getattr(fb, "text", "")
                    if txt:
                        return txt.strip()
            except Exception as fb_err:
                if _is_quota_error_text(str(fb_err)):
                    return self._quota_fallback_response(user_input)
                logger.warning("Fallback failed: %s", fb_err)

            return "I'm here to help! What electronics are you looking for?"

        except Exception as exc:
            logger.error("Generation error: %s", exc, exc_info=True)
            err = str(exc)
            if "API Key not found" in err or "API_KEY_INVALID" in err:
                self.ready = False
                self.error = "Invalid Gemini API key."
                return "API key error — please update GEMINI_API_KEY in .env and restart."
            if _is_quota_error_text(err):
                return self._quota_fallback_response(user_input)
            return "Something went wrong. Please try again."
        finally:
            CURRENT_SENDER_NUMBER = ""


# ---------------------------------------------------------------------------
chat_model = GeminiChatModel()


def initialize_model() -> bool:
    if chat_model.ready:
        logger.info("✅ Chat model initialized successfully")
        return True
    logger.warning("⚠️ Chat model failed: %s", chat_model.error)
    return False


def get_chat_response(sender_number: str, msg: str, context_text: str = "") -> str:
    return chat_model.generate(sender_number, msg, context_text=context_text)


if __name__ == "__main__":
    if initialize_model():
        test_sender = "123456789"
        for q in [
            "show all products",
            "Do you have any smartphones under 20000?",
            "Show me mouse pads",
        ]:
            print(f"\nUser : {q}")
            print(f"Zara : {get_chat_response(test_sender, q)}")