"""
Miscellaneous utilities.
"""

import types


class Stack:
    """Utility class implementing a stack."""

    def __init__(self):
        self.items = []

    def clone(self):
        s = self.__class__()
        for item in self.items:
            try:
                item = item.clone()
            except AttributeError:
                pass
            s.push(item)
        return s

    def push(self, item):
        self.items.append(item)

    def pop(self):
        return self.items.pop()

    def top(self, position=0):
        """'position' is 0 for the top of the stack, 1 for the item below,
        and so on.  It must not be negative."""
        return self.items[~position]

    def depth(self):
        return len(self.items)

    def empty(self):
        return not self.items


class InitializedClass(type):
    """A meta-class that allows a class to initialize itself (or its
    subclasses) by calling __initclass__() as a class method."""
    def __init__(self, name, bases, dict):
        super(InitializedClass, self).__init__(name, bases, dict)
        if hasattr(self, '__initclass__'):
            raw = dict.get('__initclass__')
            if isinstance(raw, types.FunctionType):
                self.__initclass__ = classmethod(raw)
            self.__initclass__()


class ThreadLocals:
    """Thread-local storage."""

    def __init__(self):
        self.executioncontext = None

# XXX no thread support yet, so this is easy :-)
_locals = ThreadLocals()
def getthreadlocals():
    return _locals
