from pypy.rpython.lltypesystem import rffi, lltype
from pypy.interpreter.error import OperationError
from pypy.module.cpyext.test.test_api import BaseApiTest
from pypy.module.cpyext import sequence

class TestIterator(BaseApiTest):
    def test_sequence(self, space, api):
        w_t = space.wrap((1, 2, 3, 4))
        assert api.PySequence_Fast(w_t, "message") is w_t
        w_l = space.wrap((1, 2, 3, 4))
        assert api.PySequence_Fast(w_l, "message") is w_l

        assert space.int_w(api.PySequence_Fast_GET_ITEM(w_l, 1)) == 2
        assert api.PySequence_Fast_GET_SIZE(w_l) == 4

        w_set = space.wrap(set((1, 2, 3, 4)))
        w_seq = api.PySequence_Fast(w_set, "message")
        assert space.type(w_seq) is space.w_tuple
        assert space.int_w(space.len(w_seq)) == 4

    def test_exception(self, space, api):
        message = rffi.str2charp("message")
        assert not api.PySequence_Fast(space.wrap(3), message)
        assert api.PyErr_Occurred() is space.w_TypeError
        api.PyErr_Clear()

        exc = raises(OperationError, sequence.PySequence_Fast,
                     space, space.wrap(3), message)
        assert exc.value.match(space, space.w_TypeError)
        assert space.str_w(exc.value.get_w_value(space)) == "message"
        rffi.free_charp(message)
    
    def test_get_slice(self, space, api):
        w_t = space.wrap((1, 2, 3, 4, 5))
        assert space.unwrap(api.PySequence_GetSlice(w_t, 2, 4)) == (3, 4)
        assert space.unwrap(api.PySequence_GetSlice(w_t, 1, -1)) == (2, 3, 4)
