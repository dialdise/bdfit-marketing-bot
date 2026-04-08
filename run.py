"""
Entry point — start the BDFit Marketing Bot Dashboard.
Usage: python run.py
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    # Check for .env
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        example = Path(__file__).parent / ".env.example"
        print("⚠️  No .env file found.")
        print(f"   Copy .env.example to .env and add your ANTHROPIC_API_KEY:")
        print(f"   cp .env.example .env")
        print(f"   Then edit .env and set your API key.")
        sys.exit(1)

    # Check API key
    from dotenv import load_dotenv
    load_dotenv()
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("⚠️  ANTHROPIC_API_KEY not set in .env")
        sys.exit(1)

    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", 8000))

    print(f"""
╔══════════════════════════════════════════════════════╗
║       🏃 BDFit Marketing Bot Dashboard              ║
║       @bdfitindahouse · Bruno Diaz                  ║
╠══════════════════════════════════════════════════════╣
║  Agent 1 — News Scout    → runs daily at 9:00 AM    ║
║  Agent 2 — Content Creator → triggers on approval   ║
╠══════════════════════════════════════════════════════╣
║  Dashboard → http://localhost:{port:<22} ║
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
