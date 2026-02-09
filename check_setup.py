#!/usr/bin/env python3
"""
check_setup.py
──────────────
Quick diagnostic script to verify Outreach Engine setup.
Run with: python check_setup.py
"""

import sys
import subprocess
from pathlib import Path

def c(text: str, color: str) -> str:
    """Colorize text for terminal."""
    colors = {
        "green": "\033[92m",
        "red": "\033[91m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "cyan": "\033[96m",
        "reset": "\033[0m",
        "bold": "\033[1m"
    }
    return f"{colors.get(color, '')}{text}{colors['reset']}"

def check_python():
    """Check Python version."""
    version = sys.version_info
    if version.major >= 3 and version.minor >= 10:
        print(f"  {c('✓', 'green')} Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"  {c('✗', 'red')} Python {version.major}.{version.minor} (need 3.10+)")
        return False

def check_ollama():
    """Check Ollama installation and running status."""
    try:
        # Check if ollama command exists
        result = subprocess.run(
            ["ollama", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version = result.stdout.strip() or result.stderr.strip()
            print(f"  {c('✓', 'green')} Ollama installed: {version}")
        else:
            print(f"  {c('✗', 'red')} Ollama not working")
            return False, []
    except FileNotFoundError:
        print(f"  {c('✗', 'red')} Ollama not installed")
        print(f"      Download from: https://ollama.ai/download")
        return False, []
    except Exception as e:
        print(f"  {c('✗', 'red')} Ollama check failed: {e}")
        return False, []
    
    # Check if Ollama is running
    try:
        import urllib.request
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            import json
            data = json.loads(resp.read().decode())
            models = [m["name"] for m in data.get("models", [])]
            if models:
                print(f"  {c('✓', 'green')} Ollama running - {len(models)} model(s) available:")
                for m in models[:5]:
                    print(f"      • {m}")
                if len(models) > 5:
                    print(f"      ... and {len(models) - 5} more")
                return True, models
            else:
                print(f"  {c('⚠', 'yellow')} Ollama running but no models pulled")
                print(f"      Run: ollama pull mistral")
                return True, []
    except Exception:
        print(f"  {c('⚠', 'yellow')} Ollama installed but not running")
        print(f"      Start it with: ollama serve")
        return False, []

def check_env():
    """Check .env file."""
    env_path = Path(".env")
    if env_path.exists():
        print(f"  {c('✓', 'green')} .env file exists")
        # Check for OLLAMA_MODEL
        content = env_path.read_text()
        if "OLLAMA_MODEL" in content:
            for line in content.split("\n"):
                if line.startswith("OLLAMA_MODEL"):
                    model = line.split("=")[1].strip() if "=" in line else "?"
                    print(f"      Configured model: {c(model, 'cyan')}")
        return True
    else:
        print(f"  {c('⚠', 'yellow')} .env file not found")
        print(f"      Copy from: cp .env.example .env")
        return False

def check_dependencies():
    """Check Python dependencies."""
    try:
        import fastapi
        print(f"  {c('✓', 'green')} FastAPI installed")
    except ImportError:
        print(f"  {c('✗', 'red')} FastAPI not installed")
        return False
    
    try:
        import langchain_ollama
        print(f"  {c('✓', 'green')} LangChain Ollama installed")
    except ImportError:
        print(f"  {c('✗', 'red')} LangChain Ollama not installed")
        return False
    
    try:
        from langgraph.graph import StateGraph
        print(f"  {c('✓', 'green')} LangGraph installed")
    except ImportError:
        print(f"  {c('✗', 'red')} LangGraph not installed")
        return False
    
    return True

def check_node():
    """Check Node.js for frontend."""
    try:
        result = subprocess.run(
            ["node", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"  {c('✓', 'green')} Node.js {version}")
            return True
    except:
        pass
    print(f"  {c('⚠', 'yellow')} Node.js not found (needed for frontend)")
    return False

def main():
    print()
    print(c("═" * 50, "blue"))
    print(c("  OUTREACH ENGINE SETUP CHECK", "bold"))
    print(c("═" * 50, "blue"))
    print()
    
    all_ok = True
    
    print(c("[ Python ]", "cyan"))
    if not check_python():
        all_ok = False
    print()
    
    print(c("[ Dependencies ]", "cyan"))
    if not check_dependencies():
        all_ok = False
        print(f"      Run: pip install -r requirements.txt")
    print()
    
    print(c("[ Ollama LLM ]", "cyan"))
    ollama_ok, models = check_ollama()
    if not ollama_ok:
        all_ok = False
    print()
    
    print(c("[ Configuration ]", "cyan"))
    check_env()
    print()
    
    print(c("[ Frontend ]", "cyan"))
    check_node()
    print()
    
    print(c("═" * 50, "blue"))
    if all_ok and models:
        print(c("  ✓ All systems ready! Run: python start.ps1", "green"))
    elif all_ok:
        print(c("  ⚠ Setup incomplete. Pull an Ollama model first.", "yellow"))
    else:
        print(c("  ✗ Setup issues found. See above for fixes.", "red"))
    print(c("═" * 50, "blue"))
    print()

if __name__ == "__main__":
    main()
