#!/usr/bin/python
"""
Small helper module that aids in writing unit tests. It allows to
construct objects or call functions without any arguments by looking up
the required arguments from a helper object or from the class itself.
"""


class CallHelper(object):
    """
    Helper for making easy-to-call functions that would otherwise
    require multiple (possibly complex) arguments to call correctly.

    The helper calls the provided function and takes care of any
    arguments that were not explicitly provided by getting 'good' values
    from a helper object.

    Example:
    >>> def add(a, b): return a + b
    >>> class dummy_values:
    ...     a = 1
    ...     b = 2
    >>> add = CallHelper(add, dummy_values())

    In reality the code below calls add(dummy.a, dummy.b)
    dummy is the instance of dummy_values
    >>> add()
    3

    You can still call the function as it was the original
    >>> add(5, -1)
    4

    Let's try something more complicated.
    >>> def inc(value, increment=1):
    ...     return value + increment
    >>> class inc_dummy(object):
    ...     value = 5
    ...     increment = 2

    Here the function already has a default value for one of the
    arguments.  This example is naive but real life scenarios might use
    None as the default to construct some real value internally.  We'd
    like to be able to say
        "call inc but use the default value for increment".
    Here is how we do it:
    >>> inc = CallHelper(inc, inc_dummy())
    >>> inc(increment=inc.DEFAULT)
    6

    There are two special values you can use DEFAULT and DUMMY. Passing
    DEFAULT simply instructs the helper not to provide a value from the
    defaults even if we can. Passing DUMMY does the opposite. Having
    both makes sense when you consider positional arguments.
    >>> def add3(a, b, c):
    ...     return a + b + c
    >>> class add3_dummy(object):
    ...     a = 1
    ...     b = 2
    ...     c = 3
    >>> add3 = CallHelper(add3, add3_dummy)
    >>> add3()
    6

    What if I want to specify the middle argument while the rest gets
    filled with dummies? Simple, use DUMMY positional arguments.
    >>> add3(add3.DUMMY, -2, add3.DUMMY)
    2

    Another way of doing that is to use keyword arguments
    >>> add3(b=-2)
    2
    """
    DEFAULT = object()
    DUMMY = object()

    def __init__(self, func, dummy, ignore_self=False):
        """
        Initialize call helper to wrap function `func' and supply values
        from properties of `dummy' object.
        """
        if func.func_code.co_flags & 0x4:
            raise ValueError("Functions with variable argument lists "
                    "are not supported")
        if func.func_code.co_flags & 0x8:
            raise ValueError("Functions with variable keyword arguments "
                    "are not supported")
        self._func = func
        self._dummy = dummy
        self._args = func.func_code.co_varnames[:func.func_code.co_argcount]
        self._args_with_defaults = dict(
                zip(self._args[-len(func.func_defaults):] if
                    func.func_defaults else (), func.func_defaults or ()))
        if ignore_self:
            self._args = self._args[1:]

    def _get_dummy_for(self, arg_name):
        """ Get dummy value for given argument """
        try:
            return getattr(self._dummy, arg_name)
        except AttributeError:
            raise ValueError("Dummy %s does not have dummy value for %s" % (
                self._dummy, arg_name))

    def _fill_args(self, *args, **kwargs):
        a_out = []
        used_kwargs = set()
        # Walk through all arguments of the original function. Ff the
        # argument is present in `args' then use it. If we run out of
        # positional arguments look for keyword arguments with the same
        # name.
        for i, arg_name in enumerate(self._args):
            # find the argument
            if i < len(args):
                # positional arguments get passed as-is
                arg = args[i]
            elif arg_name in kwargs:
                # keyword arguments take over
                arg = kwargs[arg_name]
                # also remember we got it from a keyword argument
                used_kwargs.add(arg_name)
            else:
                # otherwise the function defaults kick in
                # with a yet another fall-back to special DUMMY value
                arg = self._args_with_defaults.get(arg_name, self.DUMMY)
            # resolve the argument
            if arg is self.DEFAULT:
                if arg_name not in self._args_with_defaults:
                    import sys
                    print >>sys.stderr, "args:", self._args
                    print >>sys.stderr, "args with defaults:", \
                            self._args_with_defaults
                    raise ValueError("You passed DEFAULT argument to %s "
                            "which has no default value" % (arg_name,))
                arg = self._args_with_defaults[arg_name]
            elif arg is self.DUMMY:
                arg = self._get_dummy_for(arg_name)
            # store the argument
            a_out.append(arg)
        # Now check if we have too many / not enough arguments
        if len(a_out) != len(self._args):
            raise TypeError("%s takes exactly %d argument, %d given" % (
                self._func, len(self._args), len(args)))
        # Now check keyword arguments
        for arg_name in kwargs:
            # Check for duplicate definitions of positional/keyword
            # arguments
            if arg_name in self._args and arg_name not in used_kwargs:
                raise TypeError("%s() got multiple values for keyword "
                        "argument '%s'" % (self._func.func_name, arg_name))

            # Look for stray keyword arguments
            if arg_name not in self._args:
                raise TypeError("%s() got an unexpected keyword "
                        "argument '%s'" % (self._func.func_name, arg_name))
        # We're done
        return a_out

    def __call__(self, *args, **kwargs):
        """
        Call the original function passing dummy values for all
        arguments """
        a_out = self._fill_args(*args, **kwargs)
        # We're done, let's call the function now! Note that we don't
        # use kw_args as we resolve keyword arguments ourselves, this
        # would be only useful for functions that support *args and
        # **kwargs style variable arguments which CallHelper does not
        # yet support.
        return self._func(*a_out)

class ObjectFactory(CallHelper):
    """
    Helper class for making objects

    This class allows to easily construct a dummy instances by building
    a call_helper which will look for special dummy values inside the
    class. You can override dummy values by passing any positional or
    keyword arguments.
    >>> class Person(object):
    ...     class _Dummy:
    ...         name = "Joe"
    ...     def __init__(self, name):
    ...         self.name = name
    >>> factory = ObjectFactory(Person)
    >>> person = factory()
    >>> person.name
    'Joe'
    >>> person = factory(name="Bob")
    >>> person.name
    'Bob'

    In addition the factory expoes the dummy values it is using via the
    `dummy' property. This can be useful in unit tests where you don't
    want to worry about the particular value but need to check if it can
    be stored, retrieved, etc.
    >>> name = factory.dummy.name
    >>> person = factory(name)
    >>> person.name == name
    True
    """
    def __init__(self, cls):
        if not hasattr(cls, '_Dummy'):
            raise ValueError("Class %s needs to have a nested class"
                    " called _Dummy" % (cls,))
        self._cls = cls
        self._dummy = cls._Dummy()
        super(ObjectFactory, self).__init__(
                cls.__init__, self.dummy, ignore_self=True)

    @property
    def dummy(self):
        """ Helper property for read-only access to dummy values """
        return self._dummy

    def __call__(self, *args, **kwargs):
        """ Construct new object instance """
        a_out = self._fill_args(*args, **kwargs)
        return self._cls(*a_out)

if __name__ == '__main__':
    import doctest
    doctest.testmod()
