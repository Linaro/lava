"""
Patches for django bugs that affect this package
"""

class PatchDjangoTicket1476(object):
    """
    Patch for bug http://code.djangoproject.com/ticket/1476
    """

    @classmethod
    def apply_if_needed(patch):
        import django
        if django.VERSION[0:3] <= (1, 2, 4):
            patch.apply()

    @classmethod
    def apply(patch):
        from django.utils.decorators import method_decorator
        from django.views.decorators.csrf import csrf_protect

        @method_decorator(csrf_protect)
        def __call__(self, request, *args, **kwargs):
            """
            Main method that does all the hard work, conforming to the Django view
            interface.
            """
            if 'extra_context' in kwargs:
                self.extra_context.update(kwargs['extra_context'])
            current_step = self.determine_step(request, *args, **kwargs)
            self.parse_params(request, *args, **kwargs)

            # Sanity check.
            if current_step >= self.num_steps():
                raise Http404('Step %s does not exist' % current_step)

            # Process the current step. If it's valid, go to the next step or call
            # done(), depending on whether any steps remain.
            if request.method == 'POST':
                form = self.get_form(current_step, request.POST)
            else:
                form = self.get_form(current_step)

            if form.is_valid():
                # Validate all the forms. If any of them fail validation, that
                # must mean the validator relied on some other input, such as
                # an external Web site.

                # It is also possible that validation might fail under certain
                # attack situations: an attacker might be able to bypass previous
                # stages, and generate correct security hashes for all the
                # skipped stages by virtue of:
                #  1) having filled out an identical form which doesn't have the
                #     validation (and does something different at the end),
                #  2) or having filled out a previous version of the same form
                #     which had some validation missing,
                #  3) or previously having filled out the form when they had
                #     more privileges than they do now.
                #
                # Since the hashes only take into account values, and not other
                # other validation the form might do, we must re-do validation
                # now for security reasons.
                previous_form_list = [self.get_form(i, request.POST) for i in range(current_step)]

                for i, f in enumerate(previous_form_list):
                    if request.POST.get("hash_%d" % i, '') != self.security_hash(request, f):
                        return self.render_hash_failure(request, i)

                    if not f.is_valid():
                        return self.render_revalidation_failure(request, i, f)
                    else:
                        self.process_step(request, f, i)

                # Now progress to processing this step:
                self.process_step(request, form, current_step)
                next_step = current_step + 1


                if next_step == self.num_steps():
                    return self.done(request, previous_form_list + [form])
                else:
                    form = self.get_form(next_step)
                    self.step = current_step = next_step

            return self.render(form, request, current_step)

        from django.contrib.formtools.wizard import FormWizard
        FormWizard.__call__ = __call__


class PatchDjangoTicket15155(object):
    """
    Patch for bug http://code.djangoproject.com/ticket/15155
    """

    PROPER_FORMAT = r'(?<!%)%s'

    @classmethod
    def apply_if_needed(patch):
        from django.db.backends.sqlite3 import base
        if base.FORMAT_QMARK_REGEX != patch.PROPER_FORMAT:
            patch.apply()

    @classmethod
    def apply(cls):
        from django.db.backends.sqlite3 import base
        import re
        base.FORMAT_QMARK_REGEX = re.compile(cls.PROPER_FORMAT)


def patch():
    PatchDjangoTicket1476.apply_if_needed()
    PatchDjangoTicket15155.apply_if_needed()
