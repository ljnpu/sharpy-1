# import os
# import time
#
# import sharpy.utils.cout_utils as cout
# import sharpy.utils.input_arg as input_arg
# import sharpy.utils.sharpydir as sharpydir
# import sharpy.utils.solver_interface as solver_interface
# from sharpy.presharpy.presharpy import PreSharpy
#
# from sharpy.presharpy.presharpy import PreSharpy
# # Loading solvers and postprocessors
# import sharpy.solvers
# import sharpy.postproc
# import sharpy.generators
# # ------------
import sharpy.utils.cout_utils as cout
import sys


def main(args):
    """
    Main ``SHARPy`` routine

    This is the main ``SHARPy`` routine.
    It starts the solution process by reading the settings that are included in the ``.solver.txt`` file that is parsed
    as an argument.
    It reads the solvers specific settings and runs them in order

    Args:
        args (str): ``.solver.txt`` file with the problem information and settings

    Returns:
        ``PreSharpy`` class object

    """
    import time

    import sharpy.utils.input_arg as input_arg
    import sharpy.utils.solver_interface as solver_interface
    from sharpy.presharpy.presharpy import PreSharpy
    from sharpy.utils.cout_utils import start_writer, finish_writer
    # Loading solvers and postprocessors
    import sharpy.solvers
    import sharpy.postproc
    import sharpy.generators
    # ------------

    # output writer
    start_writer()
    # timing
    t = time.process_time()

    settings = input_arg.read_settings(args)

    # Loop for the solvers specified in *.solver.txt['SHARPy']['flow']
    # run preSHARPy
    data = PreSharpy(settings)
    for solver_name in settings['SHARPy']['flow']:
        solver = solver_interface.initialise_solver(solver_name)
        solver.initialise(data)
        data = solver.run()

    elapsed_time = time.process_time() - t
    cout.cout_wrap('FINISHED - Elapsed time = %f6 seconds' % elapsed_time, 2)
    finish_writer()
    return data
