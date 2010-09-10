"""
Module with RegistryMeta and RegistryBase 
"""

class RegistryMeta(type):
    """
    Meta class for handling automatic registration of implementing
    classes. Allows to query for all sub-classes of any class in the
    inheritance chain.

    Since people don't like to use meta-classes directly there is a
    class with convenience API called RegistryBase.
    """

    def __new__(mcls, name, bases, namespace):
        cls = super(RegistryMeta, mcls).__new__(mcls, name, bases, namespace)
        cls._subclasses = []
        for base_cls in bases:
            if hasattr(base_cls, '_subclasses'):
                base_cls._subclasses.append(cls)
        return cls


class RegistryBase(object):
    """
    Convenience class for using RegistryMeta meta-class.

    All sub-classes of this class gain two methods:
        get_direct_subclasses()
        get_subclasses()
    """
    __metaclass__ = RegistryMeta

    @classmethod
    def get_direct_subclasses(cls):
        """
        Return all direct subclasses of this class

        Example:
        >>> class A(RegistryBase): pass
        >>> class B(A): pass
        >>> A.get_direct_subclasses()
        [<class 'launch_control.utils.registry.B'>]
        """
        return cls._subclasses

    @classmethod
    def get_subclasses(cls):
        """
        Return all subclasses of this class

        Example:
        >>> class A(RegistryBase): pass
        >>> class B(A): pass
        >>> class C(B): pass
        >>> A.get_subclasses()
        [<class 'launch_control.utils.registry.B'>, <class 'launch_control.utils.registry.C'>]
        """
        result = list(cls._subclasses)
        for scls in cls._subclasses:
            result.extend(scls.get_subclasses())
        return result
