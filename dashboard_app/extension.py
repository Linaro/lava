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

    def contribute_to_settings(self, settings):
        super(DashboardExtension, self).contribute_to_settings(settings)
        settings['INSTALLED_APPS'].extend([
            "linaro_django_pagination",
            "south",
        ])
        settings['MIDDLEWARE_CLASSES'].append(
            'linaro_django_pagination.middleware.PaginationMiddleware')
        settings['RESTRUCTUREDTEXT_FILTER_SETTINGS'] = {
            "initial_header_level": 4}
        # TODO: Add dataview database support
