import json
import logging
import os
import re
import time

from google import genai
from google.genai import types
from django.db import connection

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
client = genai.Client(api_key=GEMINI_API_KEY)

DB_SCHEMA = """
You have access to two PostGIS tables in a PostgreSQL database:

1. geo_uploadedfeature
   - id (bigint, PK)
   - upload_session_id (uuid)
   - feature_index (integer)
   - properties (jsonb) — original shapefile attributes
   - geom (geometry, SRID=4326)
   - uploaded_at (timestamptz)

   Key properties (access via properties->>'key'):
     - '構造' — structure type (e.g. '木造'=wooden, 'ＲＣ'=reinforced concrete)
     - '建物用途_C' — building usage code
     - '建物階数' — number of floors (text, cast to int)
     - '高さ' — height in meters (text, cast to float)
     - '浸水ランク' — flood inundation rank
     - '全壊Flag' — total collapse flag ('1' = collapsed)
     - '現象区分' — damage/phenomenon type
     - '建物面積' — building footprint area from shapefile (text, cast to float)
     - '差_Height' — height difference
     - 'PLATEAU_He' — PLATEAU height
     - 'Height' — height value
     - 'usage' — building usage
     - 'storeysAbo' — storeys above ground
     - 'totalFloor' — total floor area

2. geo_classifiedbuilding
   - id (bigint, PK)
   - upload_session_id (uuid)
   - analysis_session_id (bigint, nullable)
   - feature_index (integer)
   - classification (varchar) — one of: 'unchanged', 'modified', 'removed', 'new', 'unknown'
   - confidence (float, nullable)
   - iou_score (float, nullable)
   - pixel_score (float, nullable)
   - properties (jsonb)
   - input_geom (geometry, SRID=4326) — original footprint
   - detected_geom (geometry, SRID=4326, nullable) — SAM-detected footprint
   - classified_at (timestamptz)

Spatial functions available: ST_Area, ST_Perimeter, ST_Within, ST_Intersects,
ST_DWithin, ST_Buffer, ST_Centroid, ST_Distance, ST_AsGeoJSON, ST_MakeEnvelope,
ST_SetSRID, ST_MakePoint, ST_Transform, ST_Union, ST_Collect.

For area/distance in meters, cast to geography: geom::geography or input_geom::geography

IMPORTANT RULES:
- Generate ONLY SELECT statements. Never INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE.
- Always include ST_AsGeoJSON(geom) or ST_AsGeoJSON(input_geom) so results can be mapped.
- LIMIT results to 500 max unless the user asks for a count/aggregate.
- For classification queries, use geo_classifiedbuilding.
- For raw building data, use geo_uploadedfeature.
- When the user says "changed" or "modified", filter classification = 'modified'.
- When the user says "destroyed" or "removed" or "demolished", filter classification = 'removed'.
- When the user says "unchanged" or "same" or "intact", filter classification = 'unchanged'.
- For area queries, use ST_Area(geom::geography) which returns square meters.
- For distance queries, use ST_DWithin(geom::geography, ..., distance_in_meters).
- Always return id and feature_index for frontend linkage.
- For "big roofs" or "large buildings", use ST_Area(geom::geography) > threshold.
"""

SYSTEM_PROMPT = f"""You are a spatial data assistant for a building damage assessment system.
You convert natural language questions into PostGIS SQL queries.

{DB_SCHEMA}

Respond ONLY with a JSON object in this exact format (no markdown, no code fences):
{{
  "explanation": "Brief human-readable explanation of what the query does",
  "sql": "SELECT ... FROM ... WHERE ... LIMIT 500;",
  "map_filter": null or "unchanged" or "modified" or "removed" or "new",
  "is_aggregate": false
}}

- "map_filter" should be set when the user asks about a classification category,
  so the frontend can highlight those buildings on the map.
- "is_aggregate" should be true for COUNT, AVG, SUM queries that don't return geometries.
- If the user's question cannot be answered with SQL, set sql to null and explain why.
"""

MODELS = [
    "gemini-2.5-flash-lite",
]

MAX_RETRIES = 3
RETRY_BASE_DELAY = 10


def generate_sql_from_prompt(user_message: str, session_id: str = None) -> dict:
    """
    Send user message to Gemini, get back a SQL query plan.
    Retries on rate limit (429) with exponential backoff and model fallback.
    """
    context = ""
    if session_id:
        context = (
            f"\nThe current upload session ID is '{session_id}'. "
            f"Filter by upload_session_id = '{session_id}' unless the user asks about all sessions."
        )

    full_prompt = SYSTEM_PROMPT + context + "\n\nUser question: " + user_message

    last_error = None

    for model_name in MODELS:
        for attempt in range(MAX_RETRIES):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=full_prompt,
                    config=types.GenerateContentConfig(
                        temperature=0,
                        response_mime_type="application/json",
                    ),
                )

                content = response.text.strip()

                if content.startswith("```"):
                    content = re.sub(r"^```(?:json)?\s*", "", content)
                    content = re.sub(r"\s*```$", "", content)

                result = json.loads(content)
                logger.info("Gemini query succeeded with model=%s attempt=%d", model_name, attempt + 1)
                return result

            except json.JSONDecodeError as e:
                logger.error("Failed to parse Gemini response as JSON: %s\nRaw: %s", e, content)
                return {
                    "explanation": "Failed to parse LLM response. Please rephrase your question.",
                    "sql": None,
                    "map_filter": None,
                    "is_aggregate": False,
                }

            except Exception as e:
                last_error = e
                error_str = str(e)

                # Check if it's a rate limit error
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    delay_match = re.search(r"retry in ([\d.]+)s", error_str, re.IGNORECASE)
                    delay = float(delay_match.group(1)) if delay_match else RETRY_BASE_DELAY * (2 ** attempt)
                    delay = min(delay, 60)  # cap at 60s

                    logger.warning(
                        "Rate limited on %s (attempt %d/%d). Retrying in %.1fs...",
                        model_name, attempt + 1, MAX_RETRIES, delay,
                    )
                    time.sleep(delay)
                    continue
                else:
                    # Non-rate-limit error — don't retry
                    logger.error("Gemini call failed (non-retryable): %s", e, exc_info=True)
                    return {
                        "explanation": f"Failed to generate query: {str(e)}",
                        "sql": None,
                        "map_filter": None,
                        "is_aggregate": False,
                    }

        # All retries exhausted for this model, try next model
        logger.warning("All retries exhausted for model %s, trying next model...", model_name)

    # All models exhausted
    logger.error("All Gemini models exhausted. Last error: %s", last_error)
    return {
        "explanation": "Rate limit exceeded on all models. Please wait a minute and try again.",
        "sql": None,
        "map_filter": None,
        "is_aggregate": False,
    }


def validate_sql(sql: str) -> tuple[bool, str]:
    """
    Validate that the SQL is safe (read-only, no mutations).
    Returns (is_safe, error_message).
    """
    if not sql:
        return False, "No SQL generated"

    sql_upper = sql.upper().strip()

    forbidden = [
        "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
        "CREATE", "GRANT", "REVOKE", "EXEC", "EXECUTE", "COPY",
        "\\\\", "--", "/*",
    ]

    for keyword in forbidden:
        pattern = r'(?<![A-Z_])' + re.escape(keyword) + r'(?![A-Z_])'
        if re.search(pattern, sql_upper):
            return False, f"Forbidden keyword detected: {keyword}"

    if not (sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")):
        return False, "Query must start with SELECT or WITH"

    return True, ""


def execute_safe_query(sql: str, limit: int = 500) -> dict:
    """
    Execute a validated read-only SQL query and return results.
    """
    sql_upper = sql.upper().strip().rstrip(";")
    if "LIMIT" not in sql_upper:
        sql = f"{sql.strip().rstrip(';')} LIMIT {limit};"

    with connection.cursor() as cur:
        cur.execute("SET TRANSACTION READ ONLY;")

        try:
            cur.execute(sql)
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
        except Exception as e:
            return {"error": str(e), "rows": [], "columns": []}

    return {
        "columns": columns,
        "rows": [dict(zip(columns, row)) for row in rows],
        "row_count": len(rows),
    }


def rows_to_geojson(rows: list[dict]) -> dict:
    """
    Convert query result rows into a GeoJSON FeatureCollection.
    """
    geojson_keys = [k for k in (rows[0].keys() if rows else [])
                    if "geojson" in k.lower() or "st_asgeojson" in k.lower()]

    features = []
    for row in rows:
        geom = None
        props = {}

        for key, val in row.items():
            if key in geojson_keys and val:
                try:
                    geom = json.loads(val) if isinstance(val, str) else val
                except (json.JSONDecodeError, TypeError):
                    props[key] = val
            else:
                if hasattr(val, "isoformat"):
                    props[key] = val.isoformat()
                elif isinstance(val, (int, float, str, bool, type(None))):
                    props[key] = val
                else:
                    props[key] = str(val)

        if geom:
            features.append({
                "type": "Feature",
                "geometry": geom,
                "properties": props,
            })
        else:
            features.append({
                "type": "Feature",
                "geometry": None,
                "properties": props,
            })

    return {
        "type": "FeatureCollection",
        "features": features,
    }


def chat_query(user_message: str, session_id: str = None) -> dict:
    """
    Full pipeline: user message → Gemini LLM → SQL → execute → GeoJSON response.
    """
    plan = generate_sql_from_prompt(user_message, session_id)

    if not plan.get("sql"):
        return {
            "explanation": plan.get("explanation", "Could not generate a query."),
            "sql": None,
            "map_filter": plan.get("map_filter"),
            "geojson": None,
            "results": None,
        }

    sql = plan["sql"]

    is_safe, error = validate_sql(sql)
    if not is_safe:
        logger.warning("Unsafe SQL blocked: %s — %s", error, sql)
        return {
            "explanation": f"Query blocked for safety: {error}",
            "sql": sql,
            "map_filter": None,
            "geojson": None,
            "results": None,
        }

    result = execute_safe_query(sql)

    if "error" in result and result["error"]:
        return {
            "explanation": f"Query error: {result['error']}",
            "sql": sql,
            "map_filter": plan.get("map_filter"),
            "geojson": None,
            "results": None,
        }

    geojson = rows_to_geojson(result["rows"]) if result["rows"] else None

    return {
        "explanation": plan.get("explanation", ""),
        "sql": sql,
        "map_filter": plan.get("map_filter"),
        "is_aggregate": plan.get("is_aggregate", False),
        "row_count": result["row_count"],
        "geojson": geojson,
        "results": result["rows"] if plan.get("is_aggregate") else None,
    }