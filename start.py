import os
import uvicorn
# START FILE
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"Starting on port {port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port)