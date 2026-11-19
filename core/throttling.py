from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle


class MerchantRateThrottle(SimpleRateThrottle):
    scope = "merchant"

    def get_cache_key(self, request, view):
        if request.user is None or not getattr(request.user, "is_authenticated", False):
            return None
        return self.cache_format % {"scope": self.scope, "ident": request.user.pk}


class SignupRateThrottle(AnonRateThrottle):
    scope = "signup"
