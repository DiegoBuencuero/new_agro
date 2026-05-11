from django.shortcuts import redirect

URLS_EXENTAS = (
    "/login/",
    "/registro/",
    "/cuenta-suspendida/",
    "/accounts/",
    "/admin/",
    "/static/",
    "/media/",
    "/i18n/",
)


class PerfilActivoMiddleware:
    """
    Verifica que el usuario autenticado tenga profile.status == 'A'.
    Si está suspendido ('S') o pendiente ('N') redirige a cuenta_suspendida.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not request.user.is_superuser:
            path = request.path
            if not any(path.startswith(url) for url in URLS_EXENTAS):
                try:
                    if request.user.profile.status != "A":
                        return redirect("cuenta_suspendida")
                except Exception:
                    pass

        return self.get_response(request)
