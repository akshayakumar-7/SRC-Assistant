"""Flask application for the SRC campus assistant.

Campus lookups are resolved locally from the JSON data.  Groq is used only
for messages that are not identifiable as campus location or route requests.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import re
import time
from typing import Any

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from groq import Groq

from location_matching import LocationResolution, LocationResolver, normalize


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _load_json(filename: str) -> Any:
    """Load one required data file relative to the application directory."""

    with (BASE_DIR / filename).open("r", encoding="utf-8") as file:
        return json.load(file)


locations = _load_json("locations.json")
aliases = _load_json("aliases.json")
campus_graph = _load_json("campus_graph.json")
resolver = LocationResolver(locations, aliases, campus_graph)

app = Flask(__name__)

# The client is deliberately lazy: importing the Flask app does not require a
# key, and no secret value is ever logged or returned to a caller.
client: Groq | Any | None = None
GROQ_MODEL = "openai/gpt-oss-20b"
MAX_MESSAGE_LENGTH = 1_000

_ROUTE_RE = re.compile(r"\bfrom\s+(.+?)\s+to\s+(.+)$")
_LOCATION_MARKER_RE = re.compile(
    r"\b(?:where|location|locate|find|room|hall|lab|laboratory|facility|"
    r"building|directions?|navigate|get to)\b"
)


def find_location(user_query: Any) -> str | None:
    """Return a verified canonical location key, or ``None``."""

    return resolver.find_location(user_query)


def find_floor(place: Any) -> Any:
    """Return a floor only when the location and graph entry are verified."""

    return resolver.find_floor(place)


def get_route(start_place: Any, end_place: Any) -> list[str] | None:
    """Return a floor-level route for two verified locations."""

    return resolver.get_route(start_place, end_place)


def _get_groq_client() -> Groq | Any | None:
    """Create the Groq client on demand without exposing configuration."""

    global client
    if client is not None:
        return client
    if not os.getenv("GROQ_API_KEY"):
        return None

    try:
        client = Groq(timeout=15.0)
    except Exception:
        # Do not include exception details: SDK errors can contain request
        # metadata, and a missing provider should not break local lookups.
        logger.warning("Groq client could not be initialized")
        return None
    return client


def _is_location_question(message: str, resolution: LocationResolution) -> bool:
    """Identify campus-shaped requests without sending them to the model."""

    if resolution.status in {"resolved", "ambiguous"}:
        return True
    return bool(_LOCATION_MARKER_RE.search(normalize(message)))


def _resolution_reply(resolution: LocationResolution) -> str:
    if resolution.status == "ambiguous":
        candidates = resolution.candidates[:5]
        if candidates:
            choices = ", ".join(candidates)
            return (
                "I found more than one possible location. Please use the full "
                f"name, such as one of: {choices}."
            )
        return "I found more than one possible location. Please use the full name."

    return (
        "I couldn't confidently identify that location from the verified campus "
        "data. Please enter the full hall, room, lab, or a registered alias."
    )


def _route_reply(message: str) -> tuple[bool, str | None]:
    """Handle a route-shaped message and return (was_route, reply)."""

    match = _ROUTE_RE.search(normalize(message))
    if not match:
        return False, None

    start_text, destination_text = match.groups()
    start_resolution = resolver.resolve(start_text)
    destination_resolution = resolver.resolve(destination_text)

    if start_resolution.status != "resolved" or destination_resolution.status != "resolved":
        return True, (
            "I couldn't verify both route endpoints. Please use full registered "
            "location names or aliases for the starting point and destination."
        )

    route = resolver.generate_route(start_text, destination_text)
    if route is None:
        return True, (
            "Both locations are known, but the available campus graph does not "
            "contain enough verified floor data to produce this route."
        )
    return True, "\n".join(route)


@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/chatbot")
def chatbot():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    """Return a verified campus answer or a guarded general-AI answer."""

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"reply": "Please send a JSON object with a message."}), 400

    user_message = data.get("message")
    if not isinstance(user_message, str):
        return jsonify({"reply": "Please enter a message."}), 400

    user_message = user_message.strip()
    if not user_message:
        return jsonify({"reply": "Please enter a message."}), 400
    if len(user_message) > MAX_MESSAGE_LENGTH:
        return jsonify({"reply": "Please keep the message under 1,000 characters."}), 413

    resolution = resolver.resolve(user_message)

    was_route, route_reply = _route_reply(user_message)
    if was_route:
        return jsonify({"reply": route_reply})

    if _is_location_question(user_message, resolution):
        if resolution.status == "resolved" and resolution.canonical:
            return jsonify({"reply": locations[resolution.canonical]})
        return jsonify({"reply": _resolution_reply(resolution)})

    groq_client = _get_groq_client()
    if groq_client is None:
        return jsonify({
            "reply": (
                "The general AI service is not available right now. I can still "
                "answer verified campus location and route questions."
            )
        })

    started_at = time.perf_counter()
    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are SRC Assistant for SASTRA SRC Kumbakonam. "
                        "Answer briefly and clearly. Campus locations, rooms, "
                        "facilities, and routes are handled by verified local "
                        "data; do not invent them. If campus information is not "
                        "available, say so plainly."
                    ),
                },
                {"role": "user", "content": user_message},
            ],
            max_tokens=150,
            temperature=0.3,
        )
        reply = response.choices[0].message.content
        if not isinstance(reply, str) or not reply.strip():
            reply = "Sorry, I couldn't generate a response."
        logger.info("General AI response completed in %.2fs", time.perf_counter() - started_at)
        return jsonify({"reply": reply.strip()})
    except Exception:
        # Keep provider errors out of the response and logs. Local campus data
        # remains available even when Groq is unavailable.
        logger.warning("Groq request failed after %.2fs", time.perf_counter() - started_at)
        return jsonify({
            "reply": (
                "I'm having trouble connecting to the general AI right now. "
                "Please try again, or ask me about a verified campus location."
            )
        })


if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "").casefold() in {"1", "true", "yes"}
    app.run(debug=debug)
