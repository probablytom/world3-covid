from inspect import isfunction, isclass, ismethod
import re
import builtins
from functools import wraps, partial, reduce
import ast
from textwrap import dedent
import copy
import inspect
from types import FunctionType


class AspectHooks:

    pre_rules = list()
    around_rules = list()
    post_rules = list()
    error_handling_rules = list()
    fuzzers = list()
    manage_ordering = False
    treat_rules_as_dynamic = False
    rule_cache = dict()
    shallow_apply = False
    permitted_depth = 1

    def __enter__(self, *args, **kwargs):
        self.old_import = __import__
        import builtins
        builtins.__import__ = self.__import__

    def final_around(self, target, *args, **kwargs):
        return target(*args, **kwargs)

    def __import__(self, *args, **kwargs):
        # We don't want every nested use of the `import` keyword to use this, 
        # so we actually have to disable it before we do anymore importing!
        # We'll re-enable at the very end.
        builtins = self.old_import("builtins")
        builtins.__import__ = self.old_import
        mod = self.old_import(*args, **kwargs)

        def build_wrapper(target):

            class CouldNotFuzzException(Exception):
                pass


            old_target_code = copy.deepcopy(target.__code__)

            @wraps(target)
            def wrapper(*args, **kwargs):

                pre, around, post, error_handlers, fuzzers = self.get_rules(target.__name__, AspectHooks.manage_ordering)
                target_to_exec = target  # fuzzing may change this.

                def reset_code_to_previous():
                    # TODO FIX THIS: CHANGED FUZZING INJECTION METHOD
                    if not isinstance(target, FunctionType):
                        target.__func__.__code__ = old_target_code
                    else:
                        target.__code__ = old_target_code

                try:

                    if fuzzers is not None and fuzzers != []:
                        code = dedent(inspect.getsource(target))
                        target_ast = ast.parse(code)
                        funcbody_steps = target_ast.body[0].body  # Assume we've got a module object containing only a function definition.

                        for fuzzer in fuzzers:
                            non_inline_changed_steps = fuzzer(funcbody_steps, *args, **kwargs)

                            if non_inline_changed_steps:
                                funcbody_steps = non_inline_changed_steps

                        # target_ast.body[0].body = funcbody_steps
                        # print(ast.dump(target_ast))
                        # compiled_fuzzed_target = compile(target_ast, "<ast>", "exec")

                        target_ast.body[0].name = "__pdsf_fuzzed_temp"
                        target_ast.body[0].body = funcbody_steps
                        target_ast.body[0].decorator_list = []  # dodgy as hell
                        compiled_fuzzed_target = compile(target_ast, "<ast>", "exec")
                        exec(compiled_fuzzed_target)  # A function containing our fuzzed code now exists with the id "__pdsf_fuzzed_temp" in our locals

                        
                        def new_target_call_method(*args, **kwargs):
                            print("\nExecuting new\n")
                            return exec(compiled_fuzzed_target, *args, **kwargs)  # TODO does this return work with exec?

                        if not isinstance(target, FunctionType):
                            target.__func__ = eval("__pdsf_fuzzed_temp")
                        else:
                            target_to_exec = eval("__pdsf_fuzzed_temp")

                    # Run pre advice
                    [advice(target_to_exec, *args, **kwargs) for advice in pre]

                    def nest_around_call(nested_around, next_around):
                        return partial(next_around, nested_around)

                    # NOTE. The signature of around functions is around(next_around_function, target, *args, **kwargs),
                    # ... and they MUST make the call next_around_function(target*args, **kwargs)
                    # for around_index in range(len(around-1)):
                    #     around[around_index] = partial(around[around_index], around_index[around_index+1])
                    # around[-1] = partial(around[-1], self.final_around)

                    nested_around = reduce(nest_around_call,
                                           around[::-1],
                                           self.final_around)

                    ret = nested_around(target_to_exec, *args, **kwargs)

                    for advice in post:
                        post_return = advice(target_to_exec, ret, *args, **kwargs)
                        ret = ret if post_return is None else post_return

                    reset_code_to_previous()

                    return ret
                except Exception as exception:

                    # Oh no! We might have fuzzed and then thrown an exception before we could replace the fuzzed code object. Make sure that's done now.
                    reset_code_to_previous()

                    prevent_raising = False
                    for handler in error_handlers:
                        prevent_raising = prevent_raising or handler(target_to_exec, exception, *args, **kwargs)
                    if not prevent_raising:
                        raise exception

            return wrapper

        def apply_hooks(target_object, remaining_depth):
            print("applying to " + str(target_object) + " with depth " + str(remaining_depth))
            for item_name in filter(lambda p: isinstance(p, str) and len(p) > 1 and p[:2] != "__", dir(target_object)):
                item = getattr(target_object, item_name)
                try:
                    setattr(target_object, "__pdsf_visited", True)
                except TypeError as e:
                    print("Tried to apply hooks to " + str(target_object) + ", but couldn't. It's probably a builtin.")
                try:
                    print(item.__module__, mod.__name__)  
                except:
                    print(str(item) + " (has no __module__ attr)")
                # Only apply if we're either specifically applying to things imported by this module too (`deep_apply`) or
                # if it's from the original target module, `mod`
                if hasattr(item, "__module__") and (item.__module__ == mod.__name__ or not AspectHooks.shallow_apply) and remaining_depth > 0:
                    print(2)  
                    if isfunction(item) or ismethod(item):
                        print(3)  
                        try:
                            print("Added hooks to " + str(item_name) + " on target object " + str(target_object))
                            setattr(target_object, item_name, build_wrapper(item))
                        except TypeError as e:
                            print("Tried to apply hooks to " + str(item) + ", but couldn't. It's probably a builtin.")
                            print(item.__module__)
                    elif isclass(item):#and not hasattr(item, "__pdsf_visited"):
                        print(4)  
                        print("Applying to " + str(item) + " (named " + item_name + ")")
                        apply_hooks(item, remaining_depth-1)
                    print(5)
                else:
                    print(6)
                    # print('hasattr(item, "__module__"):\t' + str(hasattr(item, "__module__")))
                    # print('item.__module__ == mod.__name__:\t' + str(item.__module__ == mod.__name__))
                    # print('remaining_depth:\t' + str(remaining_depth))


                    print(5)  
        apply_hooks(mod, remaining_depth=AspectHooks.permitted_depth)

        return mod
        builtins.__import__ = self.__import__

    @classmethod
    def add_prelude(cls, rule, advice, urgency=0):
        rule_tuple = (re.compile(rule), advice, urgency)
        AspectHooks.pre_rules.append(rule_tuple)
        return lambda : AspectHooks.pre_rules.remove(rule_tuple)

    @classmethod
    def add_around(cls, rule, advice, urgency=0):
        rule_tuple = (re.compile(rule), advice, urgency)
        AspectHooks.around_rules.append(rule_tuple)
        return lambda : AspectHooks.around_rules.remove(rule_tuple)

    @classmethod
    def add_encore(cls, rule, advice, urgency=0):
        rule_tuple = (re.compile(rule), advice, urgency)
        AspectHooks.post_rules.append(rule_tuple)
        return lambda : AspectHooks.post_rules.remove(rule_tuple)

    @classmethod
    def add_error_handler(cls, rule, advice, urgency=0):
        rule_tuple = (re.compile(rule), advice, urgency)
        AspectHooks.error_handling_rules.append(rule_tuple)
        return lambda : AspectHooks.error_handling_rules.remove(rule_tuple)

    @classmethod
    def remove(cls, rule_remover):
        try:
            rule_remover()
            cls.rule_cache = dict()
        except Exception as e:
            print(e)
            raise(e)


    @classmethod
    def add_fuzzer(self, rule, advice, urgency=0):
        rule_tuple = (re.compile(rule), advice, urgency)
        AspectHooks.fuzzers.append(rule_tuple)
        return lambda : AspectHooks.fuzzers.remove(rule_tuple)


    def get_rules(self, methodname, manage_urgency):

        if not AspectHooks.treat_rules_as_dynamic and methodname in AspectHooks.rule_cache:
            return AspectHooks.rule_cache[methodname]

        pre, around, post, error_handlers, fuzzers = list(), list(), list(), list(), list()
        for pattern, advice, urgency in AspectHooks.pre_rules:
            if pattern.match(methodname) is not None:
                pre.append((advice, urgency) if manage_urgency else advice)

        for pattern, advice, urgency in AspectHooks.around_rules:
            if pattern.match(methodname) is not None:
                around.append((advice, urgency) if manage_urgency else advice)

        for pattern, advice, urgency in AspectHooks.post_rules:
            if pattern.match(methodname) is not None:
                post.append((advice, urgency) if manage_urgency else advice)

        for pattern, advice, urgency in AspectHooks.error_handling_rules:
            if pattern.match(methodname) is not None:
                error_handlers.append((advice, urgency) if manage_urgency else advice)

        for pattern, advice, urgency in AspectHooks.fuzzers:
            if pattern.match(methodname):
                fuzzers.append((advice, urgency) if manage_urgency else advice)

        if not manage_urgency:
            if not AspectHooks.treat_rules_as_dynamic:
                AspectHooks.rule_cache[methodname] = (pre, around, post, error_handlers, fuzzers)

            return (pre, around, post, error_handlers, fuzzers)

        urgencykey = lambda ad_urg_tuple: -ad_urg_tuple[1]  # Negative so we get the highest urgency first
        first = lambda x: x[0]
        pre, around, post, error_handlers, fuzzers = sorted(pre, key=urgencykey), sorted(around, key=urgencykey), sorted(post, key=urgencykey), sorted(error_handlers, key=urgencykey), sorted(fuzzers, key=urgencykey)
        advice_functions = list(map(first, pre)), list(map(first, around)), list(map(first, post)), list(map(first, error_handlers)), list(map(first, fuzzers))

        if not AspectHooks.treat_rules_as_dynamic:
            AspectHooks.rule_cache[methodname] = advice_functions

        return advice_functions

    @classmethod
    def reset(cls):
        AspectHooks.pre_rules = list()
        AspectHooks.around_rules = list()
        AspectHooks.post_rules = list()
        AspectHooks.error_handling_rules = list()
        AspectHooks.fuzzers = list()

    def __exit__(self, *args, **kwargs):
        builtins.__import__ = self.old_import

    def __init__(self, ) -> None:
        # TODO: add options for instance-based configuration.
        # step 1: make class-level attributes default attributes here
        # step 2: add options as parameters here, set them for an instance
        # step 3: change weaving logic to avoid AsepctHooks.attr and use
        #         self.attr instead
        # step 4: test test test!!!
        pass

if __name__ == "__main__":
    from math import pow
    with AspectHooks():
        import testmod
    invocations = 0
    def encore(*args, **kwargs):
        global invocations
        invocations += 1
    def loggingaround(next_around, target, *args, **kwargs):
        print("running " + str(target))
        ret = next_around(target, *args, **kwargs)
        print(str(target) + " returned " + str(ret))
        return ret
    def switch_to_power_of_two(next_around, target, *args, **kwargs):
        return next_around(partial(pow, 2), *args, **kwargs)

    def remove_final_statement(steps, *args, **kwargs):
        steps.pop()

    AspectHooks.add_encore(".*", encore)
    AspectHooks.add_around(".*", loggingaround)
    assert testmod.dosomething() is None
    assert testmod.Calc().triple(4) == 12

    assert testmod.double(5) == 10
    AspectHooks.add_around("double", switch_to_power_of_two)
    assert testmod.double(5) == 32

    AspectHooks.add_fuzzer('triple', remove_final_statement)
    assert testmod.Calc().triple(5) is None

    assert invocations == 5

