from fastapi import APIRouter, Request, Depends, HTTPException
from authlib.integrations.starlette_client import OAuth
from starlette.responses import RedirectResponse
from ..infrastructure.config_manager import config
import logging

logger = logging.getLogger("ArchAI.Auth")
router = APIRouter(prefix="/auth", tags=["Authentication"])

oauth = OAuth()

# Google OAuth Configuration
oauth.register(
    name='google',
    client_id=config.get_secret('google_client_id'),
    client_secret=config.get_secret('google_client_secret'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile https://www.googleapis.com/auth/drive.appdata'}
)

# GitHub OAuth Configuration
oauth.register(
    name='github',
    client_id=config.get_secret('github_client_id'),
    client_secret=config.get_secret('github_client_secret'),
    access_token_url='https://github.com/login/oauth/access_token',
    access_token_params=None,
    authorize_url='https://github.com/login/oauth/authorize',
    authorize_params=None,
    api_base_url='https://api.github.com/',
    client_kwargs={'scope': 'user:email'}
)

@router.get('/login/{provider}')
async def login(provider: str, request: Request):
    redirect_uri = request.url_for('auth_callback', provider=provider)
    if provider == 'google':
        return await oauth.google.authorize_redirect(request, redirect_uri)
    elif provider == 'github':
        return await oauth.github.authorize_redirect(request, redirect_uri)
    raise HTTPException(status_code=400, detail="Invalid provider")

@router.get('/callback/{provider}', name='auth_callback')
async def auth_callback(provider: str, request: Request):
    if provider == 'google':
        token = await oauth.google.authorize_access_token(request)
        user = token.get('userinfo')
    elif provider == 'github':
        token = await oauth.github.authorize_access_token(request)
        resp = await oauth.github.get('user', token=token)
        user = resp.json()
    
    # In a production environment, we would issue a JWT here.
    # For now, we'll store the token/user info for the backup service.
    logger.info(f"User {user.get('email') or user.get('login')} logged in via {provider}")
    
    # Redirect back to the dashboard with a success flag
    return RedirectResponse(url='/dashboard/?auth=success')

@router.get('/logout')
async def logout(request: Request):
    request.session.pop('user', None)
    return RedirectResponse(url='/')
