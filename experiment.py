from pyworld3.utils import plot_world_variables
import matplotlib.pyplot as plt
from covid19 import *

from pdsf import AspectHooks
AspectHooks.permitted_depth = 3
AspectHooks.treat_rules_as_dynamic = True
with AspectHooks():
    import pyworld3



world3 = pyworld3.World3()  # choose the time limits and step.
world3.init_world3_constants()  # choose the model constants.
world3.init_world3_variables()  # initialize all variables.
world3.set_world3_table_functions()  # get tables from a json file.
world3.set_world3_delay_functions()  # initialize delay functions.

def mutated_experimental_frame():

    # aspect_applicator = TimedAspectApplicator(world3, [(".*update_m.*", runs_5_times, 'fuzzer', [2000, 2004])])
    aspect_applicator = TimedAspectApplicator(world3, [(".*update_m[123].*", IoannidisMortalityGeneric, 'fuzzer', [2020, 2024]),
                                                       (".*update_m4.*", IoannidisMortalityGeneric, 'fuzzer', [2020, 10000]),
                                                       (".*update_iopc.*", HiscottEconomicEffect().econ_effect, 'fuzzer', [2020, 10000])])
    AspectHooks.add_prelude("^_?loop[0k]_.*", aspect_applicator)

    world3.run_world3(fast=True)
    plot_world_variables(world3.time,
                         [world3.nrfr, world3.iopc, world3.fpc, world3.pop,
                          world3.ppolx],
                         ["NRFR", "IOPC", "FPC", "POP", "PPOLX"],
                         [[0, 1], [0, 1e3], [0, 1e3], [0, 16e9], [0, 32]],
                         figsize=(7, 5),
                         grid=1,
                         title="World3 COVID19 run")

    plt.show(block=True)
    plt.savefig("world3_covid19.png")

def reference_experimental_frame():

    world3.run_world3(fast=True)
    plot_world_variables(world3.time,
                         [world3.nrfr, world3.iopc, world3.fpc, world3.pop,
                          world3.ppolx],
                         ["NRFR", "IOPC", "FPC", "POP", "PPOLX"],
                         [[0, 1], [0, 1e3], [0, 1e3], [0, 16e9], [0, 32]],
                         figsize=(7, 5),
                         grid=1,
                         title="World3 unmodified run")

    plt.show(block=True)
    plt.savefig("world3_unmodified.png")

if __name__ == "__main__":
    reference_experimental_frame()
    mutated_experimental_frame()