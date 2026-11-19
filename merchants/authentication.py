from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from merchants.models import ApiKey


class ApiKeyAuthentication(BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request):
        header = get_authorization_header(request).split()
        if not header:
            return None
        if len(header) != 2 or header[0].decode("latin-1") != self.keyword:
            raise AuthenticationFailed("Malformed Authorization header, expected 'Bearer <key>'.")

        raw_key = header[1].decode("latin-1")
        api_key = (
            ApiKey.objects.active()
            .select_related("merchant")
            .filter(key_hash=ApiKey.hash_key(raw_key))
            .first()
        )
        if api_key is None:
            raise AuthenticationFailed("Invalid API key.")
        return api_key.merchant, api_key

    def authenticate_header(self, request):
        # 401 with WWW-Authenticate instead of 403
        return self.keyword
