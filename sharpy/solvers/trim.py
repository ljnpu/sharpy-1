import ctypes as ct
import numpy as np
import scipy.optimize
import warnings

import sharpy.aero.utils.mapping as mapping
import sharpy.utils.cout_utils as cout
import sharpy.utils.solver_interface as solver_interface
from sharpy.utils.solver_interface import solver, BaseSolver
import sharpy.utils.settings as settings
import sharpy.utils.algebra as algebra


@solver
class Trim(BaseSolver):
    solver_id = 'Trim'

    def __init__(self):
        self.settings_types = dict()
        self.settings_default = dict()

        self.settings_types['print_info'] = 'bool'
        self.settings_default['print_info'] = True

        self.settings_types['solver'] = 'str'
        self.settings_default['solver'] = None

        self.settings_types['solver_settings'] = 'dict'
        self.settings_default['solver_settings'] = None

        self.settings_types['max_iter'] = 'int'
        self.settings_default['max_iter'] = 100

        self.settings_types['tolerance'] = 'float'
        self.settings_default['tolerance'] = 1e-4

        self.settings_types['initial_alpha'] = 'float'
        self.settings_default['initial_alpha'] = 0*np.pi/180.

        self.settings_types['initial_beta'] = 'float'
        self.settings_default['initial_beta'] = 0*np.pi/180.

        self.settings_types['initial_roll'] = 'float'
        self.settings_default['initial_roll'] = 0*np.pi/180.

        self.settings_types['cs_indices'] = 'list(int)'
        self.settings_default['cs_indices'] = np.array([])

        self.settings_types['initial_cs_deflection'] = 'list(float)'
        self.settings_default['initial_cs_deflection'] = np.array([])

        self.settings_types['thrust_nodes'] = 'list(int)'
        self.settings_default['thrust_nodes'] = np.array([0])

        self.settings_types['initial_thrust'] = 'list(float)'
        self.settings_default['initial_thrust'] = np.array([1.])

        self.settings_types['thrust_direction'] = 'list(float)'
        self.settings_default['thrust_direction'] = np.array([.0, 1.0, 0.0])

        self.settings_types['special_case'] = 'dict'
        self.settings_default['special_case'] = dict()

        self.settings_types['refine_solution'] = 'bool'
        self.settings_default['refine_solution'] = False

        self.data = None
        self.settings = None
        self.solver = None

        self.x_info = dict()
        self.initial_state = None

        self.with_special_case = False

    def initialise(self, data):
        self.data = data
        self.settings = data.settings[self.solver_id]
        settings.to_custom_types(self.settings, self.settings_types, self.settings_default)

        self.solver = solver_interface.initialise_solver(self.settings['solver'])
        self.solver.initialise(self.data, self.settings['solver_settings'])

        # generate x_info (which elements of the x array are what)
        counter = 0
        self.x_info['n_variables'] = 0
        # alpha
        self.x_info['i_alpha'] = counter
        counter += 1
        # beta
        self.x_info['i_beta'] = counter
        counter += 1
        # roll
        self.x_info['i_roll'] = counter
        counter += 1
        # control surfaces
        n_control_surfaces = len(self.settings['cs_indices'])
        self.x_info['i_control_surfaces'] = []  # indices in the state vector
        self.x_info['control_surfaces_id'] = []  # indices of the trimmed control surfaces
        for i_cs in range(n_control_surfaces):
            self.x_info['i_control_surfaces'].append(counter)
            self.x_info['control_surfaces_id'].append(self.settings['cs_indices'][i_cs])
            counter += 1
        # thrust
        n_thrust_nodes = len(self.settings['thrust_nodes'])
        self.x_info['i_thrust'] = []
        self.x_info['thrust_nodes'] = []
        self.x_info['thrust_direction'] = []
        for i_thrust in range(n_thrust_nodes):
            self.x_info['i_thrust'].append(counter)
            self.x_info['thrust_nodes'].append(self.settings['thrust_nodes'][i_thrust])
            self.x_info['thrust_direction'].append(self.settings['thrust_direction'])
            counter += 1
        self.x_info['n_variables'] = counter

        # special cases
        self.with_special_case = self.settings['special_case']
        if self.with_special_case:
            if self.settings['special_case']['case_name'] == 'differential_thrust':
                self.x_info['special_case'] = 'differential_thrust'
                self.x_info['i_base_thrust'] = counter
                counter += 1
                self.x_info['i_differential_parameter'] = counter
                counter += 1
                self.x_info['initial_base_thrust'] = self.settings['special_case']['initial_base_thrust']
                self.x_info['initial_differential_parameter'] = self.settings['special_case']['initial_differential_parameter']
                self.x_info['base_thrust_nodes'] = [int(e) for e in self.settings['special_case']['base_thrust_nodes']]
                self.x_info['negative_thrust_nodes'] = [int(e) for e in self.settings['special_case']['negative_thrust_nodes']]
                self.x_info['positive_thrust_nodes'] = [int(e) for e in self.settings['special_case']['positive_thrust_nodes']]

            self.x_info['n_variables'] = counter


        # initial state vector
        self.initial_state = np.zeros(self.x_info['n_variables'])
        self.initial_state[self.x_info['i_alpha']] = self.settings['initial_alpha'].value
        self.initial_state[self.x_info['i_beta']] = self.settings['initial_beta'].value
        self.initial_state[self.x_info['i_roll']] = self.settings['initial_roll'].value
        for i_cs in range(n_control_surfaces):
            self.initial_state[self.x_info['i_control_surfaces'][i_cs]] = self.settings['initial_cs_deflection'][i_cs]
        for i_thrust in range(n_thrust_nodes):
            self.initial_state[self.x_info['i_thrust'][i_thrust]] = self.settings['initial_thrust'][i_thrust]
        if self.with_special_case:
            if self.settings['special_case']['case_name'] == 'differential_thrust':
                self.initial_state[self.x_info['i_base_thrust']] = self.x_info['initial_base_thrust']
                self.initial_state[self.x_info['i_differential_parameter']] = self.x_info['initial_differential_parameter']


        # bounds
        # NOTE probably not necessary anymore, as Nelder-Mead method doesn't use them
        self.bounds = self.x_info['n_variables']*[None]
        for k, v in self.x_info.items():
            if k == 'i_alpha':
                self.bounds[v] = (self.initial_state[self.x_info['i_alpha']] - 3*np.pi/180,
                                  self.initial_state[self.x_info['i_alpha']] + 3*np.pi/180)
            elif k == 'i_beta':
                self.bounds[v] = (self.initial_state[self.x_info['i_beta']] - 2*np.pi/180,
                                  self.initial_state[self.x_info['i_beta']] + 2*np.pi/180)
            elif k == 'i_roll':
                self.bounds[v] = (self.initial_state[self.x_info['i_roll']] - 2*np.pi/180,
                                  self.initial_state[self.x_info['i_roll']] + 2*np.pi/180)
            elif k == 'i_thrust':
                for ii, i in enumerate(v):
                    self.bounds[i] = (self.initial_state[self.x_info['i_thrust'][ii]] - 2,
                                      self.initial_state[self.x_info['i_thrust'][ii]] + 2)
            elif k == 'i_control_surfaces':
                for ii, i in enumerate(v):
                    self.bounds[i] = (self.initial_state[self.x_info['i_control_surfaces'][ii]] - 4*np.pi/180,
                                      self.initial_state[self.x_info['i_control_surfaces'][ii]] + 4*np.pi/180)
            elif k == 'i_base_thrust':
                if self.with_special_case:
                    if self.settings['special_case']['case_name'] == 'differential_thrust':
                        self.bounds[v] = (float(self.x_info['initial_base_thrust'])*0.5,
                                          float(self.x_info['initial_base_thrust'])*1.5)
            elif k == 'i_differential_parameter':
                if self.with_special_case:
                    if self.settings['special_case']['case_name'] == 'differential_thrust':
                        self.bounds[v] = (-0.5, 0.5)

    def increase_ts(self):
        self.data.ts += 1
        self.structural_solver.next_step()
        self.aero_solver.next_step()

    def cleanup_timestep_info(self):
        if max(len(self.data.aero.timestep_info), len(self.data.structure.timestep_info)) > 1:
            # copy last info to first
            self.data.aero.timestep_info[0] = self.data.aero.timestep_info[-1]
            self.data.structure.timestep_info[0] = self.data.structure.timestep_info[-1]
            # delete all the rest
            while len(self.data.aero.timestep_info) - 1:
                del self.data.aero.timestep_info[-1]
            while len(self.data.structure.timestep_info) - 1:
                del self.data.structure.timestep_info[-1]

        self.data.ts = 0

    def run(self):
        self.trim_algorithm()
        return self.data

    def trim_algorithm(self):
        # create bounds

        # call optimiser
        self.optimise(solver_wrapper,
                      tolerance=self.settings['tolerance'].value,
                      print_info=True,
                      # method='BFGS')
                      method='Nelder-Mead',
                      # method='SLSQP',
                      refine=self.settings['refine_solution'])

        # self.optimise(self.solver_wrapper, )
        pass

    def optimise(self, func, tolerance, print_info, method, refine):
        args = (self.x_info, self, -2)

        solution = scipy.optimize.minimize(func,
                                           self.initial_state,
                                           args=args,
                                           method=method,
                                           options={'disp': print_info,
                                                    'maxfev': 1000,
                                                    'xatol': tolerance,
                                                    'fatol': 1e-4})
        if refine:
            cout.cout_wrap('Refining results with a gradient-based method', 1)
            solution = scipy.optimize.minimize(func,
                                               solution.x,
                                               args=args,
                                               method='BFGS',
                                               options={'disp': print_info,
                                                        'eps': 0.05,
                                                        'maxfev': 5000,
                                                        'fatol': 1e-4})

        cout.cout_wrap('Solution = ')
        cout.cout_wrap(solution.x)
        # pretty_print_x(x, x_info)
        return solution


# def pretty_print_x(x, x_info):
#     cout.cout_wrap('X vector:', 1)
#     for k, v in x_info:
#         if k.startswith('i_'):
#             if isinstance(v, list):
#                 for i, vv in v:
#                     cout.cout_wrap(k + ' ' + str(i) + ': ', vv)
#             else:
#                 cout.cout_wrap(k + ': ', v)


def solver_wrapper(x, x_info, solver_data, i_dim=-1):
    if solver_data.settings['print_info']:
        cout.cout_wrap('x = ' + str(x), 1)
    # print('x = ', x)
    alpha = x[x_info['i_alpha']]
    beta = x[x_info['i_beta']]
    roll = x[x_info['i_roll']]
    # change input data
    solver_data.data.structure.timestep_info[solver_data.data.ts] = solver_data.data.structure.ini_info.copy()
    tstep = solver_data.data.structure.timestep_info[solver_data.data.ts]
    aero_tstep = solver_data.data.aero.timestep_info[solver_data.data.ts]
    orientation_quat = algebra.euler2quat(np.array([roll, alpha, beta]))
    tstep.quat[:] = orientation_quat
    # control surface deflection
    for i_cs in range(len(x_info['i_control_surfaces'])):
        solver_data.data.aero.aero_dict['control_surface_deflection'][x_info['control_surfaces_id'][i_cs]] = x[x_info['i_control_surfaces'][i_cs]]
    # thrust input
    tstep.steady_applied_forces[:] = 0.0
    try:
        x_info['special_case']
    except KeyError:
        for i_thrust in range(len(x_info['i_thrust'])):
            thrust = x[x_info['i_thrust'][i_thrust]]
            i_node = x_info['thrust_nodes'][i_thrust]
            solver_data.data.structure.ini_info.steady_applied_forces[i_node, 0:3] = thrust*x_info['thrust_direction'][i_thrust]
    else:
        if x_info['special_case'] == 'differential_thrust':
            base_thrust = x[x_info['i_base_thrust']]
            pos_thrust = base_thrust*(1.0 + x[x_info['i_differential_parameter']])
            neg_thrust = -base_thrust*(1.0 - x[x_info['i_differential_parameter']])
            for i_base_node in x_info['base_thrust_nodes']:
                solver_data.data.structure.ini_info.steady_applied_forces[i_base_node, 1] = base_thrust
            for i_pos_diff_node in x_info['positive_thrust_nodes']:
                solver_data.data.structure.ini_info.steady_applied_forces[i_pos_diff_node, 1] = pos_thrust
            for i_neg_diff_node in x_info['negative_thrust_nodes']:
                solver_data.data.structure.ini_info.steady_applied_forces[i_neg_diff_node, 1] = neg_thrust

    # run the solver
    solver_data.solver.run()
    # extract resultants
    forces, moments = solver_data.solver.extract_resultants()

    totals = np.zeros((6,))
    totals[0:3] = forces
    totals[3:6] = moments
    if solver_data.settings['print_info']:
        cout.cout_wrap(' forces = ' + str(totals), 1)
    # print('total forces = ', totals)
    # try:
    #     totals += x[x_info['i_none']]
    # except KeyError:
    #     pass
    # return resultant forces and moments
    # return np.linalg.norm(totals)
    if i_dim >= 0:
        return totals[i_dim]
    elif i_dim == -1:
        # return [np.sum(totals[0:3]**2), np.sum(totals[4:6]**2)]
        return totals
    elif i_dim == -2:
        coeffs = np.array([1.0, 1.0, 1.0, 2, 2, 2])
        # print('return = ', np.dot(coeffs*totals, coeffs*totals))
        if solver_data.settings['print_info']:
            cout.cout_wrap(' val = ' + str(np.dot(coeffs*totals, coeffs*totals)), 1)
        return np.dot(coeffs*totals, coeffs*totals)
