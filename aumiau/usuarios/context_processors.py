def acesso_google(request):
    from .google import google_configurado
    return {'google_configurado': google_configurado()}
