from dashboard_app.models import ImageHealth


def dashboard_globals(request):
    return {
        "dashboard": {
            "interesting_images": [
                ImageHealth('nano', 'panda'),
                ImageHealth('nano', 'omap3'),
                ImageHealth('nano', 'lt-panda'),
                ImageHealth('developer', 'panda'),
                ImageHealth('developer', 'omap3'),
                ImageHealth('developer', 'lt-panda'),
                ImageHealth('alip', 'panda'),
                ImageHealth('alip', 'omap3'),
                ImageHealth('alip', 'lt-panda'),
                ImageHealth('alip', 'lt-panda-x11-base-natty'),
                ImageHealth('ubuntu-desktop', 'panda'),
                ImageHealth('ubuntu-desktop', 'omap3'),
                ImageHealth('ubuntu-desktop', 'lt-panda'),
                ImageHealth('ubuntu-desktop', 'lt-panda-x11-base-natty'),
            ]
        }
    }
