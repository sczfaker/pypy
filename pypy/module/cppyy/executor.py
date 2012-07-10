import sys

from pypy.interpreter.error import OperationError

from pypy.rpython.lltypesystem import rffi, lltype
from pypy.rlib import libffi, clibffi

from pypy.module._rawffi.interp_rawffi import unpack_simple_shape
from pypy.module._rawffi.array import W_Array

from pypy.module.cppyy import helper, capi

# Executor objects are used to dispatch C++ methods. They are defined by their
# return type only: arguments are converted by Converter objects, and Executors
# only deal with arrays of memory that are either passed to a stub or libffi.
# No argument checking or conversions are done.
#
# If a libffi function is not implemented, FastCallNotPossible is raised. If a
# stub function is missing (e.g. if no reflection info is available for the
# return type), an app-level TypeError is raised.
#
# Executor instances are created by get_executor(<return type name>), see
# below. The name given should be qualified in case there is a specialised,
# exact match for the qualified type.


NULL = lltype.nullptr(clibffi.FFI_TYPE_P.TO)

class FunctionExecutor(object):
    _immutable_ = True
    libffitype = NULL

    def __init__(self, space, extra):
        pass

    def execute(self, space, cppmethod, cppthis, num_args, args):
        raise OperationError(space.w_TypeError,
                             space.wrap('return type not available or supported'))

    def execute_libffi(self, space, libffifunc, argchain):
        from pypy.module.cppyy.interp_cppyy import FastCallNotPossible
        raise FastCallNotPossible


class PtrTypeExecutor(FunctionExecutor):
    _immutable_ = True
    typecode = 'P'

    def execute(self, space, cppmethod, cppthis, num_args, args):
        if hasattr(space, "fake"):
            raise NotImplementedError
        lresult = capi.c_call_l(cppmethod, cppthis, num_args, args)
        address = rffi.cast(rffi.ULONG, lresult)
        arr = space.interp_w(W_Array, unpack_simple_shape(space, space.wrap(self.typecode)))
        return arr.fromaddress(space, address, sys.maxint)


class VoidExecutor(FunctionExecutor):
    _immutable_ = True
    libffitype = libffi.types.void

    def execute(self, space, cppmethod, cppthis, num_args, args):
        capi.c_call_v(cppmethod, cppthis, num_args, args)
        return space.w_None

    def execute_libffi(self, space, libffifunc, argchain):
        libffifunc.call(argchain, lltype.Void)
        return space.w_None


class NumericExecutorMixin(object):
    _mixin_ = True
    _immutable_ = True

    def _wrap_result(self, space, result):
        return space.wrap(rffi.cast(self.c_type, result))

    def execute(self, space, cppmethod, cppthis, num_args, args):
        result = self.c_stubcall(cppmethod, cppthis, num_args, args)
        return self._wrap_result(space, result)

    def execute_libffi(self, space, libffifunc, argchain):
        result = libffifunc.call(argchain, self.c_type)
        return space.wrap(result)


class BoolExecutor(FunctionExecutor):
    _immutable_ = True
    libffitype  = libffi.types.schar

    def execute(self, space, cppmethod, cppthis, num_args, args):
        result = capi.c_call_b(cppmethod, cppthis, num_args, args)
        return space.wrap(result)

    def execute_libffi(self, space, libffifunc, argchain):
        result = libffifunc.call(argchain, rffi.CHAR)
        return space.wrap(bool(ord(result)))

class ConstIntRefExecutor(FunctionExecutor):
    _immutable_ = True
    libffitype = libffi.types.pointer

    def _wrap_result(self, space, result):
        intptr = rffi.cast(rffi.INTP, result)
        return space.wrap(intptr[0])

    def execute(self, space, cppmethod, cppthis, num_args, args):
        result = capi.c_call_r(cppmethod, cppthis, num_args, args)
        return self._wrap_result(space, result)

    def execute_libffi(self, space, libffifunc, argchain):
        result = libffifunc.call(argchain, rffi.INTP)
        return space.wrap(result[0])

class IntRefExecutor(FunctionExecutor):
    _immutable_ = True
    libffitype = libffi.types.pointer

    def __init__(self, space, extra):
        FunctionExecutor.__init__(self, space, extra)
        self.do_assign = False
        self.item = rffi.cast(rffi.INT, 0)

    def set_item(self, space, w_item):
        self.item = rffi.cast(rffi.INT, space.c_int_w(w_item))
        self.do_assign = True

    def _wrap_result(self, space, intptr):
        if self.do_assign:
            intptr[0] = self.item
        return space.wrap(intptr[0])    # all paths, for rtyper

    def execute(self, space, cppmethod, cppthis, num_args, args):
        result = rffi.cast(rffi.INTP, capi.c_call_r(cppmethod, cppthis, num_args, args))
        return self._wrap_result(space, result)

    def execute_libffi(self, space, libffifunc, argchain):
        result = libffifunc.call(argchain, rffi.INTP)
        return self._wrap_result(space, result)

class ConstLongRefExecutor(ConstIntRefExecutor):
    _immutable_ = True
    libffitype = libffi.types.pointer

    def _wrap_result(self, space, result):
        longptr = rffi.cast(rffi.LONGP, result)
        return space.wrap(longptr[0])

    def execute_libffi(self, space, libffifunc, argchain):
        result = libffifunc.call(argchain, rffi.LONGP)
        return space.wrap(result[0])

class FloatExecutor(FunctionExecutor):
    _immutable_ = True
    libffitype = libffi.types.float

    def execute(self, space, cppmethod, cppthis, num_args, args):
        result = capi.c_call_f(cppmethod, cppthis, num_args, args)
        return space.wrap(float(result))

    def execute_libffi(self, space, libffifunc, argchain):
        result = libffifunc.call(argchain, rffi.FLOAT)
        return space.wrap(float(result))

class DoubleRefExecutor(FunctionExecutor):
    _immutable_ = True
    libffitype = libffi.types.pointer

    def __init__(self, space, extra):
        FunctionExecutor.__init__(self, space, extra)
        self.do_assign = False
        self.item = rffi.cast(rffi.DOUBLE, 0)

    def set_item(self, space, w_item):
        self.item = rffi.cast(rffi.DOUBLE, space.float_w(w_item))
        self.do_assign = True

    def _wrap_result(self, space, dptr):
        if self.do_assign:
            dptr[0] = self.item
        return space.wrap(dptr[0])      # all paths, for rtyper

    def execute(self, space, cppmethod, cppthis, num_args, args):
        result = rffi.cast(rffi.DOUBLEP, capi.c_call_r(cppmethod, cppthis, num_args, args))
        return self._wrap_result(space, result)

    def execute_libffi(self, space, libffifunc, argchain):
        result = libffifunc.call(argchain, rffi.DOUBLEP)
        return self._wrap_result(space, result)


class CStringExecutor(FunctionExecutor):
    _immutable_ = True

    def execute(self, space, cppmethod, cppthis, num_args, args):
        lresult = capi.c_call_l(cppmethod, cppthis, num_args, args)
        ccpresult = rffi.cast(rffi.CCHARP, lresult)
        result = rffi.charp2str(ccpresult)  # TODO: make it a choice to free
        return space.wrap(result)


class ConstructorExecutor(VoidExecutor):
    _immutable_ = True

    def execute(self, space, cppmethod, cppthis, num_args, args):
        capi.c_constructor(cppmethod, cppthis, num_args, args)
        return space.w_None


class InstancePtrExecutor(FunctionExecutor):
    _immutable_ = True
    libffitype = libffi.types.pointer

    def __init__(self, space, cppclass):
        FunctionExecutor.__init__(self, space, cppclass)
        self.cppclass = cppclass

    def execute(self, space, cppmethod, cppthis, num_args, args):
        from pypy.module.cppyy import interp_cppyy
        long_result = capi.c_call_l(cppmethod, cppthis, num_args, args)
        ptr_result = rffi.cast(capi.C_OBJECT, long_result)
        return interp_cppyy.wrap_cppobject(
            space, space.w_None, self.cppclass, ptr_result, isref=False, python_owns=False)

    def execute_libffi(self, space, libffifunc, argchain):
        from pypy.module.cppyy import interp_cppyy
        ptr_result = rffi.cast(capi.C_OBJECT, libffifunc.call(argchain, rffi.VOIDP))
        return interp_cppyy.wrap_cppobject(
            space, space.w_None, self.cppclass, ptr_result, isref=False, python_owns=False)

class InstancePtrPtrExecutor(InstancePtrExecutor):
    _immutable_ = True

    def execute(self, space, cppmethod, cppthis, num_args, args):
        from pypy.module.cppyy import interp_cppyy
        voidp_result = capi.c_call_r(cppmethod, cppthis, num_args, args)
        ref_address = rffi.cast(rffi.VOIDPP, voidp_result)
        ptr_result = rffi.cast(capi.C_OBJECT, ref_address[0])
        return interp_cppyy.wrap_cppobject(
            space, space.w_None, self.cppclass, ptr_result, isref=False, python_owns=False)

    def execute_libffi(self, space, libffifunc, argchain):
        from pypy.module.cppyy.interp_cppyy import FastCallNotPossible
        raise FastCallNotPossible

class InstanceExecutor(InstancePtrExecutor):
    _immutable_ = True

    def execute(self, space, cppmethod, cppthis, num_args, args):
        from pypy.module.cppyy import interp_cppyy
        long_result = capi.c_call_o(cppmethod, cppthis, num_args, args, self.cppclass)
        ptr_result = rffi.cast(capi.C_OBJECT, long_result)
        return interp_cppyy.wrap_cppobject(
            space, space.w_None, self.cppclass, ptr_result, isref=False, python_owns=True)

    def execute_libffi(self, space, libffifunc, argchain):
        from pypy.module.cppyy.interp_cppyy import FastCallNotPossible
        raise FastCallNotPossible


class StdStringExecutor(InstancePtrExecutor):
    _immutable_ = True

    def execute(self, space, cppmethod, cppthis, num_args, args):
        charp_result = capi.c_call_s(cppmethod, cppthis, num_args, args)
        return space.wrap(capi.charp2str_free(charp_result))

    def execute_libffi(self, space, libffifunc, argchain):
        from pypy.module.cppyy.interp_cppyy import FastCallNotPossible
        raise FastCallNotPossible


class PyObjectExecutor(PtrTypeExecutor):
    _immutable_ = True

    def wrap_result(self, space, lresult):
        space.getbuiltinmodule("cpyext")
        from pypy.module.cpyext.pyobject import PyObject, from_ref, make_ref, Py_DecRef
        result = rffi.cast(PyObject, lresult)
        w_obj = from_ref(space, result)
        if result:
            Py_DecRef(space, result)
        return w_obj

    def execute(self, space, cppmethod, cppthis, num_args, args):
        if hasattr(space, "fake"):
            raise NotImplementedError
        lresult = capi.c_call_l(cppmethod, cppthis, num_args, args)
        return self.wrap_result(space, lresult)

    def execute_libffi(self, space, libffifunc, argchain):
        if hasattr(space, "fake"):
            raise NotImplementedError
        lresult = libffifunc.call(argchain, rffi.LONG)
        return self.wrap_result(space, lresult)


_executors = {}
def get_executor(space, name):
    # Matching of 'name' to an executor factory goes through up to four levels:
    #   1) full, qualified match
    #   2) drop '&': by-ref is pretty much the same as by-value, python-wise
    #   3) types/classes, either by ref/ptr or by value
    #   4) additional special cases
    #
    # If all fails, a default is used, which can be ignored at least until use.

    name = capi.c_resolve_name(name)

    #   1) full, qualified match
    try:
        return _executors[name](space, None)
    except KeyError:
        pass

    compound = helper.compound(name)
    clean_name = capi.c_resolve_name(helper.clean_type(name))

    #   1a) clean lookup
    try:
        return _executors[clean_name+compound](space, None)
    except KeyError:
        pass

    #   2) drop '&': by-ref is pretty much the same as by-value, python-wise
    if compound and compound[len(compound)-1] == "&":
        # TODO: this does not actually work with Reflex (?)
        try:
            return _executors[clean_name](space, None)
        except KeyError:
            pass

    #   3) types/classes, either by ref/ptr or by value
    from pypy.module.cppyy import interp_cppyy
    cppclass = interp_cppyy.scope_byname(space, clean_name)
    if cppclass:
        # type check for the benefit of the annotator
        from pypy.module.cppyy.interp_cppyy import W_CPPClass
        cppclass = space.interp_w(W_CPPClass, cppclass, can_be_None=False)
        if compound == "":
            return InstanceExecutor(space, cppclass)
        elif compound == "*" or compound == "&":
            return InstancePtrExecutor(space, cppclass)
        elif compound == "**" or compound == "*&":
            return InstancePtrPtrExecutor(space, cppclass)
    elif capi.c_is_enum(clean_name):
        return _executors['unsigned int'](space, None)

    # 4) additional special cases
    # ... none for now

    # currently used until proper lazy instantiation available in interp_cppyy
    return FunctionExecutor(space, None)
 

_executors["void"]                = VoidExecutor
_executors["void*"]               = PtrTypeExecutor
_executors["bool"]                = BoolExecutor
_executors["const char*"]         = CStringExecutor
_executors["const int&"]          = ConstIntRefExecutor
_executors["int&"]                = IntRefExecutor
_executors["float"]               = FloatExecutor
_executors["double&"]             = DoubleRefExecutor

_executors["constructor"]         = ConstructorExecutor

# special cases (note: CINT backend requires the simple name 'string')
_executors["std::basic_string<char>"]        = StdStringExecutor

_executors["PyObject*"]           = PyObjectExecutor

# add basic (builtin) executors
def _build_basic_executors():
    "NOT_RPYTHON"
    type_info = (
        (rffi.CHAR,       libffi.types.schar,   capi.c_call_c,   ("char", "unsigned char")),
        (rffi.SHORT,      libffi.types.sshort,  capi.c_call_h,   ("short", "short int", "unsigned short", "unsigned short int")),
        (rffi.INT,        libffi.types.sint,    capi.c_call_i,   ("int",)),
        (rffi.UINT,       libffi.types.uint,    capi.c_call_l,   ("unsigned", "unsigned int")),
        (rffi.LONG,       libffi.types.slong,   capi.c_call_l,   ("long", "long int")),
        (rffi.ULONG,      libffi.types.ulong,   capi.c_call_l,   ("unsigned long", "unsigned long int")),
        (rffi.LONGLONG,   libffi.types.sint64,  capi.c_call_ll,  ("long long", "long long int")),
        (rffi.ULONGLONG,  libffi.types.uint64,  capi.c_call_ll,  ("unsigned long long", "unsigned long long int")),
        (rffi.DOUBLE,     libffi.types.double,  capi.c_call_d,   ("double",))
    )

    for t_rffi, t_ffi, stub, names in type_info:
        class BasicExecutor(NumericExecutorMixin, FunctionExecutor):
            _immutable_ = True
            libffitype  = t_ffi
            c_type      = t_rffi
            c_stubcall  = staticmethod(stub)
        for name in names:
            _executors[name] = BasicExecutor
_build_basic_executors()

# add the set of aliased names
def _add_aliased_executors():
    "NOT_RPYTHON"
    alias_info = (
        ("const char*",                     ("char*",)),
        ("std::basic_string<char>",         ("string",)),
        ("PyObject*",                       ("_object*",)),
    )

    for info in alias_info:
        for name in info[1]:
            _executors[name] = _executors[info[0]]
_add_aliased_executors()

# create the pointer executors; all real work is in the PtrTypeExecutor, since
# all pointer types are of the same size
def _build_ptr_executors():
    "NOT_RPYTHON"
    ptr_info = (
        ('b', ("bool",)),     # really unsigned char, but this works ...
        ('h', ("short int", "short")),
        ('H', ("unsigned short int", "unsigned short")),
        ('i', ("int",)),
        ('I', ("unsigned int", "unsigned")),
        ('l', ("long int", "long")),
        ('L', ("unsigned long int", "unsigned long")),
        ('f', ("float",)),
        ('d', ("double",)),
    )

    for info in ptr_info:
        class PtrExecutor(PtrTypeExecutor):
            _immutable_ = True
            typecode = info[0]
        for name in info[1]:
            _executors[name+'*'] = PtrExecutor
_build_ptr_executors()
