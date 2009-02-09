
""" Tests of libffi wrappers and dl* friends
"""

from pypy.rpython.test.test_llinterp import interpret
from pypy.translator.c.test.test_genc import compile
from pypy.rlib.libffi import *
from pypy.rlib.objectmodel import keepalive_until_here
from pypy.rpython.lltypesystem.ll2ctypes import ALLOCATED
from pypy.rpython.lltypesystem import rffi, lltype
import os, sys
import py
import time

def setup_module(mod):
    for name in type_names:
        # XXX force this to be seen by ll2ctypes
        # so that ALLOCATED.clear() clears it
        ffistruct = globals()[name]
        rffi.cast(rffi.VOIDP, ffistruct)

class TestDLOperations:
    def setup_method(self, meth):
        ALLOCATED.clear()

    def test_dlopen(self):
        py.test.raises(OSError, "dlopen(rffi.str2charp('xxxxxxxxxxxx'))")
        assert dlopen(rffi.str2charp(libc_name))
        
    def get_libc(self):
        return CDLL(libc_name)
    
    def get_libm(self):
        if sys.platform == 'win32':
            return CDLL('msvcrt.dll')
        elif sys.platform == "darwin":
            return CDLL('libm.dylib')
        else:
            return CDLL('libm.so')
    
    def test_library_open(self):
        lib = self.get_libc()
        del lib
        assert not ALLOCATED

    def test_library_get_func(self):
        lib = self.get_libc()
        ptr = lib.getpointer('time', [], ffi_type_void)
        py.test.raises(KeyError, lib.getpointer, 'xxxxxxxxxxxxxxx', [], ffi_type_void)
        del ptr
        del lib
        assert not ALLOCATED

    def test_library_func_call(self):
        lib = self.get_libc()
        ptr = lib.getpointer('rand', [], ffi_type_sint)
        zeroes = 0
        first = ptr.call(rffi.INT)
        for i in range(100):
            res = ptr.call(rffi.INT)
            if res == first:
                zeroes += 1
        assert zeroes < 90
        # not very hard check, but something :]
        del ptr
        del lib
        assert not ALLOCATED

    def test_call_args(self):
        libm = self.get_libm()
        pow = libm.getpointer('pow', [ffi_type_double, ffi_type_double],
                              ffi_type_double)
        pow.push_arg(2.0)
        pow.push_arg(2.0)
        res = pow.call(rffi.DOUBLE)
        assert res == 4.0
        pow.push_arg(3.0)
        pow.push_arg(3.0)
        res = pow.call(rffi.DOUBLE)
        assert res == 27.0
        del pow
        del libm
        assert not ALLOCATED

    def test_wrong_args(self):
        libc = self.get_libc()
        # XXX assume time_t is long
        ulong = cast_type_to_ffitype(rffi.ULONG)
        ctime = libc.getpointer('time', [ffi_type_pointer], ulong)
        x = lltype.malloc(lltype.GcStruct('xxx'))
        y = lltype.malloc(lltype.GcArray(rffi.LONG), 3)
        z = lltype.malloc(lltype.Array(rffi.LONG), 4, flavor='raw')
        py.test.raises(ValueError, "ctime.push_arg(x)")
        py.test.raises(ValueError, "ctime.push_arg(y)")
        py.test.raises(ValueError, "ctime.push_arg(z)")
        del ctime
        del libc
        lltype.free(z, flavor='raw')
        # allocation check makes no sense, since we've got GcStructs around

    def test_unichar(self):
        from pypy.rlib.runicode import MAXUNICODE
        wchar = cast_type_to_ffitype(lltype.UniChar)
        if MAXUNICODE > 65535:
            assert wchar is ffi_type_uint32
        else:
            assert wchar is ffi_type_uint16

    def test_call_time(self):
        libc = self.get_libc()
        # XXX assume time_t is long
        ulong = cast_type_to_ffitype(rffi.ULONG)
        ctime = libc.getpointer('time', [ffi_type_pointer], ulong)
        ctime.push_arg(lltype.nullptr(rffi.CArray(rffi.LONG)))
        t0 = ctime.call(rffi.LONG)
        time.sleep(2)
        ctime.push_arg(lltype.nullptr(rffi.CArray(rffi.LONG)))
        t1 = ctime.call(rffi.LONG)
        assert t1 > t0
        l_t = lltype.malloc(rffi.CArray(rffi.LONG), 1, flavor='raw')
        ctime.push_arg(l_t)
        t1 = ctime.call(rffi.LONG)
        assert l_t[0] == t1
        lltype.free(l_t, flavor='raw')
        del ctime
        del libc
        assert not ALLOCATED

    def test_closure_heap(self):
        ch = ClosureHeap()

        assert not ch.free_list
        a = ch.alloc()
        assert ch.free_list        
        b = ch.alloc()
        
        chunks = [a, b]
        p = ch.free_list
        while p:
            chunks.append(p)
            p = rffi.cast(rffi.VOIDPP, p)[0]
        closure_size = rffi.sizeof(FFI_CLOSUREP.TO)
        assert len(chunks) == CHUNK//closure_size
        for i in range(len(chunks) -1 ):
            s = rffi.cast(rffi.UINT, chunks[i+1])
            e = rffi.cast(rffi.UINT, chunks[i])
            assert (e-s) >= rffi.sizeof(FFI_CLOSUREP.TO)

        ch.free(a)
        assert ch.free_list == rffi.cast(rffi.VOIDP, a)
        snd = rffi.cast(rffi.VOIDPP, a)[0]
        assert snd == chunks[2]

        ch.free(b)
        assert ch.free_list == rffi.cast(rffi.VOIDP, b)
        snd = rffi.cast(rffi.VOIDPP, b)[0]
        assert snd == rffi.cast(rffi.VOIDP, a)
        
    def test_callback(self):
        slong = cast_type_to_ffitype(rffi.LONG)
        libc = self.get_libc()
        qsort = libc.getpointer('qsort', [ffi_type_pointer, slong,
                                          slong, ffi_type_pointer],
                                ffi_type_void)

        def callback(ll_args, ll_res, stuff):
            p_a1 = rffi.cast(rffi.VOIDPP, ll_args[0])[0]
            p_a2 = rffi.cast(rffi.VOIDPP, ll_args[1])[0]
            a1 = rffi.cast(rffi.INTP, p_a1)[0]
            a2 = rffi.cast(rffi.INTP, p_a2)[0]
            res = rffi.cast(rffi.INTP, ll_res)
            if a1 > a2:
                res[0] = rffi.cast(rffi.INT, 1)
            else:
                res[0] = rffi.cast(rffi.INT, -1)

        ptr = CallbackFuncPtr([ffi_type_pointer, ffi_type_pointer],
                              ffi_type_sint, callback)
        
        TP = rffi.CArray(rffi.INT)
        to_sort = lltype.malloc(TP, 4, flavor='raw')
        to_sort[0] = rffi.cast(rffi.INT, 4)
        to_sort[1] = rffi.cast(rffi.INT, 3)
        to_sort[2] = rffi.cast(rffi.INT, 1)
        to_sort[3] = rffi.cast(rffi.INT, 2)
        qsort.push_arg(rffi.cast(rffi.VOIDP, to_sort))
        qsort.push_arg(rffi.sizeof(rffi.INT))
        qsort.push_arg(4)
        qsort.push_arg(ptr.ll_closure)
        qsort.call(lltype.Void)
        assert ([rffi.cast(lltype.Signed, to_sort[i]) for i in range(4)] ==
                [1,2,3,4])
        lltype.free(to_sort, flavor='raw')
        keepalive_until_here(ptr)  # <= this test is not translated, but don't
                                   #    forget this in code that is meant to be

    def test_compile(self):
        import py
        py.test.skip("Segfaulting test, skip")
        # XXX cannot run it on top of llinterp, some problems
        # with pointer casts

        def f(x, y):
            libm = self.get_libm()
            c_pow = libm.getpointer('pow', [ffi_type_double, ffi_type_double], ffi_type_double)
            c_pow.push_arg(x)
            c_pow.push_arg(y)
            res = c_pow.call(rffi.DOUBLE)
            return res

        fn = compile(f, [float, float])
        res = fn(2.0, 4.0)
        assert res == 16.0

    def test_rawfuncptr(self):
        libm = self.get_libm()
        pow = libm.getrawpointer('pow', [ffi_type_double, ffi_type_double],
                                 ffi_type_double)
        buffer = lltype.malloc(rffi.DOUBLEP.TO, 3, flavor='raw')
        buffer[0] = 2.0
        buffer[1] = 3.0
        buffer[2] = 43.5
        pow.call([rffi.cast(rffi.VOIDP, buffer),
                  rffi.cast(rffi.VOIDP, rffi.ptradd(buffer, 1))],
                 rffi.cast(rffi.VOIDP, rffi.ptradd(buffer, 2)))
        assert buffer[2] == 8.0
        lltype.free(buffer, flavor='raw')
        del pow
        del libm
        assert not ALLOCATED

    def test_make_struct_fftiype(self):
        tp = make_struct_ffitype(6, 2)
        assert tp.c_type == FFI_TYPE_STRUCT
        assert tp.c_size == 6
        assert tp.c_alignment == 2
        lltype.free(tp, flavor='raw')

    def test_struct_by_val(self):
        from pypy.translator.tool.cbuild import ExternalCompilationInfo
        from pypy.translator.platform import platform
        from pypy.tool.udir import udir

        c_file = udir.ensure("test_libffi", dir=1).join("xlib.c")
        c_file.write(py.code.Source('''
        #include <stdlib.h>
        #include <stdio.h>

        struct x_y {
            long x;
            long y;
        };

        long sum_x_y(struct x_y s) {
            return s.x + s.y;
        }

        long sum_x_y_p(struct x_y *p) {
            return p->x + p->y;
        }
        
        '''))
        eci = ExternalCompilationInfo(export_symbols=['sum_x_y'])
        lib_name = str(platform.compile([c_file], eci, 'x', standalone=False))

        lib = CDLL(lib_name)

        slong = cast_type_to_ffitype(rffi.LONG)
        size = slong.c_size*2
        alignment = slong.c_alignment
        tp = make_struct_ffitype(size, alignment)

        sum_x_y = lib.getrawpointer('sum_x_y', [tp], slong)

        buffer = lltype.malloc(rffi.LONGP.TO, 3, flavor='raw')
        buffer[0] = 200
        buffer[1] = 220
        buffer[2] = 666
        sum_x_y.call([rffi.cast(rffi.VOIDP, buffer)],
                     rffi.cast(rffi.VOIDP, rffi.ptradd(buffer, 2)))
        assert buffer[2] == 420

        lltype.free(buffer, flavor='raw')
        del sum_x_y
        lltype.free(tp, flavor='raw')
        del lib

        assert not ALLOCATED

    def test_ret_struct_val(self):
        from pypy.translator.tool.cbuild import ExternalCompilationInfo
        from pypy.translator.platform import platform
        from pypy.tool.udir import udir

        c_file = udir.ensure("test_libffi", dir=1).join("xlib.c")
        c_file.write(py.code.Source('''
        #include <stdlib.h>
        #include <stdio.h>

        struct s2h {
            short x;
            short y;
        };

        struct s2h give(short x, short y) {
            struct s2h out;
            out.x = x;
            out.y = y;
            return out;
        }

        struct s2h perturb(struct s2h inp) {
            inp.x *= 2;
            inp.y *= 3;
            return inp;
        }
        
        '''))
        eci = ExternalCompilationInfo(export_symbols=['give', 'perturb'])
        lib_name = str(platform.compile([c_file], eci, 'x', standalone=False))

        lib = CDLL(lib_name)

        size = ffi_type_sshort.c_size*2
        alignment = ffi_type_sshort.c_alignment
        tp = make_struct_ffitype(size, alignment)

        give  = lib.getrawpointer('give', [ffi_type_sshort, ffi_type_sshort],
                                  tp)
        inbuffer = lltype.malloc(rffi.SHORTP.TO, 2, flavor='raw')
        inbuffer[0] = rffi.cast(rffi.SHORT, 40)
        inbuffer[1] = rffi.cast(rffi.SHORT, 72)

        outbuffer = lltype.malloc(rffi.SHORTP.TO, 2, flavor='raw')

        give.call([rffi.cast(rffi.VOIDP, inbuffer),
                   rffi.cast(rffi.VOIDP, rffi.ptradd(inbuffer, 1))],
                   rffi.cast(rffi.VOIDP, outbuffer))

        assert outbuffer[0] == 40
        assert outbuffer[1] == 72

        perturb  = lib.getrawpointer('perturb', [tp], tp)

        inbuffer[0] = rffi.cast(rffi.SHORT, 7)
        inbuffer[1] = rffi.cast(rffi.SHORT, 11)

        perturb.call([rffi.cast(rffi.VOIDP, inbuffer)],
                     rffi.cast(rffi.VOIDP, outbuffer))

        assert inbuffer[0] == 7
        assert inbuffer[1] == 11

        assert outbuffer[0] == 14
        assert outbuffer[1] == 33

        lltype.free(outbuffer, flavor='raw')
        lltype.free(inbuffer, flavor='raw')
        del give
        del perturb
        lltype.free(tp, flavor='raw')
        del lib

        assert not ALLOCATED

class TestWin32Handles:
    def setup_class(cls):
        if sys.platform != 'win32':
            py.test.skip("Handle to libc library, Win-only test")
    
    def test_get_libc_handle(self):
        handle = get_libc_handle()
        print libc_name
        print hex(handle)
        assert handle != 0
        assert handle % 0x1000 == 0
