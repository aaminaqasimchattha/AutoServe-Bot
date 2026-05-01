# File Upload Integration Guide

## ✅ What's Been Implemented

Your FYP system now supports dynamic data uploading through the frontend dashboard. Users can upload CSV, Excel, or JSON files, which are automatically converted to embeddings and integrated into the chatbot's knowledge base.

### Key Features:
- **Multiple Format Support**: CSV, Excel (.xlsx, .xls), JSON
- **Real-time Processing**: Files are processed immediately after upload
- **Embedding Generation**: Automatic conversion to vector embeddings using SentenceTransformer
- **Pinecone Integration**: Embeddings stored alongside original database
- **Smart Chatbot Responses**: Zara chatbot uses both original and uploaded data

---

## 📁 Files Modified/Created

### Backend Files:

1. **`ai-agent/file_processor.py`** (NEW)
   - Handles file parsing for CSV, Excel, JSON formats
   - Converts data rows to embeddings
   - Uploads to Pinecone with metadata
   - Batch processing for efficiency

2. **`app.py`** (UPDATED)
   - Added `/api/upload` POST endpoint
   - File validation and temporary file handling
   - Integration with Pinecone and embedding model
   - Error handling and response formatting

3. **`ai-agent/chat_model.py`** (UPDATED)
   - System prompt updated to acknowledge user-uploaded data
   - Chatbot searches both original and uploaded data automatically
   - No functional changes needed - search already works with Pinecone

### Frontend Files:

1. **`frontend/dashboard/file-upload.tsx`** (UPDATED)
   - Added backend API integration
   - Real-time upload status tracking
   - Error message display
   - Progress bar with simulated progress

2. **`frontend/.env.local`** (NEW)
   - Environment configuration for API URL
   - Set `NEXT_PUBLIC_API_URL` to your backend server

### Configuration:

1. **`requirements.txt`** (UPDATED)
   - Added: `pandas`, `openpyxl`, `pillow`
   - These are required for file processing

---

## 🚀 Setup Instructions

### 1. Install Dependencies

If you haven't already installed the new packages:

```bash
pip install pandas openpyxl pillow
```

Or install all requirements:
```bash
pip install -r requirements.txt
```

### 2. Configure Frontend API URL

**File**: `frontend/.env.local`

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Update this if your backend runs on a different host/port.

### 3. Start Backend

```bash
# Terminal 1: Start FastAPI server
cd /path/to/FYP
uvicorn app:app --reload --port 8000
```

### 4. Start Frontend

```bash
# Terminal 2: Start Next.js dev server
cd frontend
npm run dev
# or
pnpm dev
```

The frontend will be available at `http://localhost:3000`

---

## 💾 How It Works

### Upload Flow:

```
User selects file (CSV/Excel/JSON)
        ↓
Frontend shows upload UI with progress
        ↓
File sent to backend: POST /api/upload
        ↓
Backend validates file format
        ↓
File parsed into rows
        ↓
Each row converted to embedding
        ↓
Embeddings stored in Pinecone with metadata
        ↓
Frontend shows "✅ Complete"
```

### Data Structure:

When a file is uploaded, each row becomes:

```json
{
  "id": "filename_0",
  "values": [0.23, 0.45, 0.12, ...],  // 384-dim embedding
  "metadata": {
    "column1": "value1",
    "column2": "value2",
    ...all_columns,
    "_source_file": "your_filename"
  }
}
```

### Chat Integration:

When users chat with Zara:
1. Query is converted to embedding
2. Pinecone searches for top-3 matching products
3. Includes both original database AND uploaded data
4. Zara responds with relevant products and prices

---

## 📋 Supported File Formats

### CSV Files
```csv
name,category,price,rating
Laptop,Electronics,50000,4.5
Phone,Electronics,30000,4.2
```

### Excel Files (.xlsx, .xls)
Same structure as CSV - first row is column headers

### JSON Files
```json
[
  {"name": "Laptop", "category": "Electronics", "price": 50000},
  {"name": "Phone", "category": "Electronics", "price": 30000}
]
```

---

## 🔍 Example Usage

### Upload Scenario:

1. **User clicks "Select Files"** on dashboard
2. **Selects** `products.csv` with 1000 products
3. **Frontend shows progress**: 0% → 100%
4. **Status changes**: Processing → ✅ Complete
5. **Chatbot automatically uses** the new data

### Chat Scenario:

User: "Do you have any laptops?"

Zara searches Pinecone and finds:
- Original DB: 5 laptops
- User uploads: 3 laptops
→ Returns top 3 by rating from both sources

---

## 🛡️ Error Handling

### Common Errors & Solutions:

**1. "Unsupported file format"**
- Solution: Use CSV, XLSX, XLS, or JSON files

**2. "File contains no valid data"**
- Solution: Ensure file has headers and data rows
- Remove empty columns/rows

**3. "Pinecone or embedding model not available"**
- Solution: Ensure PINECONE_API_KEY and GEMINI_API_KEY are set in .env

**4. Connection refused (localhost:8000)
- Solution: Start backend server with `uvicorn app:app --reload --port 8000`

**5. CORS Error (frontend can't reach backend)
- Solution: Ensure NEXT_PUBLIC_API_URL matches backend URL in .env.local

---

## 📊 Monitoring Uploads

### Backend Logs:

```
📥 File received: products.csv (50000 bytes)
✅ Parsed CSV file: 1000 rows, 5 columns
📤 Uploading 1000 items from 'products' to Pinecone...
📤 Uploaded 250/1000 items...
📤 Uploaded 500/1000 items...
✅ Successfully uploaded 1000 items from 'products'
```

### Frontend UI:

- **Yellow Clock Icon**: Processing
- **Green Check Icon**: Successfully uploaded
- **Red Alert Icon**: Error with message displayed

---

## ⚙️ Customization

### Change Embedding Model:

**File**: `ai-agent/file_processor.py` (line 20)
```python
MODEL_NAME = "all-MiniLM-L6-v2"  # Change this
```

Available models: [Sentence Transformers](https://www.sbert.net/docs/pretrained_models/all-MiniLM-models.html)

### Change Batch Size:

**File**: `ai-agent/file_processor.py` (line 105)
```python
batch_size = 100  # Process 100 rows at a time
```

### Change Max File Size:

**File**: `app.py` - Add validation in upload endpoint

---

## 🧪 Testing

### Test with Sample Data:

Create `test_products.csv`:
```csv
name,category,price,rating
Laptop Pro,Electronics,100000,4.8
Gaming Mouse,Accessories,5000,4.5
USB Cable,Accessories,200,4.0
```

1. Go to frontend dashboard
2. Upload `test_products.csv`
3. Chat: "What electronics do you have?"
4. Zara should mention your test products

---

## 🔄 Workflow Remains Unchanged

- ✅ Original 9599 products still available
- ✅ Chat format and responses unchanged
- ✅ Embedding search quality improved with more data
- ✅ WhatsApp integration still works
- ✅ All existing features preserved

---

## 📝 Next Steps

1. **Test uploads** with sample CSV files
2. **Monitor logs** to verify data is being processed
3. **Chat with Zara** to verify responses include uploaded data
4. **Scale up** with larger datasets as needed

---

## 🆘 Troubleshooting Checklist

- [ ] Backend running on port 8000?
- [ ] Frontend .env.local configured correctly?
- [ ] Dependencies installed? (`pandas`, `openpyxl`)
- [ ] PINECONE_API_KEY set in .env?
- [ ] GEMINI_API_KEY set in .env?
- [ ] File format is CSV/XLSX/JSON?
- [ ] File has headers in first row?
- [ ] Browser console shows no errors?
- [ ] Backend logs show upload success?

---

## 📞 Support

If you encounter issues:
1. Check the backend logs for error messages
2. Verify all environment variables are set
3. Ensure file format and structure are correct
4. Try with a small test file first

