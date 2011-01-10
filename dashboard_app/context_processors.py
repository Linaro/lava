def project_version(request):
    from dashboard_app import __version__
    return {'project_version': __version__}
