import json
import logging
import os
import re
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, TypedDict, cast

import requests

# Disable SSL warnings for corporate proxy with self-signed certificates
try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None

try:
    from pinecone import Pinecone
except ImportError:  # pragma: no cover
    Pinecone = None

try:
    from sentence_transformers import SentenceTransformer
except ImportError:  # pragma: no cover
    SentenceTransformer = None


logger = logging.getLogger(__name__)

PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "autoserve")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")

_embedding_model = None
_pinecone_index = None


class PineconeVector(TypedDict):
    id: str
    values: list[float]
    metadata: dict[str, Any]


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd is not None and pd.isna(value):
            return ""
    except Exception:
        pass
    text = str(value).strip()
    return "" if text.lower() in {"", "nan", "none", "null"} else text


def _get_embedding_model():
    global _embedding_model
    if _embedding_model is not None:
        return _embedding_model
    if SentenceTransformer is None:
        raise RuntimeError("sentence-transformers is not installed")
    _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _embedding_model


def _get_pinecone_index():
    global _pinecone_index
    if _pinecone_index is not None:
        return _pinecone_index

    api_key = (os.getenv("PINECONE_API_KEY") or os.getenv("PINECONE_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("PINECONE_API_KEY or PINECONE_KEY is missing")
    if Pinecone is None:
        raise RuntimeError("pinecone is not installed")

    try:
        # Try standard initialization first
        pc = Pinecone(api_key=api_key)
    except Exception as e:
        logger.warning(f"Standard Pinecone initialization failed: {str(e)}")
        # If standard initialization fails due to SSL, try with httpx client configuration
        try:
            import httpx
            # Create a custom http client that doesn't verify SSL
            http_client = httpx.Client(verify=False)
            pc = Pinecone(api_key=api_key, http_client=http_client)
        except Exception as e2:
            logger.warning(f"Pinecone initialization with custom HTTP client also failed: {str(e2)}")
            # Last resort: try without any special configuration
            pc = Pinecone(api_key=api_key)
    
    _pinecone_index = pc.Index(name=PINECONE_INDEX_NAME)
    return _pinecone_index


def _row_to_text(row: dict[str, Any]) -> str:
    preferred_order = [
        "name",
        "title",
        "product",
        "product_name",
        "description",
        "main_category",
        "sub_category",
        "category",
        "discount_price",
        "actual_price",
        "ratings",
        "no_of_ratings",
        "link",
        "url",
    ]
    parts: list[str] = []
    seen_keys: set[str] = set()

    for key in preferred_order:
        value = _clean_text(row.get(key))
        if value:
            parts.append(f"{key}: {value}")
            seen_keys.add(key.lower())

    for key, value in row.items():
        clean_key = str(key).strip()
        clean_value = _clean_text(value)
        if clean_key and clean_value and clean_key.lower() not in seen_keys:
            parts.append(f"{clean_key}: {clean_value}")
            seen_keys.add(clean_key.lower())

    return " | ".join(parts)


def _row_to_metadata(row: dict[str, Any], source_name: str, row_index: int, source_type: str) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "source_name": source_name,
        "source_type": source_type,
        "row_index": row_index,
    }

    aliases = {
        "name": ["name", "title", "product", "product_name"],
        "main_category": ["main_category", "category", "cat"],
        "sub_category": ["sub_category", "subcategory", "subcat"],
        "image": ["image", "image_url", "img", "thumbnail"],
        "link": ["link", "url", "product_url", "website"],
        "ratings": ["ratings", "rating", "stars"],
        "no_of_ratings": ["no_of_ratings", "reviews", "review_count"],
        "discount_price": ["discount_price", "sale_price", "price", "discounted_price"],
        "actual_price": ["actual_price", "mrp", "original_price", "list_price"],
    }

    lowered = {str(k).lower(): v for k, v in row.items()}
    for target, keys in aliases.items():
        for key in keys:
            value = _clean_text(lowered.get(key))
            if value:
                metadata[target] = value
                break

    for key, value in row.items():
        key_text = _clean_text(key)
        value_text = _clean_text(value)
        if key_text and value_text and key_text not in metadata:
            metadata[key_text] = value_text

    return metadata


def _extract_rows_from_file(file_path: Path) -> tuple[list[dict[str, Any]], str]:
    suffix = file_path.suffix.lower()
    if pd is None:
        raise RuntimeError("pandas is not installed")

    if suffix == ".csv":
        logger.info(f"Reading CSV file: {file_path}")
        try:
            df = pd.read_csv(file_path)
        except Exception as e:
            logger.warning(f"Primary CSV read failed for {file_path}: {e}. Retrying with permissive parser.")
            try:
                # use python engine and skip bad lines (pandas >=1.3)
                df = pd.read_csv(file_path, engine="python", on_bad_lines="skip", dtype=str)
            except Exception as e2:
                logger.warning(f"Permissive pandas CSV read failed for {file_path}: {e2}. Falling back to csv module.")
                try:
                    import csv
                    from io import StringIO

                    text = file_path.read_text(encoding="utf-8", errors="replace")
                    sniffer = csv.Sniffer()
                    try:
                        dialect = sniffer.sniff(text[:8192])
                        delim = dialect.delimiter
                    except Exception:
                        delim = ','

                    reader = csv.DictReader(StringIO(text), delimiter=delim)
                    records = []
                    for row in reader:
                        records.append({str(k): (v if v is not None else "") for k, v in row.items()})
                    logger.info(f"CSV fallback parser succeeded for {file_path}: {len(records)} rows")
                    return records, "csv"
                except Exception as e3:
                    logger.error(f"CSV fallback parser failed for {file_path}: {e3}")
                    raise

        records = [{str(key): value for key, value in row.items()} for row in df.fillna("").to_dict(orient="records")]
        logger.info(f"CSV parsed successfully for {file_path}: {len(records)} rows")
        return records, "csv"

    if suffix in {".xlsx", ".xls"}:
        logger.info(f"Reading Excel file: {file_path}")
        df = pd.read_excel(file_path)
        records = [{str(key): value for key, value in row.items()} for row in df.fillna("").to_dict(orient="records")]
        logger.info(f"Excel parsed successfully for {file_path}: {len(records)} rows")
        return records, "excel"

    if suffix == ".json":
        logger.info(f"Reading JSON file: {file_path}")
        raw = json.loads(file_path.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            records = [item for item in raw if isinstance(item, dict)]
            logger.info(f"JSON parsed successfully for {file_path}: {len(records)} rows")
            return records, "json"
        if isinstance(raw, dict):
            for key in ("records", "data", "items", "products"):
                candidate = raw.get(key)
                if isinstance(candidate, list):
                    records = [item for item in candidate if isinstance(item, dict)]
                    logger.info(f"JSON parsed successfully for {file_path}: {len(records)} rows")
                    return records, "json"
            logger.info(f"JSON parsed successfully for {file_path}: 1 row")
            return [raw], "json"

    raise RuntimeError("Unsupported file type. Use CSV, XLSX, XLS, or JSON.")


class _HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.parts.append(text)

    def get_text(self) -> str:
        return " ".join(self.parts)


def _extract_url_text(page_url: str) -> tuple[str, str]:
    response = requests.get(page_url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    content_type = (response.headers.get("content-type") or "").lower()

    if "text/html" in content_type or "application/xhtml+xml" in content_type or not content_type:
        parser = _HTMLTextExtractor()
        parser.feed(response.text)
        return parser.get_text(), content_type or "text/html"

    return response.text, content_type


def _upsert_rows(rows: list[dict[str, Any]], source_name: str, source_type: str) -> int:
    if not rows:
        return 0

    try:
        logger.info(f"Starting embedding pipeline for {source_name}: {len(rows)} rows from {source_type}")
        index = _get_pinecone_index()
        model = _get_embedding_model()
        vector_batch: list[PineconeVector] = []
        texts: list[str] = []
        payloads: list[tuple[int, dict[str, Any], str]] = []

        for row_index, row in enumerate(rows):
            row_dict = dict(row)
            text = _row_to_text(row_dict)
            if not text:
                continue
            texts.append(text)
            payloads.append((row_index, row_dict, text))

        if not texts:
            logger.warning(f"No embeddable text found for {source_name}")
            return 0

        embeddings = model.encode(texts, convert_to_numpy=True).tolist()
        logger.info(f"Generated {len(embeddings)} embeddings for {source_name}")

        for (row_index, row_dict, text), values in zip(payloads, embeddings):
            metadata = _row_to_metadata(row_dict, source_name, row_index, source_type)
            metadata["text"] = text[:2000]
            vector_id = f"{Path(source_name).stem}-{row_index}-{int(datetime.utcnow().timestamp())}"
            vector_batch.append({"id": vector_id, "values": [float(v) for v in values], "metadata": metadata})

        if vector_batch:
            try:
                index.upsert(vectors=cast(Any, vector_batch))
                logger.info(f"Upserted {len(vector_batch)} vectors to Pinecone for {source_name}")
            except Exception as e:
                logger.warning(f"Pinecone upsert failed for {source_name}: {str(e)}. Vectors prepared but not stored.")
                return 0

        return len(vector_batch)
    except Exception as e:
        logger.warning(f"Vector processing failed for {source_name}: {str(e)}. File saved but vectors not processed.")
        return 0


def process_uploaded_file(file_path: str | Path, source_name: str | None = None) -> dict[str, Any]:
    path = Path(file_path)
    source_name = source_name or path.name
    rows, source_type = _extract_rows_from_file(path)
    vectors_upserted = _upsert_rows(rows, source_name, source_type)
    return {
        "success": True,
        "source_name": source_name,
        "source_type": source_type,
        "rows_processed": len(rows),
        "vectors_upserted": vectors_upserted,
    }


def process_uploaded_url(url: str, domain: str | None = None) -> dict[str, Any]:
    page_text, content_type = _extract_url_text(url)
    source_name = domain or url
    row = {
        "name": source_name,
        "main_category": "url",
        "sub_category": "webpage",
        "link": url,
        "url": url,
        "domain": source_name,
        "content_type": content_type,
        "description": page_text[:5000],
    }
    vectors_upserted = _upsert_rows([row], source_name, "url")
    return {
        "success": True,
        "source_name": source_name,
        "rows_processed": 1,
        "vectors_upserted": vectors_upserted,
    }
