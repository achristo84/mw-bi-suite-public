#!/usr/bin/env python3
"""
Browser Capture Script - Captures network traffic using Playwright CDP.

Usage:
    python scripts/capture_browser.py [--url URL] [--output DIR] [--name NAME]

Examples:
    python scripts/capture_browser.py --url "https://example.com" --name distributor-capture
    python scripts/capture_browser.py  # Opens blank browser, saves to captures/session-{timestamp}

The browser window opens for you to interact with manually.
Press Enter in the terminal when done to save and close.
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from playwright.sync_api import sync_playwright, Request, Response
except ImportError:
    print("Playwright not installed. Run:")
    print("  pip install playwright")
    print("  playwright install chromium")
    sys.exit(1)


class NetworkCapture:
    """Captures network requests and responses."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.requests: list[dict[str, Any]] = []
        self.responses: list[dict[str, Any]] = []
        self.cookies_timeline: list[dict[str, Any]] = []
        self.console_logs: list[dict[str, Any]] = []
        self.request_map: dict[str, dict] = {}  # Track requests by ID for response matching

        self.start_time = time.time()

    def _timestamp(self) -> float:
        return time.time() - self.start_time

    def on_request(self, request: Request):
        """Called for each network request."""
        req_data = {
            "timestamp": self._timestamp(),
            "url": request.url,
            "method": request.method,
            "headers": dict(request.headers),
            "post_data": None,
            "resource_type": request.resource_type,
        }

        # Capture POST data if present
        try:
            post_data = request.post_data
            if post_data:
                req_data["post_data"] = post_data
        except Exception:
            pass

        self.requests.append(req_data)
        # Store for response matching
        self.request_map[request.url + request.method] = req_data

    def on_response(self, response: Response):
        """Called for each network response."""
        resp_data = {
            "timestamp": self._timestamp(),
            "url": response.url,
            "status": response.status,
            "status_text": response.status_text,
            "headers": dict(response.headers),
            "body": None,
            "body_size": None,
        }

        # Try to capture response body for JSON/text responses
        content_type = response.headers.get("content-type", "")
        if any(t in content_type for t in ["application/json", "text/", "javascript"]):
            try:
                body = response.text()
                resp_data["body"] = body
                resp_data["body_size"] = len(body)
            except Exception:
                pass

        self.responses.append(resp_data)

    def on_console(self, msg):
        """Called for console messages."""
        self.console_logs.append({
            "timestamp": self._timestamp(),
            "type": msg.type,
            "text": msg.text,
        })

    def capture_cookies(self, context, label: str):
        """Capture current cookie state."""
        cookies = context.cookies()
        self.cookies_timeline.append({
            "timestamp": self._timestamp(),
            "label": label,
            "cookies": cookies,
        })

    def save(self):
        """Save all captured data to disk."""
        # Save requests
        with open(self.output_dir / "requests.jsonl", "w") as f:
            for req in self.requests:
                f.write(json.dumps(req) + "\n")

        # Save responses
        with open(self.output_dir / "responses.jsonl", "w") as f:
            for resp in self.responses:
                f.write(json.dumps(resp) + "\n")

        # Save cookies timeline
        with open(self.output_dir / "cookies.jsonl", "w") as f:
            for entry in self.cookies_timeline:
                f.write(json.dumps(entry) + "\n")

        # Save console logs
        with open(self.output_dir / "console.jsonl", "w") as f:
            for log in self.console_logs:
                f.write(json.dumps(log) + "\n")

        # Save metadata
        metadata = {
            "capture_start": datetime.now().isoformat(),
            "duration_seconds": self._timestamp(),
            "total_requests": len(self.requests),
            "total_responses": len(self.responses),
            "console_logs": len(self.console_logs),
            "cookie_snapshots": len(self.cookies_timeline),
        }
        with open(self.output_dir / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

        return metadata


def main():
    parser = argparse.ArgumentParser(description="Capture browser network traffic")
    parser.add_argument("--url", default="about:blank", help="Starting URL")
    parser.add_argument("--output", default="captures", help="Output directory base")
    parser.add_argument("--name", help="Session name (default: session-{timestamp})")
    args = parser.parse_args()

    # Determine output directory
    if args.name:
        session_name = args.name
    else:
        session_name = f"session-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    output_dir = Path(args.output) / session_name

    print(f"Starting capture session: {session_name}")
    print(f"Output directory: {output_dir}")
    print(f"Starting URL: {args.url}")
    print()

    capture = NetworkCapture(output_dir)

    with sync_playwright() as p:
        # Launch browser - visible for user interaction
        # Using Firefox as it's more stable on macOS
        browser = p.firefox.launch(
            headless=False,
        )

        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        page = context.new_page()

        # Set up event listeners
        page.on("request", capture.on_request)
        page.on("response", capture.on_response)
        page.on("console", capture.on_console)

        # Capture initial cookies
        capture.capture_cookies(context, "initial")

        # Navigate to starting URL
        if args.url != "about:blank":
            print(f"Navigating to {args.url}...")
            page.goto(args.url, wait_until="domcontentloaded")

        # Create signal file path
        stop_signal = output_dir / ".stop"

        print()
        print("=" * 60)
        print("Browser is ready. Interact with it as needed.")
        print("All network requests are being captured.")
        print()
        print(f"To stop capturing, create this file: {stop_signal}")
        print("  Or press Ctrl+C in this terminal")
        print("=" * 60)
        print()

        # Wait for stop signal file or keyboard interrupt
        try:
            while not stop_signal.exists():
                time.sleep(0.5)
            print("Stop signal received.")
        except KeyboardInterrupt:
            print("\nInterrupted.")

        # Capture final cookies
        capture.capture_cookies(context, "final")

        # Save everything
        print("Saving capture data...")
        metadata = capture.save()

        browser.close()

    print()
    print("=" * 60)
    print("Capture complete!")
    print(f"  Requests:  {metadata['total_requests']}")
    print(f"  Responses: {metadata['total_responses']}")
    print(f"  Console:   {metadata['console_logs']}")
    print(f"  Duration:  {metadata['duration_seconds']:.1f}s")
    print()
    print(f"Data saved to: {output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
