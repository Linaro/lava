def action(func):
    """
    Decorator marking the function as an action
    """
    func.is_action = True
    return func
