# backend/__main__.py
import uvicorn

def main():
    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    main()
