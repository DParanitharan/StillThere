from rest_framework.authentication import SessionAuthentication


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """SessionAuthentication without CSRF enforcement for SPA clients."""

    def enforce_csrf(self, request):
        return
