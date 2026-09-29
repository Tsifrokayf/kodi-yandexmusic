"""OAuth: device-code login, token refresh, access token resolution."""
import requests

from yandex_music import Client
from yandex_music._client.device_auth import (
    _DEFAULT_CLIENT_ID,
    _DEFAULT_CLIENT_SECRET,
    _OAUTH_BASE_URL,
)
from yandex_music.exceptions import DeviceAuthError, YandexMusicError


class NotAuthorized(Exception):
    """User is not logged in or the session can no longer be used."""


class AuthError(Exception):
    """Login/refresh failed."""


def refresh_token(store):
    """Exchange refresh_token for a new access token. Returns new token data."""
    session = store.load()
    refresh = session.get('refresh_token')
    if not refresh:
        raise NotAuthorized('refresh token is missing')
    try:
        response = requests.post(
            _OAUTH_BASE_URL + '/token',
            data={
                'grant_type': 'refresh_token',
                'client_id': _DEFAULT_CLIENT_ID,
                'client_secret': _DEFAULT_CLIENT_SECRET,
                'refresh_token': refresh,
            },
            timeout=30,
        )
        payload = response.json()
    except Exception as error:
        raise AuthError('token refresh request failed: {0}'.format(error))
    if response.status_code != 200 or 'access_token' not in payload:
        description = payload.get('error_description') or payload.get('error') or payload
        raise AuthError('token refresh failed: {0}'.format(description))
    store.save(
        payload.get('access_token'),
        payload.get('refresh_token') or refresh,
        payload.get('expires_in'),
    )
    return payload


def get_access_token(store, manual_token=None):
    if manual_token:
        return manual_token
    if not store.has_token():
        raise NotAuthorized('not logged in')
    if store.expired():
        refresh_token(store)
    return store.load().get('access_token')


def device_login(store, show_code=None, should_cancel=None):
    """Blocking OAuth Device Flow.

    show_code(code) -> UI hook called with the yandex_music.DeviceCode.
    should_cancel() -> optional hook polled between token polls; truthy aborts login.
    Returns the OAuthToken. Raises AuthError on failure/cancel.
    """
    client = Client()

    def cb_show_code(code):
        if show_code is not None:
            show_code(code)

    def cb_should_cancel():
        if should_cancel is None:
            return False
        try:
            return bool(should_cancel())
        except Exception:
            return False

    try:
        token = client.device_auth(on_code=cb_show_code, should_cancel=cb_should_cancel)
    except DeviceAuthError as error:
        if cb_should_cancel():
            raise AuthError('cancelled')
        raise AuthError(str(error))
    except YandexMusicError as error:
        raise AuthError(str(error))

    store.save(token.access_token, token.refresh_token, token.expires_in)
    return token
