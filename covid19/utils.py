from pdsf import AspectHooks

class TimedAspectApplicator:
    '''
    Applies aspects on specific ticks or tick ranges.
    '''

    kind_weaver_map = {
        'prelude': AspectHooks.add_prelude,
        'around': AspectHooks.add_around,
        'encore': AspectHooks.add_encore,
        'fuzzer': AspectHooks.add_fuzzer
    }

    def __init__(self, world, toApply):
        '''
        Some required values for managing ticks.
        :param world: the world object being simulated.
        :param toApply: a list of tuples of the form (target_rule, aspect, aspect_kind:string, year:int|range)
        '''
        self.world = world
        self.first_year = world.year_min
        self.dt = world.dt
        self.aspects_to_apply = toApply
        # A list of tuples of the form (time, remover, application_rule), where:
        #     time is the required time for an aspect to be applied (either int year or range [start, end) years),
        #     remover is a lambda which removes it when executed,
        #     application_rule is a rule defining the aspect's application, to be added back to self.aspects_to_apply (in the case of ranges with gaps)
        self.currently_appled_aspects = list()

    def _should_be_applied(self, curr_year, time):
        '''
        Determines whether an aspect to be applied at `time` should be applied in `curr_year`.
        Cleans things up because `time` can be an int or a range of times.
        :param curr_year: integer current year
        :param time: int year to apply aspect, or range of int years to apply aspect (list of start and end times, inclusive of start and exclusive of end)
        :return: bool representing applicability at current simulated time.
        '''
        if isinstance(time, int):
            return curr_year == time
        else:
            return curr_year >= time[0] and curr_year < time[1]

    def __call__(self, target, *args, **kwargs):
        '''
        Acts as a prelude to pyworld3 ticking.
        Ticks are identified by calls to loop0_<sector>, loopk_<sector>, or _loopk_world3_fast .
        This applies aspects according to the _year_ of the simulation (translating ticks to years).
        pointcut should be "^_?loop[0k]_.*"
        :param target: the target being applied to.
        :param args: args for the target
        :param kwargs: kwargs for the target
        :return:
        '''

        # The loop0s don't get ticks, but we can identify them by their arguments:
        #     they take only self and an optional bool.
        #     The bool is only applied when running individual sectors, which we don't support.
        # Others get a tick as their first argument, so this is easily identified.
        if len(args) <= 1:
            tick = 0
        else:
            tick = args[2]

        year = tick * self.dt + self.first_year

        applied = list()

        # Check whether each rule should be applied.
        for application_rule in self.aspects_to_apply:
            target_rule, aspect, kind, time = application_rule  # Deconstruct the application rule
            if self._should_be_applied(year, time):
                # If it should, find the right method to weave it using the kind:weaver map, weave it, and keep the remover lambda so we can unweave later.
                weaver = TimedAspectApplicator.kind_weaver_map[kind]
                remover = weaver(target_rule, aspect)
                self.currently_appled_aspects.append((time, remover, application_rule))

                applied.append(application_rule)  # To avoid changing the length of self.aspects_to_apply during iteration

        # un-apply anything that shouldn't be woven anymore
        to_forget = list()
        for applied_advice in self.currently_appled_aspects:
            time, remover, application_rule = applied_advice
            if not self._should_be_applied(year, time):
                remover()
                self.aspects_to_apply.append(application_rule)
                to_forget.append(applied_advice)
        for applied_advice in to_forget:
            self.currently_appled_aspects.remove(applied_advice)

        # Avoid applying again --- the removal loop will replace this if needs be.
        for application_rule in applied:
            self.aspects_to_apply.remove(application_rule)

