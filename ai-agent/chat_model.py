import csv
import logging
import pickle
import re
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PRODUCT_DATA_PATH = Path(__file__).resolve().parent / "product_data.pkl"
SIMILARITY_PATH = Path(__file__).resolve().parent / "similarity_matrix.pkl"
CSV_FALLBACK_PATH = Path(__file__).resolve().parent.parent / "electronics_product.csv"

class ChatModel:
    def __init__(self, product_data_path: Path = PRODUCT_DATA_PATH, similarity_path: Path = SIMILARITY_PATH):
        self.product_data_path = product_data_path
        self.similarity_path = similarity_path
        self.products: list[dict[str, Any]] = []
        self.similarity_matrix: Any = None
        self.assets_loaded = False
        self.load_assets()

    def load_assets(self) -> bool:
        """Load product and similarity artifacts from pickle files."""
        try:
            raw_products = self._load_pickle(self.product_data_path)
            raw_similarity = self._load_pickle(self.similarity_path)

            self.products = self._normalize_products(raw_products)
            self.similarity_matrix = raw_similarity

            if not self.products and CSV_FALLBACK_PATH.exists():
                logger.warning("Pickle product data was empty/invalid. Using CSV fallback.")
                self.products = self._load_products_from_csv(CSV_FALLBACK_PATH)

            self.assets_loaded = bool(self.products)
            logger.info(
                "Assets ready: products=%s, similarity=%s",
                len(self.products),
                type(self.similarity_matrix).__name__ if self.similarity_matrix is not None else "None",
            )
            return self.assets_loaded
        except Exception as e:
            logger.error(f"Error loading assets: {e}")
            self.assets_loaded = False
            return False

    def _load_pickle(self, path: Path) -> Any:
        if not path.exists():
            logger.warning("Pickle file missing: %s", path)
            return None
        with path.open("rb") as f:
            return pickle.load(f)

    def _safe_text(self, value: Any) -> str:
        """Return ASCII-safe text for terminals/environments with limited encoding."""
        text = str(value or "")
        text = text.replace("\u20b9", "Rs ")
        return text.encode("ascii", "ignore").decode("ascii")

    def _normalize_products(self, obj: Any) -> list[dict[str, Any]]:
        """Normalize supported product-data formats into list-of-dicts."""
        if obj is None:
            return []

        if hasattr(obj, "to_dict"):
            try:
                return obj.to_dict(orient="records")
            except TypeError:
                pass

        if isinstance(obj, list):
            return [item for item in obj if isinstance(item, dict)]

        if isinstance(obj, dict):
            if "products" in obj and isinstance(obj["products"], list):
                return [item for item in obj["products"] if isinstance(item, dict)]
            return []

        return []

    def _load_products_from_csv(self, csv_path: Path) -> list[dict[str, Any]]:
        products: list[dict[str, Any]] = []
        with csv_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                products.append(row)
        return products

    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r"[a-z0-9]+", (text or "").lower())

    def _product_text(self, product: dict[str, Any]) -> str:
        name = str(product.get("name", ""))
        main_category = str(product.get("main_category", ""))
        sub_category = str(product.get("sub_category", ""))
        return f"{name} {main_category} {sub_category}".lower()

    def _match_products(self, user_input: str) -> list[int]:
        tokens = self._tokenize(user_input)
        if not tokens:
            return []

        scored: list[tuple[int, int]] = []
        for idx, product in enumerate(self.products):
            product_blob = self._product_text(product)
            score = sum(1 for token in tokens if token in product_blob)
            if score > 0:
                scored.append((score, idx))

        scored.sort(reverse=True)
        return [idx for _, idx in scored[:5]]

    def _similar_indices(self, anchor_idx: int, limit: int = 3) -> list[int]:
        """Return nearest indices from similarity matrix if it looks valid."""
        matrix = self.similarity_matrix
        if matrix is None:
            return []

        try:
            row = matrix[anchor_idx]
            indexed = [(float(score), i) for i, score in enumerate(row) if i != anchor_idx]
            indexed.sort(reverse=True)
            return [i for _, i in indexed[:limit]]
        except Exception:
            return []

    def _format_reply(self, indices: list[int]) -> str:
        lines = ["Here are some products you may like:"]
        for i, idx in enumerate(indices, start=1):
            if idx < 0 or idx >= len(self.products):
                continue
            product = self.products[idx]
            name = self._safe_text(product.get("name", "Unknown Product"))
            price = self._safe_text(product.get("discount_price", "N/A"))
            category = self._safe_text(product.get("sub_category", "Electronics"))
            lines.append(f"{i}. {name} | Price: {price} | Category: {category}")

        if len(lines) == 1:
            return "I could not find matching products right now. Please try another keyword."
        return "\n".join(lines)

    def generate_response(self, user_input: str) -> str:
        """Generate a recommendation reply using pickle-loaded artifacts."""
        try:
            if not self.assets_loaded:
                return "Recommendation model is not ready. Please load valid product .pkl files."

            matches = self._match_products(user_input)
            if not matches:
                return "I could not find a match. Try keywords like phone, earbuds, charger, or smartwatch."

            anchor = matches[0]
            similar = self._similar_indices(anchor, limit=3)
            candidate_indices = [anchor] + [idx for idx in similar if idx not in matches[:1]]

            if len(candidate_indices) < 3:
                for idx in matches[1:]:
                    if idx not in candidate_indices:
                        candidate_indices.append(idx)
                    if len(candidate_indices) >= 3:
                        break

            return self._format_reply(candidate_indices[:3])
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "Sorry, I hit an error while generating recommendations."



# Initialize the model globally
chat_model = None

def initialize_model():
    """Initialize pickle-backed recommendation model on startup."""
    global chat_model
    try:
        chat_model = ChatModel()
        logger.info("Chat model initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize chat model: {e}")
        return False

def get_chat_response(user_message):
    """
    Get a response from the chat model.
    Call this from your webhook handler.
    """
    global chat_model
    
    if chat_model is None:
        logger.warning("Chat model not initialized, initializing now...")
        initialize_model()
    
    if chat_model is None:
        return "I'm sorry, I'm not available right now. Please try again later."
    
    return chat_model.generate_response(user_message)


if __name__ == "__main__":
    # Test the model
    if initialize_model():
        test_message = "Hello, how are you?"
        response = get_chat_response(test_message)
        print(f"User: {test_message}")
        print(f"Bot: {response}")
