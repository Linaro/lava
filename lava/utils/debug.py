
def debug_obj(obj):
    retval = ''
    for attr in dir(obj):
        if hasattr(obj, attr):
            retval += ("%s = %s\n" % (attr, getattr(obj, attr)))
    return retval
