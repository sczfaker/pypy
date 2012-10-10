import autopath


class AppTestMap:

   def test_trivial_map_one_seq(self):
      assert list(map(lambda x: x+2, [1, 2, 3, 4])) == [3, 4, 5, 6]

   def test_trivial_map_one_seq_2(self):
      assert list(map(str, [1, 2, 3, 4])) == ['1', '2', '3', '4']

   def test_trivial_map_two_seq(self):
      assert list(map(lambda x,y: x+y,
                           [1, 2, 3, 4],[1, 2, 3, 4])) == (
                       [2, 4, 6, 8])

   def test_trivial_map_sizes_dont_match(self):
      assert list(map(lambda x,y: x+y, [1, 2, 3, 4], [1, 2, 3])) == (
         [2, 4, 6])

   def test_trivial_map_no_arguments(self):
      raises(TypeError, map)

   def test_trivial_map_no_function_no_seq(self):
      raises(TypeError, map, None)

   def test_trivial_map_no_fuction(self):
      m = map(None, [1, 2, 3])    # Don't crash here...
      raises(TypeError, next, m)  # ...but only on first item.

   def test_map_identity1(self):
      a = ['1', 2, 3, 'b', None]
      b = a[:]
      assert list(map(lambda x: x, a)) == a
      assert a == b

   def test_map_badoperation(self):
      a = ['1', 2, 3, 'b', None]
      raises(TypeError, list, map, lambda x: x+1, a)

   def test_map_add(self):
      a = [1, 2, 3, 4]
      b = [0, 1, 1, 1]
      assert list(map(lambda x, y: x+y, a, b)) == [1, 3, 4, 5]

   def test_map_first_item(self):
      a = [1, 2, 3, 4, 5]
      b = [6, 7, 8, 9, 10]
      assert list(map(lambda x, y: x, a, b)) == a

   def test_map_iterables(self):
      class A(object):
         def __init__(self, n):
            self.n = n
         def __iter__(self):
            return B(self.n)
      class B(object):
         def __init__(self, n):
            self.n = n
         def __next__(self):
            self.n -= 1
            if self.n == 0: raise StopIteration
            return self.n
      result = map(lambda *x:x, A(3), A(8))
      # this also checks that B.next() is not called any more after it
      # raised StopIteration once
      assert list(result) == [(2, 7), (1, 6)]

   def test_repr(self):
      assert repr(map(1, [2])).startswith('<map object ')

class AppTestMap2:

    def test_map(self):
        obj_list = [object(), object(), object()]
        it = map(lambda *x:x, obj_list)
        for x in obj_list:
            assert next(it) == (x, )
        raises(StopIteration, next, it)

        it = map(lambda *x:x, [1, 2, 3], [4], [5, 6])
        assert next(it) == (1, 4, 5)
        raises(StopIteration, next, it)

        it = map(lambda *x:x, [], [], [1], [])
        raises(StopIteration, next, it)

        it = map(str, [0, 1, 0, 1])
        for x in ['0', '1', '0', '1']:
            assert next(it) == x
        raises(StopIteration, next, it)

        import operator
        it = map(operator.add, [1, 2, 3], [4, 5, 6])
        for x in [5, 7, 9]:
            assert next(it) == x
        raises(StopIteration, next, it)

    def test_map_wrongargs(self):
        # Duplicate python 2.4 behaviour for invalid arguments
        it = map(0, [])
        raises(StopIteration, next, it)
        it = map(0, [0])
        raises(TypeError, next, it)
        raises(TypeError, map, None, 0)

        raises(TypeError, map, None)
        raises(TypeError, map, bool)
        raises(TypeError, map, 42)

class AppTestZip:
   def test_one_list(self):
      assert list(zip([1,2,3])) == [(1,), (2,), (3,)]

   def test_three_lists(self):
      assert list(zip([1,2,3], [1,2], [1,2,3])) == [(1,1,1), (2,2,2)]

   def test_repr(self):
      assert repr(zip([1,2,3], [1,2], [1,2,3])).startswith('<zip object ')

class AppTestFilter:
   def test_None(self):
       assert list(filter(None, ['a', 'b', 1, 0, None])) == ['a', 'b', 1]

   def test_return_type(self):
       txt = "This is a test text"
       assert list(filter(None, txt)) == list(txt)
       tup = ("a", None, 0, [], 1)
       assert list(filter(None, tup)) == ["a", 1]

   def test_function(self):
       assert list(filter(lambda x: x != "a", "a small text")) == list(" smll text")
       assert list(filter(lambda x: x < 20, [3, 33, 5, 55])) == [3, 5]

class AppTestFilter2:
    def test_filter(self):
        it = filter(None, [])
        raises(StopIteration, next, it)

        it = filter(None, [1, 0, 2, 3, 0])
        for x in [1, 2, 3]:
            assert next(it) == x
        raises(StopIteration, next, it)

        def is_odd(arg):
            return (arg % 2 == 1)

        it = filter(is_odd, [1, 2, 3, 4, 5, 6])
        for x in [1, 3, 5]:
            assert next(it) == x
        raises(StopIteration, next, it)

    def test_filter_wrongargs(self):
        import itertools

        it = filter(0, [1])
        raises(TypeError, next, it)

        raises(TypeError, filter, bool, None)


class AppTestRange:
   def test_range(self):
      x = range(2, 9, 3)
      assert x[1] == 5
      assert len(x) == 3
      assert list(x) == [2, 5, 8]
      # test again, to make sure that range() is not its own iterator
      assert list(x) == [2, 5, 8]

   def test_range_iter(self):
      x = range(2, 9, 3)
      it = iter(x)
      assert iter(it) is it
      assert it.__next__() == 2
      assert it.__next__() == 5
      assert it.__next__() == 8
      raises(StopIteration, it.__next__)
      # test again, to make sure that range() is not its own iterator
      assert iter(x).__next__() == 2

   def test_range_object_with___index__(self):
       class A(object):
          def __index__(self):
             return 5

       assert list(range(A())) == [0, 1, 2, 3, 4]
       assert list(range(0, A())) == [0, 1, 2, 3, 4]
       assert list(range(0, 10, A())) == [0, 5]

       class A2(object):
          def __index__(self):
             return 'quux'
       raises(TypeError, range, A2())

   def test_range_float(self):
      raises(TypeError, "range(0.1, 2.0, 1.1)")

   def test_range_long(self):
       import sys
       a = 10 * sys.maxsize
       assert range(a)[-1] == a-1
       assert range(0, a)[-1] == a-1
       assert range(0, 1, a)[-1] == 0

   def test_range_reduce(self):
      x = range(2, 9, 3)
      callable, args = x.__reduce__()
      y = callable(*args)
      assert list(y) == list(x)

   def test_range_iter_reduce(self):
      x = iter(range(2, 9, 3))
      next(x)
      callable, args = x.__reduce__()
      y = callable(*args)
      assert list(y) == list(x)

   def test_range_iter_reduce_one(self):
      x = iter(range(2, 9))
      next(x)
      callable, args = x.__reduce__()
      y = callable(*args)
      assert list(y) == list(x)

   def test_lib_python_range_optimization(self):
      x = range(1)
      assert type(reversed(x)) == type(iter(x))


class AppTestReversed:
   def test_reversed(self):
      r = reversed("hello")
      assert iter(r) is r
      assert r.__next__() == "o"
      assert r.__next__() == "l"
      assert r.__next__() == "l"
      assert r.__next__() == "e"
      assert r.__next__() == "h"
      raises(StopIteration, r.__next__)
      assert list(reversed(list(reversed("hello")))) == ['h','e','l','l','o']
      raises(TypeError, reversed, reversed("hello"))

class AppTestAllAny:
    """
    These are copied directly and replicated from the Python 2.5 source code.
    """

    def test_all(self):

        class TestFailingBool(object):
            def __bool__(self):
                raise RuntimeError
        class TestFailingIter(object):
            def __iter__(self):
                raise RuntimeError

        assert all([2, 4, 6]) == True
        assert all([2, None, 6]) == False
        raises(RuntimeError, all, [2, TestFailingBool(), 6])
        raises(RuntimeError, all, TestFailingIter())
        raises(TypeError, all, 10)               # Non-iterable
        raises(TypeError, all)                   # No args
        raises(TypeError, all, [2, 4, 6], [])    # Too many args
        assert all([]) == True                   # Empty iterator
        S = [50, 60]
        assert all([x > 42 for x in S]) == True
        S = [50, 40, 60]
        assert all([x > 42 for x in S]) == False

    def test_any(self):

        class TestFailingBool(object):
            def __bool__(self):
                raise RuntimeError
        class TestFailingIter(object):
            def __iter__(self):
                raise RuntimeError

        assert any([None, None, None]) == False
        assert any([None, 4, None]) == True
        raises(RuntimeError, any, [None, TestFailingBool(), 6])
        raises(RuntimeError, all, TestFailingIter())
        raises(TypeError, any, 10)               # Non-iterable
        raises(TypeError, any)                   # No args
        raises(TypeError, any, [2, 4, 6], [])    # Too many args
        assert any([]) == False                  # Empty iterator
        S = [40, 60, 30]
        assert any([x > 42 for x in S]) == True
        S = [10, 20, 30]
        assert any([x > 42 for x in S]) == False

class AppTestMinMax:
   def test_min(self):
      assert min(1, 2) == 1
      assert min(1, 2, key=lambda x: -x) == 2
      assert min([1, 2, 3]) == 1
      raises(TypeError, min, 1, 2, bar=2)
      raises(TypeError, min, 1, 2, key=lambda x: x, bar=2)

   def test_max(self):
      assert max(1, 2) == 2
      assert max(1, 2, key=lambda x: -x) == 1
      assert max([1, 2, 3]) == 3
      raises(TypeError, max, 1, 2, bar=2)
      raises(TypeError, max, 1, 2, key=lambda x: x, bar=2)
