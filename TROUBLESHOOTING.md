# Troubleshooting: File Upload Errors

## 🔴 Error: "TypeError: Failed to fetch"

This means the frontend cannot connect to the backend. Here are the fixes:

### ✅ Fix 1: Enable CORS (DONE)
- CORS middleware has been added to `app.py`
- Backend will now accept requests from any origin (dev only)

### ✅ Fix 2: Backend Must Be Running

**Make sure your backend server is running:**

```bash
# Terminal 1: Navigate to FYP folder
cd c:\Users\Aims Tech\Downloads\Sem7\FYP\fyp2\FYP

# Start the backend server
uvicorn app:app --reload --port 8000
```

**You should see output like:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
✅ All environment variables loaded!
✅ Chat model initialized successfully
```

### ✅ Fix 3: Verify API URL Configuration

Check `frontend/.env.local`:
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

**If backend runs on different port:**
```
NEXT_PUBLIC_API_URL=http://localhost:YOUR_PORT
```

After changing, restart frontend dev server:
```bash
cd frontend
pnpm dev
```

---

## 🟡 Hydration Mismatch Warning

This is a minor warning caused by browser extensions. It won't affect functionality.

**Solution:** Disable any browser extensions that modify HTML (e.g., Scholarcy, Grammarly, etc.)

---

## 📋 Step-by-Step Setup

### Terminal 1: Backend
```bash
cd c:\Users\Aims Tech\Downloads\Sem7\FYP\fyp2\FYP
uvicorn app:app --reload --port 8000
```

Wait for:
```
✅ All environment variables loaded!
✅ GeminiChatModel ready!
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### Terminal 2: Frontend
```bash
cd frontend
pnpm install  # if not done yet
pnpm dev
```

Wait for:
```
- Local:        http://localhost:3000
```

### Terminal 3: Check Logs (Optional)
```bash
# Monitor API calls
curl http://localhost:8000/
# Should return: {"status": "Bot is running ✓", ...}
```

---

## ✅ Verification Checklist

- [ ] Backend terminal shows "Uvicorn running on http://127.0.0.1:8000"?
- [ ] Frontend running at http://localhost:3000?
- [ ] `frontend/.env.local` contains `NEXT_PUBLIC_API_URL=http://localhost:8000`?
- [ ] All dependencies installed (`pandas`, `openpyxl`, `pillow`)?
- [ ] PINECONE_API_KEY and GEMINI_API_KEY set in `.env`?
- [ ] Browser console doesn't show "Failed to fetch"?

---

## 🧪 Test Upload

1. Go to http://localhost:3000
2. Navigate to **File Upload** section
3. Create a test CSV:
   ```csv
   name,category,price
   Laptop,Electronics,50000
   Phone,Electronics,30000
   ```
4. Click "Select Files" and upload the CSV
5. Should show **Green checkmark** when complete
6. If error, check browser console for error message

---

## 🐛 Debug Commands

### Check Backend is Responding
```bash
curl http://localhost:8000/
```

Should return:
```json
{
  "status": "Bot is running ✓",
  "environment": {
    "ACCESS_TOKEN": "✓",
    "PHONE_ID": "✓",
    "VERIFY_TOKEN": "✓",
    "APP_SECRET": "✓"
  }
}
```

### Check API Endpoint Exists
```bash
curl -X POST http://localhost:8000/api/upload \
  -F "file=@test.csv"
```

### Clear Browser Cache
```bash
# Delete Next.js cache
rm -r frontend/.next

# Restart frontend
cd frontend && pnpm dev
```

---

## 📝 Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| "Failed to fetch" | Backend not running | Start backend with `uvicorn` |
| "Connection refused" | Wrong port | Check `.env.local` for correct port |
| "CORS error" | CORS not enabled | Already fixed in latest `app.py` |
| "File not found" | Wrong file format | Use CSV, XLSX, or JSON |
| "401 Unauthorized" | Wrong API keys | Check PINECONE_API_KEY and GEMINI_API_KEY |
| Hydration warning | Browser extension | Disable Scholarcy, Grammarly, etc. |

---

## 🚀 Everything Looks Good?

If all checks pass, file upload is ready! Try uploading a CSV with your product data.

