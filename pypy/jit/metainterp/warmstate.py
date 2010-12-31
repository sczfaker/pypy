import sys, weakref
from pypy.rpython.lltypesystem import lltype, llmemory, rstr, rffi
from pypy.rpython.ootypesystem import ootype
from pypy.rpython.annlowlevel import hlstr, llstr, cast_base_ptr_to_instance
from pypy.rpython.annlowlevel import cast_object_to_ptr
from pypy.rlib.objectmodel import specialize, we_are_translated, r_dict
from pypy.rlib.rarithmetic import intmask
from pypy.rlib.nonconst import NonConstant
from pypy.rlib.unroll import unrolling_iterable
from pypy.rlib.jit import (PARAMETERS, OPTIMIZER_SIMPLE, OPTIMIZER_FULL,
                           OPTIMIZER_NO_PERFECTSPEC)
from pypy.rlib.jit import BaseJitCell
from pypy.rlib.debug import debug_start, debug_stop, debug_print
from pypy.jit.metainterp import history
from pypy.jit.codewriter import support, heaptracker

# ____________________________________________________________

@specialize.arg(0)
def specialize_value(TYPE, x):
    """'x' must be a Signed, a GCREF or a Float.
    This function casts it to a more specialized type, like Char or Ptr(..).
    """
    INPUT = lltype.typeOf(x)
    if INPUT is lltype.Signed:
        if isinstance(TYPE, lltype.Ptr) and TYPE.TO._gckind == 'raw':
            # non-gc pointer
            return rffi.cast(TYPE, x)
        else:
            return lltype.cast_primitive(TYPE, x)
    elif INPUT is lltype.Float:
        assert TYPE is lltype.Float
        return x
    else:
        return lltype.cast_opaque_ptr(TYPE, x)

@specialize.ll()
def unspecialize_value(value):
    """Casts 'value' to a Signed, a GCREF or a Float."""
    if isinstance(lltype.typeOf(value), lltype.Ptr):
        if lltype.typeOf(value).TO._gckind == 'gc':
            return lltype.cast_opaque_ptr(llmemory.GCREF, value)
        else:
            adr = llmemory.cast_ptr_to_adr(value)
            return heaptracker.adr2int(adr)
    elif isinstance(lltype.typeOf(value), ootype.OOType):
        return ootype.cast_to_object(value)
    elif isinstance(value, float):
        return value
    else:
        return intmask(value)

@specialize.arg(0)
def unwrap(TYPE, box):
    if TYPE is lltype.Void:
        return None
    if isinstance(TYPE, lltype.Ptr):
        return box.getref(TYPE)
    if isinstance(TYPE, ootype.OOType):
        return box.getref(TYPE)
    if TYPE == lltype.Float:
        return box.getfloat()
    else:
        return lltype.cast_primitive(TYPE, box.getint())

@specialize.ll()
def wrap(cpu, value, in_const_box=False):
    if isinstance(lltype.typeOf(value), lltype.Ptr):
        if lltype.typeOf(value).TO._gckind == 'gc':
            value = lltype.cast_opaque_ptr(llmemory.GCREF, value)
            if in_const_box:
                return history.ConstPtr(value)
            else:
                return history.BoxPtr(value)
        else:
            adr = llmemory.cast_ptr_to_adr(value)
            value = heaptracker.adr2int(adr)
            # fall through to the end of the function
    elif isinstance(lltype.typeOf(value), ootype.OOType):
        value = ootype.cast_to_object(value)
        if in_const_box:
            return history.ConstObj(value)
        else:
            return history.BoxObj(value)
    elif isinstance(value, float):
        if in_const_box:
            return history.ConstFloat(value)
        else:
            return history.BoxFloat(value)
    elif isinstance(value, str) or isinstance(value, unicode):
        assert len(value) == 1     # must be a character
        value = ord(value)
    else:
        value = intmask(value)
    if in_const_box:
        return history.ConstInt(value)
    else:
        return history.BoxInt(value)

@specialize.arg(0)
def equal_whatever(TYPE, x, y):
    if isinstance(TYPE, lltype.Ptr):
        if TYPE.TO is rstr.STR or TYPE.TO is rstr.UNICODE:
            return rstr.LLHelpers.ll_streq(x, y)
    if TYPE is ootype.String or TYPE is ootype.Unicode:
        return x.ll_streq(y)
    return x == y

@specialize.arg(0)
def hash_whatever(TYPE, x):
    # Hash of lltype or ootype object.
    # Only supports strings, unicodes and regular instances,
    # as well as primitives that can meaningfully be cast to Signed.
    if isinstance(TYPE, lltype.Ptr):
        if TYPE.TO is rstr.STR or TYPE.TO is rstr.UNICODE:
            return rstr.LLHelpers.ll_strhash(x)    # assumed not null
        else:
            if x:
                return lltype.identityhash(x)
            else:
                return 0
    elif TYPE is ootype.String or TYPE is ootype.Unicode:
        return x.ll_hash()
    elif isinstance(TYPE, ootype.OOType):
        if x:
            return ootype.identityhash(x)
        else:
            return 0
    else:
        return lltype.cast_primitive(lltype.Signed, x)

@specialize.ll_and_arg(3)
def set_future_value(cpu, j, value, typecode):
    if typecode == 'ref':
        refvalue = cpu.ts.cast_to_ref(value)
        cpu.set_future_value_ref(j, refvalue)
    elif typecode == 'int':
        intvalue = lltype.cast_primitive(lltype.Signed, value)
        cpu.set_future_value_int(j, intvalue)
    elif typecode == 'float':
        assert isinstance(value, float)
        cpu.set_future_value_float(j, value)
    else:
        assert False

class JitCell(BaseJitCell):
    # the counter can mean the following things:
    #     counter >=  0: not yet traced, wait till threshold is reached
    #     counter == -1: there is an entry bridge for this cell
    #     counter == -2: tracing is currently going on for this cell
    counter = 0
    compiled_merge_points_wref = None    # list of weakrefs to LoopToken
    dont_trace_here = False
    wref_entry_loop_token = None         # (possibly) one weakref to LoopToken

    def get_compiled_merge_points(self):
        result = []
        if self.compiled_merge_points_wref is not None:
            for wref in self.compiled_merge_points_wref:
                looptoken = wref()
                if looptoken is not None and not looptoken.invalidated:
                    result.append(looptoken)
        return result

    def set_compiled_merge_points(self, looptokens):
        self.compiled_merge_points_wref = [self._makeref(token)
                                           for token in looptokens]

    def get_entry_loop_token(self):
        if self.wref_entry_loop_token is not None:
            return self.wref_entry_loop_token()
        return None

    def set_entry_loop_token(self, looptoken):
        self.wref_entry_loop_token = self._makeref(looptoken)

    def _makeref(self, looptoken):
        assert looptoken is not None
        return weakref.ref(looptoken)

# ____________________________________________________________


class WarmEnterState(object):
    THRESHOLD_LIMIT = sys.maxint // 2
    default_jitcell_dict = None

    def __init__(self, warmrunnerdesc, jitdriver_sd):
        "NOT_RPYTHON"
        self.warmrunnerdesc = warmrunnerdesc
        self.jitdriver_sd = jitdriver_sd
        if warmrunnerdesc is not None:       # for tests
            self.cpu = warmrunnerdesc.cpu
        try:
            self.profiler = warmrunnerdesc.metainterp_sd.profiler
        except AttributeError:       # for tests
            self.profiler = None
        # initialize the state with the default values of the
        # parameters specified in rlib/jit.py
        for name, default_value in PARAMETERS.items():
            meth = getattr(self, 'set_param_' + name)
            meth(default_value)

    def set_param_threshold(self, threshold):
        if threshold <= 0:
            self.increment_threshold = 0   # never reach the THRESHOLD_LIMIT
            return
        if threshold < 2:
            threshold = 2
        self.increment_threshold = (self.THRESHOLD_LIMIT // threshold) + 1
        # the number is at least 1, and at most about half THRESHOLD_LIMIT

    def set_param_trace_eagerness(self, value):
        self.trace_eagerness = value

    def set_param_trace_limit(self, value):
        self.trace_limit = value

    def set_param_inlining(self, value):
        self.inlining = value

    def set_param_optimizer(self, optimizer):
        if optimizer == OPTIMIZER_SIMPLE:
            from pypy.jit.metainterp import simple_optimize
            self.optimize_loop = simple_optimize.optimize_loop
            self.optimize_bridge = simple_optimize.optimize_bridge
        elif optimizer == OPTIMIZER_NO_PERFECTSPEC:
            from pypy.jit.metainterp import optimize_nopspec
            self.optimize_loop = optimize_nopspec.optimize_loop
            self.optimize_bridge = optimize_nopspec.optimize_bridge
        elif optimizer == OPTIMIZER_FULL:
            from pypy.jit.metainterp import optimize
            self.optimize_loop = optimize.optimize_loop
            self.optimize_bridge = optimize.optimize_bridge
        else:
            raise ValueError("unknown optimizer")

    def set_param_loop_longevity(self, value):
        # note: it's a global parameter, not a per-jitdriver one
        if (self.warmrunnerdesc is not None and
            self.warmrunnerdesc.memory_manager is not None):   # all for tests
            self.warmrunnerdesc.memory_manager.set_max_age(value)

    def disable_noninlinable_function(self, greenkey):
        cell = self.jit_cell_at_key(greenkey)
        cell.dont_trace_here = True
        debug_start("jit-disableinlining")
        loc = self.get_location_str(greenkey)
        debug_print("disabled inlining", loc)
        debug_stop("jit-disableinlining")

    def attach_unoptimized_bridge_from_interp(self, greenkey,
                                              entry_loop_token):
        cell = self.jit_cell_at_key(greenkey)
        old_token = cell.get_entry_loop_token()
        cell.set_entry_loop_token(entry_loop_token)
        cell.counter = -1       # valid entry bridge attached
        if old_token is not None:
            entry_loop_token._tmp_token = old_token
            # keep tmp token in case we invalidate this loop, so loops
            # can be redirected back to _tmp_token
            self.cpu.redirect_call_assembler(old_token, entry_loop_token)
            # entry_loop_token is also kept alive by any loop that used
            # to point to old_token.  Actually freeing old_token early
            # is a pointless optimization (it is tiny).
            old_token.record_jump_to(entry_loop_token)

    # ----------

    def make_entry_point(self):
        "NOT_RPYTHON"
        if hasattr(self, 'maybe_compile_and_run'):
            return self.maybe_compile_and_run

        warmrunnerdesc = self.warmrunnerdesc
        metainterp_sd = warmrunnerdesc.metainterp_sd
        jitdriver_sd = self.jitdriver_sd
        vinfo = jitdriver_sd.virtualizable_info
        index_of_virtualizable = jitdriver_sd.index_of_virtualizable
        num_green_args = jitdriver_sd.num_green_args
        get_jitcell = self.make_jitcell_getter()
        set_future_values = self.make_set_future_values()
        self.make_jitdriver_callbacks()
        confirm_enter_jit = self.confirm_enter_jit

        def maybe_compile_and_run(*args):
            """Entry point to the JIT.  Called at the point with the
            can_enter_jit() hint.
            """
            if NonConstant(False):
                # make sure we always see the saner optimizer from an
                # annotation point of view, otherwise we get lots of
                # blocked ops
                self.set_param_optimizer(OPTIMIZER_FULL)

            if vinfo is not None:
                virtualizable = args[num_green_args + index_of_virtualizable]
                virtualizable = vinfo.cast_to_vtype(virtualizable)
            else:
                virtualizable = None

            # look for the cell corresponding to the current greenargs
            greenargs = args[:num_green_args]
            cell = get_jitcell(True, *greenargs)

            if cell.counter >= 0:
                # update the profiling counter
                n = cell.counter + self.increment_threshold
                if n <= self.THRESHOLD_LIMIT:       # bound not reached
                    cell.counter = n
                    return
                if not confirm_enter_jit(*args):
                    cell.counter = 0
                    return
                # bound reached; start tracing
                from pypy.jit.metainterp.pyjitpl import MetaInterp
                metainterp = MetaInterp(metainterp_sd, jitdriver_sd)
                # set counter to -2, to mean "tracing in effect"
                cell.counter = -2
                try:
                    loop_token = metainterp.compile_and_run_once(jitdriver_sd,
                                                                 *args)
                finally:
                    if cell.counter == -2:
                        cell.counter = 0
            else:
                if cell.counter == -2:
                    # tracing already happening in some outer invocation of
                    # this function. don't trace a second time.
                    return
                assert cell.counter == -1
                if not confirm_enter_jit(*args):
                    return
                loop_token = cell.get_entry_loop_token()
                if loop_token is None or loop_token.invalidated:
                    # it was a weakref that has been freed or invalidated
                    cell.counter = 0
                    return
                # machine code was already compiled for these greenargs
                # get the assembler and fill in the boxes
                set_future_values(*args[num_green_args:])

            # ---------- execute assembler ----------
            while True:     # until interrupted by an exception
                metainterp_sd.profiler.start_running()
                debug_start("jit-running")
                fail_descr = warmrunnerdesc.execute_token(loop_token)
                debug_stop("jit-running")
                metainterp_sd.profiler.end_running()
                loop_token = None     # for test_memmgr
                if vinfo is not None:
                    vinfo.reset_vable_token(virtualizable)
                loop_token = fail_descr.handle_fail(metainterp_sd,
                                                    jitdriver_sd)

        maybe_compile_and_run._dont_inline_ = True
        self.maybe_compile_and_run = maybe_compile_and_run
        return maybe_compile_and_run

    # ----------

    def make_unwrap_greenkey(self):
        "NOT_RPYTHON"
        if hasattr(self, 'unwrap_greenkey'):
            return self.unwrap_greenkey
        #
        jitdriver_sd = self.jitdriver_sd
        green_args_spec = unrolling_iterable(jitdriver_sd._green_args_spec)
        #
        def unwrap_greenkey(greenkey):
            greenargs = ()
            i = 0
            for TYPE in green_args_spec:
                greenbox = greenkey[i]
                assert isinstance(greenbox, history.Const)
                value = unwrap(TYPE, greenbox)
                greenargs += (value,)
                i = i + 1
            return greenargs
        #
        unwrap_greenkey._always_inline_ = True
        self.unwrap_greenkey = unwrap_greenkey
        return unwrap_greenkey

    # ----------

    def make_jitcell_getter(self):
        "NOT_RPYTHON"
        if hasattr(self, 'jit_getter'):
            return self.jit_getter
        #
        if self.jitdriver_sd._get_jitcell_at_ptr is None:
            jit_getter = self._make_jitcell_getter_default()
        else:
            jit_getter = self._make_jitcell_getter_custom()
        #
        unwrap_greenkey = self.make_unwrap_greenkey()
        #
        def jit_cell_at_key(greenkey):
            greenargs = unwrap_greenkey(greenkey)
            return jit_getter(True, *greenargs)
        self.jit_cell_at_key = jit_cell_at_key
        self.jit_getter = jit_getter
        #
        return jit_getter

    def _make_jitcell_getter_default(self):
        "NOT_RPYTHON"
        jitdriver_sd = self.jitdriver_sd
        green_args_spec = unrolling_iterable(jitdriver_sd._green_args_spec)
        #
        def comparekey(greenargs1, greenargs2):
            i = 0
            for TYPE in green_args_spec:
                if not equal_whatever(TYPE, greenargs1[i], greenargs2[i]):
                    return False
                i = i + 1
            return True
        #
        def hashkey(greenargs):
            x = 0x345678
            i = 0
            for TYPE in green_args_spec:
                item = greenargs[i]
                y = hash_whatever(TYPE, item)
                x = intmask((1000003 * x) ^ y)
                i = i + 1
            return x
        #
        jitcell_dict = r_dict(comparekey, hashkey)
        #
        def get_jitcell(build, *greenargs):
            try:
                cell = jitcell_dict[greenargs]
            except KeyError:
                if not build:
                    return None
                cell = JitCell()
                jitcell_dict[greenargs] = cell
            return cell
        return get_jitcell

    def _make_jitcell_getter_custom(self):
        "NOT_RPYTHON"
        rtyper = self.warmrunnerdesc.rtyper
        get_jitcell_at_ptr = self.jitdriver_sd._get_jitcell_at_ptr
        set_jitcell_at_ptr = self.jitdriver_sd._set_jitcell_at_ptr
        lltohlhack = {}
        #
        def get_jitcell(build, *greenargs):
            fn = support.maybe_on_top_of_llinterp(rtyper, get_jitcell_at_ptr)
            cellref = fn(*greenargs)
            # <hacks>
            if we_are_translated():
                BASEJITCELL = lltype.typeOf(cellref)
                cell = cast_base_ptr_to_instance(JitCell, cellref)
            else:
                if isinstance(cellref, (BaseJitCell, type(None))):
                    BASEJITCELL = None
                    cell = cellref
                else:
                    BASEJITCELL = lltype.typeOf(cellref)
                    if cellref:
                        cell = lltohlhack[rtyper.type_system.deref(cellref)]
                    else:
                        cell = None
            # </hacks>
            if not build:
                return cell
            if cell is None:
                cell = JitCell()
                # <hacks>
                if we_are_translated():
                    cellref = cast_object_to_ptr(BASEJITCELL, cell)
                else:
                    if BASEJITCELL is None:
                        cellref = cell
                    else:
                        if isinstance(BASEJITCELL, lltype.Ptr):
                            cellref = lltype.malloc(BASEJITCELL.TO)
                        elif isinstance(BASEJITCELL, ootype.Instance):
                            cellref = ootype.new(BASEJITCELL)
                        else:
                            assert False, "no clue"
                        lltohlhack[rtyper.type_system.deref(cellref)] = cell
                # </hacks>
                fn = support.maybe_on_top_of_llinterp(rtyper,
                                                      set_jitcell_at_ptr)
                fn(cellref, *greenargs)
            return cell
        return get_jitcell

    # ----------

    def make_set_future_values(self):
        "NOT_RPYTHON"
        if hasattr(self, 'set_future_values'):
            return self.set_future_values

        warmrunnerdesc = self.warmrunnerdesc
        jitdriver_sd   = self.jitdriver_sd
        cpu = self.cpu
        vinfo = jitdriver_sd.virtualizable_info
        red_args_types = unrolling_iterable(jitdriver_sd._red_args_types)
        #
        def set_future_values(*redargs):
            i = 0
            for typecode in red_args_types:
                set_future_value(cpu, i, redargs[i], typecode)
                i = i + 1
            if vinfo is not None:
                set_future_values_from_vinfo(*redargs)
        #
        if vinfo is not None:
            i0 = len(jitdriver_sd._red_args_types)
            num_green_args = jitdriver_sd.num_green_args
            index_of_virtualizable = jitdriver_sd.index_of_virtualizable
            vable_static_fields = unrolling_iterable(
                zip(vinfo.static_extra_types, vinfo.static_fields))
            vable_array_fields = unrolling_iterable(
                zip(vinfo.arrayitem_extra_types, vinfo.array_fields))
            getlength = cpu.ts.getlength
            getarrayitem = cpu.ts.getarrayitem
            #
            def set_future_values_from_vinfo(*redargs):
                i = i0
                virtualizable = redargs[index_of_virtualizable]
                virtualizable = vinfo.cast_to_vtype(virtualizable)
                for typecode, fieldname in vable_static_fields:
                    x = getattr(virtualizable, fieldname)
                    set_future_value(cpu, i, x, typecode)
                    i = i + 1
                for typecode, fieldname in vable_array_fields:
                    lst = getattr(virtualizable, fieldname)
                    for j in range(getlength(lst)):
                        x = getarrayitem(lst, j)
                        set_future_value(cpu, i, x, typecode)
                        i = i + 1
        else:
            set_future_values_from_vinfo = None
        #
        self.set_future_values = set_future_values
        return set_future_values

    # ----------

    def make_jitdriver_callbacks(self):
        if hasattr(self, 'get_location_str'):
            return
        #
        warmrunnerdesc = self.warmrunnerdesc
        unwrap_greenkey = self.make_unwrap_greenkey()
        jit_getter = self.make_jitcell_getter()
        jd = self.jitdriver_sd
        cpu = self.cpu

        def can_inline_greenargs(*greenargs):
            if can_never_inline(*greenargs):
                return False
            cell = jit_getter(False, *greenargs)
            if cell is not None and cell.dont_trace_here:
                return False
            return True
        def can_inline_callable(greenkey):
            greenargs = unwrap_greenkey(greenkey)
            return can_inline_greenargs(*greenargs)
        self.can_inline_greenargs = can_inline_greenargs
        self.can_inline_callable = can_inline_callable

        def get_assembler_token(greenkey, redboxes):
            # 'redboxes' is only used to know the types of red arguments
            cell = self.jit_cell_at_key(greenkey)
            entry_loop_token = cell.get_entry_loop_token()
            if entry_loop_token is None or entry_loop_token._tmp_token is None:
                from pypy.jit.metainterp.compile import compile_tmp_callback
                if cell.counter == -1:    # used to be a valid entry bridge,
                    cell.counter = 0      # but was freed in the meantime.
                memmgr = warmrunnerdesc.memory_manager
                tmp_token = compile_tmp_callback(cpu, jd, greenkey,
                                                 redboxes, memmgr)
                if entry_loop_token is None:
                    entry_loop_token = tmp_token
                    cell.set_entry_loop_token(entry_loop_token)
                else:
                    entry_loop_token._tmp_token = tmp_token
            return entry_loop_token
        self.get_assembler_token = get_assembler_token
        
        #
        get_location_ptr = self.jitdriver_sd._get_printable_location_ptr
        if get_location_ptr is None:
            missing = '(no jitdriver.get_printable_location!)'
            missingll = llstr(missing)
            def get_location_str(greenkey):
                if we_are_translated():
                    return missingll
                else:
                    return missing
        else:
            rtyper = self.warmrunnerdesc.rtyper
            unwrap_greenkey = self.make_unwrap_greenkey()
            #
            def get_location_str(greenkey):
                greenargs = unwrap_greenkey(greenkey)
                fn = support.maybe_on_top_of_llinterp(rtyper, get_location_ptr)
                res = fn(*greenargs)
                if not we_are_translated() and not isinstance(res, str):
                    res = hlstr(res)
                return res
        self.get_location_str = get_location_str
        #
        confirm_enter_jit_ptr = self.jitdriver_sd._confirm_enter_jit_ptr
        if confirm_enter_jit_ptr is None:
            def confirm_enter_jit(*args):
                return True
        else:
            rtyper = self.warmrunnerdesc.rtyper
            #
            def confirm_enter_jit(*args):
                fn = support.maybe_on_top_of_llinterp(rtyper,
                                                      confirm_enter_jit_ptr)
                return fn(*args)
        self.confirm_enter_jit = confirm_enter_jit
        #
        can_never_inline_ptr = self.jitdriver_sd._can_never_inline_ptr
        if can_never_inline_ptr is None:
            def can_never_inline(*greenargs):
                return False
        else:
            rtyper = self.warmrunnerdesc.rtyper
            #
            def can_never_inline(*greenargs):
                fn = support.maybe_on_top_of_llinterp(rtyper,
                                                      can_never_inline_ptr)
                return fn(*greenargs)
        self.can_never_inline = can_never_inline
