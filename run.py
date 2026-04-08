"""
Entry point — BDFit Marketing Bot Dashboard.
Works locally (reads .env) and on Railway/Render (reads env vars directly).
"""

import os
import sys
from pathlib import Path

# Load .env only if it exists (local dev). Cloud platforms inject vars directly.
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    from dotenv import load_dotenv
    load_dotenv()

def main():
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("⚠️  ANTHROPIC_API_KEY is not set.")
        print("   Local: add it to your .env file")
        print("   Railway: add it in the Variables tab of your service")
        sys.exit(1)

    host = os.getenv("APP_HOST", "0.0.0.0")
    # Railway injects PORT; fall back to APP_PORT then 8000
    port = int(os.getenv("PORT") or os.getenv("APP_PORT") or 8000)

    print(f"""
╔══════════════════════════════════════════════════════╗
║       🏃 BDFit Marketing Bot Dashboard              ║
║       @bdfitindahouse · Bruno Diaz                  ║
╠══════════════════════════════════════════════════════╣
║  Agent 1 — News Scout    → runs daily at 9:00 AM    ║
║  Agent 2 — Content Creator → triggers on approval   ║
╠══════════════════════════════════════════════════════╣
║  Dashboard → http://0.0.0.0:{port:<24} ║
╚══════════════════════════════════════════════════════╝
""")

    import uvicorn
    uvicorn.run(
        "api.server:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )

if __name__ == "__main__":
    main()
