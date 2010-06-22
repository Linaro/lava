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

    The helper calls the provided function and takes care of any non-default
    arguments that were not explicitly provided by getting 'good' values from a
    helper object.

    Example:
    >>> def add(a, b): return a + b
    >>> class dummy_values:
    ...     a = 1
    ...     b = 2
    >>> add = CallHelper(add, dummy_values())

    In reality the code below calls add(dummy.a, dummy.b) dummy is the
    instance of dummy_values.
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
    arguments. This argument will not be obtained from the helper
    object.
    >>> inc = CallHelper(inc, inc_dummy())
    >>> inc()
    6

    This is same as using DEFAULT_VALUE
    >>> inc(increment=inc.DEFAULT_VALUE)
    6

    If you want to override this behaviour and force dummy values for
    default argument you can use special DUMMY_VALUE value.
    >>> inc(increment=inc.DUMMY_VALUE)
    7

    There are two special values you can use DEFAULT_VALUE and DUMMY_VALUE. Passing
    DEFAULT_VALUE simply instructs the helper not to provide a value from the
    defaults even if we can. Passing DUMMY_VALUE does the opposite. Having
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
    filled with dummies? Simple, use DUMMY_VALUE positional arguments.
    >>> add3(add3.DUMMY_VALUE, -2, add3.DUMMY_VALUE)
    2

    Another way of doing that is to use keyword arguments
    >>> add3(b=-2)
    2
    """
    DEFAULT_VALUE = object()
    DUMMY_VALUE = object()

    def __init__(self, func, dummy):
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
                # with a yet another fall-back to special DUMMY_VALUE value
                arg = self._args_with_defaults.get(arg_name, self.DUMMY_VALUE)
            # resolve the argument
            if arg is self.DEFAULT_VALUE:
                if arg_name not in self._args_with_defaults:
                    raise ValueError("You passed DEFAULT_VALUE argument to %s "
                            "which has no default value" % (arg_name,))
                arg = self._args_with_defaults[arg_name]
            elif arg is self.DUMMY_VALUE:
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
    a call_helper which will call the constructor (a rather tricky thing
    to do).

    All non-default values for the constructor will be fetched from a
    helper object. By default you can use a convention where a nested
    class called '_Dummy' contains all the properties you'd need to make
    instances.
    >>> class Person(object):
    ...     class _Dummy:
    ...         name = "Joe"
    ...     def __init__(self, name):
    ...         self.name = name
    >>> factory = ObjectFactory(Person)
    >>> person = factory()
    >>> person.name
    'Joe'

    As with CallHelper you can override dummy values by passing any
    positional or keyword arguments.
    >>> person = factory(name="Bob")
    >>> person.name
    'Bob'

    If you want you can store dummy values in separate class and pass it
    along to the ObjectFactory constructor.
    >>> class MyDummy:
    ...     name = "Alice"
    >>> factory = ObjectFactory(Person, MyDummy)
    >>> person = factory()
    >>> person.name
    'Alice'

    In addition the factory expoes the dummy values it is using via the
    `dummy' property. This can be useful in unit tests where you don't
    want to worry about the particular value but need to check if it can
    be stored, retrieved, etc.
    >>> name = factory.dummy.name
    >>> name
    'Alice'
    """
    def __init__(self, cls, dummy_cls=None):
        """
        Initialize ObjectFactory to create instances of class `cls'.
        If specified, dummy values for required arguments will come from
        instances of `dummy_cls'. Otherwise the class must have a
        '_Dummy' nested class that will be used instead.
        """
        if dummy_cls is None:
            if not hasattr(cls, '_Dummy'):
                raise ValueError("Class %s needs to have a nested class"
                        " called _Dummy" % (cls,))
            dummy_cls = cls._Dummy
        self._cls = cls
        self._dummy = dummy_cls()
        super(ObjectFactory, self).__init__(cls.__init__, self._dummy)
        # remove 'self' from argument list
        self._args = self._args[1:]

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
