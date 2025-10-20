"""
YouTube API Authentication Module
Handles both service account and OAuth authentication for YouTube API access.
"""

from __future__ import annotations

import os
import pickle

import jsonc  # type: ignore
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore
from googleapiclient.discovery import build  # type: ignore

from config import Config
from youtube_types import YouTubeResource

SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']


def get_youtube_service(service_account_file: str) -> YouTubeResource:
    """
    Create and return an authenticated YouTube API service using service account.
    
    Args:
        service_account_file: Path to the service account JSON key file
        
    Returns:
        Authenticated YouTube API service
    """
    credentials = service_account.Credentials.from_service_account_file(
        service_account_file,
        scopes=SCOPES
    )
    
    # Build and return the YouTube API service
    youtube = build('youtube', 'v3', credentials=credentials)
    return youtube  # type: ignore[return-value]


def get_youtube_service_oauth(
    credentials_file: str, 
    token_file: str = 'token.pickle'
) -> YouTubeResource:
    """
    Create and return an authenticated YouTube API service using OAuth.
    This requires user login the first time, then saves a token for future use.
    
    Args:
        credentials_file: Path to OAuth client credentials JSON
        token_file: Path to save/load the authentication token
        
    Returns:
        Authenticated YouTube API service
    """
    credentials = None
    
    # Check if we have saved credentials
    if os.path.exists(token_file):
        with open(token_file, 'rb') as token:
            credentials = pickle.load(token)
    
    # If no valid credentials, let user log in
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            print("Refreshing expired credentials...")
            credentials.refresh(Request())
        else:
            print("No valid credentials found. Starting OAuth flow...")
            print("A browser window will open for you to log in.")
            flow = InstalledAppFlow.from_client_secrets_file( # type: ignore
                credentials_file, SCOPES)
            credentials = flow.run_local_server(port=0) # type: ignore
        
        # Save credentials for next time
        with open(token_file, 'wb') as token:
            pickle.dump(credentials, token)
        print("Credentials saved for future use.")
    
    # Build and return the YouTube API service
    youtube = build('youtube', 'v3', credentials=credentials)
    return youtube  # type: ignore[return-value]


def get_authenticated_service(config: Config) -> YouTubeResource:
    """
    Get authenticated YouTube service based on configuration.
    
    Args:
        config: Configuration dictionary with auth_method specified
        
    Returns:
        Authenticated YouTube API service
    """
    auth_method = config.get('auth_method', 'service_account')
    
    if auth_method == 'oauth':
        oauth_file = config.get('oauth_credentials_file') or 'oauth_credentials.json'
        token_file = config.get('oauth_token_file') or 'token.pickle'
        return get_youtube_service_oauth(oauth_file, token_file)
    elif auth_method == 'service_account':
        return get_youtube_service(config['service_account_file'])
    else:
        raise ValueError(f"Unknown auth_method: {auth_method}. Use 'service_account' or 'oauth'")


def load_config(config_file: str = 'config.jsonc') -> Config:
    """
    Load configuration from JSONC file (JSON with comments).
    
    Args:
        config_file: Path to configuration file
        
    Returns:
        Configuration dictionary
    """
    with open(config_file, 'r') as f:
        return jsonc.load(f)  # type: ignore[return-value]
