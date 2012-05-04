from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from django.template import RequestContext, loader
from markdown import markdown


@csrf_exempt
def preview_markdown(request):
    """
    Convert markdown to HTML
    """
    markup = request.POST.get("data", "")
    template_name = "lava_markitup/preview.html"
    t = loader.get_template(template_name)
    c = RequestContext(request, {
        'markup': markdown(markup, safe_mode="escape")})
    return HttpResponse(t.render(c))
