from ast import *

times = 0

def runs_5_times(steps, *args, **kwargs):
    '''
    This is just a little proof of concept to remind me how to write these things.
    :param steps:
    :param args:
    :param kwargs:
    :return:
    '''
    global times
    toprint = "\nI've ran " + str(times) + " times!\n"
    times += 1
    print_iterations = copy_location(Expr(Call(func=Name('print', Load()),
                                 args=[Constant(toprint)],
                                 keywords=[])), steps[0])
    steps = [print_iterations] + steps
    [fix_missing_locations(step) for step in steps]
    return steps


def IoannidisMortalityGeneric(steps, *args, **kwargs):
    '''
    In ioannidis 2020, "Global perspective of COVID-19 epidemiology for a full-cycle pandemic", which predicts around
        1.5% of global total deaths over a four year period due to covid in their "plausible" scenario.
    To be applied to _update_m<n> in the population sector.
    :param steps: steps in an AST
    :param args: arguments for the target
    :param kwargs: keyword args for the target
    :return: mutated steps representing the 1.5% shift
    '''
    steps[1].value = copy_location(BinOp(steps[1].value, Mult(), Constant(1.03)), steps[1])
    steps.append(copy_location(Expr(Call(func=Name('print', Load()),
                                               args=[Constant("=====\nIn a fuzzed mortality function.\n=====")],
                                               keywords=[])), steps[0]))
    fix_missing_locations(steps[1])
    fix_missing_locations(steps[2])
    return steps

class HiscottEconomicEffect:
    '''
    Assumes a quite naive 3.8% impact on economy which reduces by 20% year-on-year.
    We assume economic impact is best represented by modifying IOPC (industrial output per capita)
         => TODO revisit this assumption.

    '''

    effect_decay = 0.2

    def __init__(self):
        self.current_impact = 0.038

    def econ_effect(self, steps, *args, **kwwargs):
        steps[1].value = copy_location(BinOp(steps[1].value, Mult(), Constant(1-self.current_impact)), steps[1])
        steps.append(copy_location(Expr(Call(func=Name('print', Load()),
                                             args=[Constant("=====\nIn a fuzzed industrial output function.\n=====")],
                                             keywords=[])), steps[0]))
        fix_missing_locations(steps[1])
        fix_missing_locations(steps[2])

        self.current_impact = self.current_impact * (1-HiscottEconomicEffect.effect_decay)

        return steps

