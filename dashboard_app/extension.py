from lava_server.extension import LavaServerExtension


class DashboardExtension(LavaServerExtension):

    @property
    def app_name(self):
        return "dashboard_app"

    @property
    def name(self):
        return "Dashboard"

    @property
    def main_view_name(self):
        return "dashboard_app.views.bundle_stream_list"

    @property
    def description(self):
        return "Validation Dashboard"

    @property
    def version(self):
        import versiontools
        import dashboard_app 
        return versiontools.format_version(dashboard_app.__version__)

    def contribute_to_settings(self, settings_module):
        super(DashboardExtension, self).contribute_to_settings(settings_module)
        settings_module['INSTALLED_APPS'].extend([
            "linaro_django_pagination",
            "south",
        ])
        settings_module['MIDDLEWARE_CLASSES'].append(
            'linaro_django_pagination.middleware.PaginationMiddleware')

    def contribute_to_settings_ex(self, settings_module, settings_object):
        settings_module['DATAVIEW_DIRS'] = settings_object._settings.get(
            "DATAVIEW_DIRS", [])
        settings_module['DATAREPORT_DIRS'] = settings_object._settings.get(
            "DATAREPORT_DIRS", [])

        # Enable constrained dataview database if requested
        if settings_object._settings.get("use_dataview_database"):
            # Copy everything from the default database and append _dataview to user
            # name. The rest is out of scope (making sure it's actually setup
            # properly, having permissions to login, permissions to view proper data)
            settings_module['DATABASES']['dataview'] = dict(settings_module['DATABASES']['default'])
            settings_module['DATABASES']['dataview']['USER'] += "_dataview"

