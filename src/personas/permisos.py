from django.contrib.auth.decorators import user_passes_test

# US-08: el panel lo abre el rol de administrador, no solo `is_staff`. Si no, una
# cuenta a la que se le da el rol desde la pestaña Usuarios no entraría.
solo_administradores = user_passes_test(
    lambda usuario: usuario.is_authenticated and usuario.es_administrador, login_url="login_gestion",
)
