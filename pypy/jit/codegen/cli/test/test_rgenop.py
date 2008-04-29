import py
from pypy.rpython.ootypesystem import ootype
from pypy.jit.codegen.cli.rgenop import RCliGenOp
from pypy.jit.codegen.test.rgenop_tests import OOType
from pypy.jit.codegen.test.rgenop_tests import AbstractRGenOpTestsDirect
from pypy.jit.codegen.test.rgenop_tests import AbstractRGenOpTestsCompile
from pypy.translator.cli.test.runtest import compile_function

# for the individual tests see
# ====> ../../test/rgenop_tests.py

class TestRCliGenopDirect(AbstractRGenOpTestsDirect):
    RGenOp = RCliGenOp
    T = OOType

    def cast(self, gv, nb_args, RESULT='not used'):
        "NOT_RPYTHON"
        def fn(*args):
            return gv.getobj().func.Invoke(*args)
        return fn
    cast_float = cast
    cast_whatever = cast

    def directtesthelper(self, FUNCTYPE, func):
        py.test.skip('???')

    def test_cast_raising(self):
        py.test.skip('fixme')

    def test_float_adder(self):
        py.test.skip('fixme')

    def test_float_loop_direct(self):
        py.test.skip('fixme')

    def test_switch_direct(self):
        py.test.skip('no promotion/flexswitch for now please :-)')

    def test_large_switch_direct(self):
        py.test.skip('no promotion/flexswitch for now please :-)')

    def test_defaultonly_switch(self):
        py.test.skip('no promotion/flexswitch for now please :-)')

    def test_read_frame_var_direct(self):
        py.test.skip('fixme: add support for frames')

    def test_read_frame_var_float_direct(self):
        py.test.skip('fixme: add support for frames')

    def test_genconst_from_frame_var_direct(self):
        py.test.skip('fixme: add support for frames')

    def test_write_frame_place_float_direct(self):
        py.test.skip('fixme: add support for frames')
        
    def test_read_float_frame_place_direct(self):
        py.test.skip('fixme: add support for frames')

    def test_write_frame_place_direct(self):
        py.test.skip('fixme: add support for frames')

    def test_write_lots_of_frame_places_direct(self):
        py.test.skip('fixme: add support for frames')
        
    def test_read_frame_place_direct(self):
        py.test.skip('fixme: add support for frames')

    def test_frame_vars_like_the_frontend_direct(self):
        py.test.skip('fixme: add support for frames')

    def test_from_random_direct(self):
        py.test.skip('mono crashes')
        
    def test_from_random_3_direct(self):
        py.test.skip('infinite loop')
        
    def test_from_random_5_direct(self):
        py.test.skip('mono crash')

    def test_ovfcheck_adder_direct(self):
        py.test.skip('fixme')

    def test_ovfcheck1_direct(self):
        py.test.skip('fixme')

    def test_ovfcheck2_direct(self):
        py.test.skip('fixme')

    def test_cast_direct(self):
        py.test.skip('fixme')

    def test_array_of_ints(self):
        py.test.skip('fixme')

    def test_interior_access(self):
        py.test.skip('fixme')


class TestRCliGenopCompile(AbstractRGenOpTestsCompile):
    RGenOp = RCliGenOp
    T = OOType

    def getcompiled(self, fn, annotation, annotatorpolicy):
        return compile_function(fn, annotation,
                                annotatorpolicy=annotatorpolicy,
                                nowrap=False)

    def test_largedummy_compile(self):
        py.test.skip('it works only if we increase .maxstack')

    def test_switch_compile(self):
        py.test.skip('no promotion/flexswitch for now please :-)')

    def test_large_switch_compile(self):
        py.test.skip('no promotion/flexswitch for now please :-)')

    def test_read_frame_var_compile(self):
        py.test.skip('fixme: add support for frames')

    def test_write_frame_place_compile(self):
        py.test.skip('fixme: add support for frames')

    def test_read_frame_place_compile(self):
        py.test.skip('fixme: add support for frames')
        
    def test_ovfcheck_adder_compile(self):
        py.test.skip('fixme')

    def test_ovfcheck1_compile(self):
        py.test.skip('fixme')
