from django.utils.translation import ungettext_lazy


def help_max_length(max_length):
    return ungettext_lazy(
        u"Maximum length: {0} character",
        u"Maximum length: {0} characters",
        max_length).format(max_length)
