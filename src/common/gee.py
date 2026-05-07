import json
import os
from typing import Any

import ee


DEFAULT_PROJECT_ID = "valid-shine-488311-d6"
_GEE_INITIALIZED = False


def get_project_id() -> str:
    return (
        os.getenv("ARASENSE_GCP_PROJECT")
        or os.getenv("GOOGLE_CLOUD_PROJECT")
        or os.getenv("GCP_PROJECT")
        or DEFAULT_PROJECT_ID
    )


def _normalize_service_account_info(raw_info: Any) -> dict[str, Any]:
    info = dict(raw_info)
    private_key = info.get("private_key", "")
    if private_key:
        info["private_key"] = private_key.replace("\\n", "\n")
    return info


def _get_st_secrets():
    """Try to get secrets from Streamlit if available."""
    try:
        import streamlit as st
        if hasattr(st, 'secrets'):
            return dict(st.secrets)
    except Exception:
        pass
    return None


def initialize_earth_engine(project_id: str | None = None) -> str:
    global _GEE_INITIALIZED

    if _GEE_INITIALIZED:
        return project_id or get_project_id()

    project = project_id or get_project_id()

    # Check Streamlit secrets first
    st_secrets = _get_st_secrets()
    
    # Try gcp_service_account from secrets
    if st_secrets and 'gcp_service_account' in st_secrets:
        info = _normalize_service_account_info(dict(st_secrets['gcp_service_account']))
        email = info.get("client_email")
        if email and info.get("private_key"):
            credentials = ee.ServiceAccountCredentials(email, key_data=json.dumps(info))
            ee.Initialize(credentials, project=project)
            _GEE_INITIALIZED = True
            return project
    
    # Try GCP_JSON_KEY from secrets
    if st_secrets and 'GCP_JSON_KEY' in st_secrets:
        raw_json = st_secrets['GCP_JSON_KEY']
        if isinstance(raw_json, str):
            raw_json = raw_json.replace('\n', '\\n')
        info = _normalize_service_account_info(json.loads(raw_json))
        email = info.get("client_email")
        if email and info.get("private_key"):
            credentials = ee.ServiceAccountCredentials(email, key_data=json.dumps(info))
            ee.Initialize(credentials, project=project)
            _GEE_INITIALIZED = True
            return project

    # Fall back to environment variables
    service_account_json = os.getenv("GCP_SERVICE_ACCOUNT_JSON") or os.getenv("GCP_JSON_KEY")
    client_email = os.getenv("EE_CLIENT_EMAIL")
    private_key = os.getenv("EE_PRIVATE_KEY")

    if service_account_json:
        info = _normalize_service_account_info(json.loads(service_account_json))
        email = info.get("client_email")
        if not email or not info.get("private_key"):
            raise ValueError("Service account JSON is missing client_email or private_key.")
        credentials = ee.ServiceAccountCredentials(email, key_data=json.dumps(info))
        ee.Initialize(credentials, project=project)
    elif client_email and private_key:
        info = _normalize_service_account_info(
            {
                "type": "service_account",
                "client_email": client_email,
                "private_key": private_key,
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        )
        credentials = ee.ServiceAccountCredentials(client_email, key_data=json.dumps(info))
        ee.Initialize(credentials, project=project)
    else:
        ee.Initialize(project=project)

    _GEE_INITIALIZED = True
    return project


def get_earth_engine_status(project_id: str | None = None) -> dict[str, str]:
    project = project_id or get_project_id()

    try:
        initialize_earth_engine(project)
    except Exception as exc:
        return {
            "status": "degraded",
            "project_id": project,
            "detail": str(exc),
        }

    return {
        "status": "ok",
        "project_id": project,
        "detail": "Earth Engine initialized.",
    }
