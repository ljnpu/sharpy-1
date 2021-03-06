import h5py as h5
import numpy as np
import configparser
import os
import sharpy.utils.algebra as algebra

case_name = 'coupled_configuration_DARPA'
route = os.path.dirname(os.path.realpath(__file__)) + '/'

m_main = 3
amplitude = 0.0
period = 3
dt_factor = 1

# flight conditions
u_inf = 25
rho = 0.0891
alpha = 4.5
beta = 0
sweep = 0*np.pi/180.
dihedral = 0*np.pi/180.
aspect_ratio = 16  # = total wing span (chord = 1)

alpha_rad = alpha*np.pi/180

dt = 1.0/m_main/u_inf*dt_factor
num_steps = int(3./dt)
# num_steps = 250

# main geometry data
main_span = 16
main_chord = 1.0
main_ea = 0.5
main_sigma = 0.5
main_airfoil_P = 0
main_airfoil_M = 0

fuselage_length = 6
fuselage_sigma = 6
fuselage_mass_sigma = 0.5

tail_span = 4.0
tail_chord = 1
tail_ea = 0.33
tail_sigma = 1
tail_mass_sigma = 0.5
tail_airfoil_P = 5
tail_airfoil_M = 5
tail_twist = -1.5*np.pi/180

fin_span = 2.5
fin_chord = 1
fin_ea = 0.33
fin_sigma = 1
fin_mass_sigma = 0.5
fin_airfoil_P = 0
fin_airfoil_M = 0

n_surfaces = 5
force = 0
momenty = 0
momentx = 0

# discretisation data
num_elem_main = 5
num_elem_tail = 4
num_elem_fin = 4
num_elem_fuselage = 3


num_node_elem = 3
num_elem = num_elem_main + num_elem_main + num_elem_fuselage + num_elem_tail + num_elem_tail + num_elem_fin
num_node_main = num_elem_main*(num_node_elem - 1) + 1
num_node_fuselage = num_elem_fuselage*(num_node_elem - 1) + 1
num_node_tail = num_elem_tail*(num_node_elem - 1) + 1
num_node_fin = num_elem_fin*(num_node_elem - 1) + 1

num_node = num_node_main + (num_node_main - 1)
num_node += num_node_fuselage - 1
num_node += (num_node_tail - 1)
num_node += (num_node_tail - 1)
num_node += num_node_fin - 1
# nodes_distributed = num_node

m_tail = 3
m_fin = 3


def clean_test_files():
    fem_file_name = route + '/' + case_name + '.fem.h5'
    if os.path.isfile(fem_file_name):
        os.remove(fem_file_name)

    dyn_file_name = route + '/' + case_name + '.dyn.h5'
    if os.path.isfile(dyn_file_name):
        os.remove(dyn_file_name)

    aero_file_name = route + '/' + case_name + '.aero.h5'
    if os.path.isfile(aero_file_name):
        os.remove(aero_file_name)

    solver_file_name = route + '/' + case_name + '.solver.txt'
    if os.path.isfile(solver_file_name):
        os.remove(solver_file_name)

    flightcon_file_name = route + '/' + case_name + '.flightcon.txt'
    if os.path.isfile(flightcon_file_name):
        os.remove(flightcon_file_name)


def generate_fem_file():
    # placeholders
    # coordinates
    global x, y, z
    x = np.zeros((num_node, ))
    y = np.zeros((num_node, ))
    z = np.zeros((num_node, ))
    # struct twist
    structural_twist = np.zeros_like(x)
    # beam number
    beam_number = np.zeros((num_elem, ), dtype=int)
    # frame of reference delta
    frame_of_reference_delta = np.zeros((num_elem, num_node_elem, 3))
    # connectivities
    conn = np.zeros((num_elem, num_node_elem), dtype=int)
    # stiffness
    num_stiffness = 4
    ea = 1e5
    ga = 1e5
    gj = 1e5
    eiy = 2e4
    eiz = 5e6
    sigma = 50
    sigma = 25
    base_stiffness = sigma*np.diag([ea, ga, ga, gj, eiy, eiz])
    stiffness = np.zeros((num_stiffness, 6, 6))
    stiffness[0, :, :] = main_sigma*base_stiffness
    stiffness[1, :, :] = fuselage_sigma*base_stiffness
    stiffness[2, :, :] = tail_sigma*base_stiffness
    stiffness[3, :, :] = fin_sigma*base_stiffness
    elem_stiffness = np.zeros((num_elem,), dtype=int)
    # mass
    num_mass = 4
    m_base = 0.75
    j_base = 0.1
    base_mass = np.diag([m_base, m_base, m_base, j_base, 0.01, 0.01])
    mass = np.zeros((num_mass, 6, 6))
    mass[0, :, :] = np.sqrt(main_sigma)*base_mass
    mass[1, :, :] = fuselage_mass_sigma*base_mass
    mass[2, :, :] = tail_mass_sigma*base_mass
    mass[3, :, :] = fin_mass_sigma*base_mass
    elem_mass = np.zeros((num_elem,), dtype=int)
    # boundary conditions
    boundary_conditions = np.zeros((num_node, ), dtype=int)
    boundary_conditions[0] = 1
    # applied forces
    app_forces = np.zeros((num_node, 6))

    # lumped masses
    n_lumped_mass = 1
    lumped_mass_nodes = np.array([0], dtype=int)
    lumped_mass = np.zeros((n_lumped_mass, ))
    lumped_mass_inertia = np.zeros((n_lumped_mass, 3, 3))
    lumped_mass_position = np.zeros((n_lumped_mass, 3))

    # right wing (beam 0) --------------------------------------------------------------
    working_elem = 0
    working_node = 0
    beam_number[working_elem:working_elem + num_elem_main] = 0
    y[working_node:working_node + num_node_main] = np.linspace(0.0, np.cos(dihedral)*main_span, num_node_main)
    z[working_node:working_node + num_node_main] = np.linspace(0.0, np.sin(dihedral)*main_span, num_node_main)
    for ielem in range(num_elem_main):
        for inode in range(num_node_elem):
            frame_of_reference_delta[working_elem + ielem, inode, :] = [-1, 0, 0]
    # connectivity
    for ielem in range(num_elem_main):
        conn[working_elem + ielem, :] = ((np.ones((3,))*(working_elem + ielem)*(num_node_elem - 1)) +
                                         [0, 2, 1])
    elem_stiffness[working_elem:working_elem + num_elem_main] = 0
    elem_mass[working_elem:working_elem + num_elem_main] = 0
    boundary_conditions[0] = 1
    boundary_conditions[working_node + num_node_main - 1] = -1
    app_forces[0, 1] = 80
    lumped_mass_position[0, 1] = 1.0
    lumped_mass[0] = 5
    working_elem += num_elem_main
    working_node += num_node_main


    # left wing (beam 1) --------------------------------------------------------------
    beam_number[working_elem:working_elem + num_elem_main] = 1
    # tempy = np.linspace(0.0, -main_span, num_node_main)
    tempy = np.linspace(-np.cos(dihedral)*main_span, 0.0, num_node_main)
    tempz = np.linspace(np.sin(dihedral)*main_span, 0.0, num_node_main)
    y[working_node:working_node + num_node_main - 1] = tempy[0:-1]
    z[working_node:working_node + num_node_main - 1] = tempz[0:-1]
    for ielem in range(num_elem_main):
        for inode in range(num_node_elem):
            frame_of_reference_delta[working_elem + ielem, inode, :] = [-1, 0, 0]
    # connectivity
    for ielem in range(num_elem_main):
        conn[working_elem + ielem, :] = ((np.ones((3,))*(working_elem + ielem)*(num_node_elem - 1)) +
                                         [0, 2, 1]) + 1
    conn[working_elem + num_elem_main - 1, 1] = 0
    elem_stiffness[working_elem:working_elem + num_elem_main] = 0
    elem_mass[working_elem:working_elem + num_elem_main] = 0
    boundary_conditions[working_node] = -1
    working_elem += num_elem_main
    working_node += num_node_main - 1

    # fuselage (beam 2) --------------------------------------------------------------
    beam_number[working_elem:working_elem + num_elem_fuselage] = 2
    tempx = np.linspace(0.0, fuselage_length, num_node_fuselage)
    x[working_node:working_node + num_node_fuselage - 1] = tempx[1:]
    for ielem in range(num_elem_fuselage):
        for inode in range(num_node_elem):
            frame_of_reference_delta[working_elem + ielem, inode, :] = [0, 1, 0]
    # connectivity
    for ielem in range(num_elem_fuselage):
        conn[working_elem + ielem, :] = ((np.ones((3,))*(working_elem + ielem)*(num_node_elem - 1)) +
                                         [0, 2, 1])
    conn[working_elem, 0] = 0
    elem_stiffness[working_elem:working_elem + num_elem_fuselage] = 1
    elem_mass[working_elem:working_elem + num_elem_fuselage] = 1
    # node_app_forces[2] = working_node + num_node_fuselage - 1 - 1
    # app_forces[2, :] = [0, 0, force, 0, 0, 0]
    # 60 nodes, 29 elems
    working_elem += num_elem_fuselage
    working_node += num_node_fuselage - 1
    global end_of_fuselage_node
    end_of_fuselage_node = working_node - 1
    #
    # #
    # # # fin (beam 3) --------------------------------------------------------------
    beam_number[working_elem:working_elem + num_elem_fin] = 3
    tempz = np.linspace(0.0, fin_span, num_node_fin)
    x[working_node:working_node + num_node_fin - 1] = x[working_node - 1]
    z[working_node:working_node + num_node_fin - 1] = tempz[1:]
    for ielem in range(num_elem_fin):
        for inode in range(num_node_elem):
            frame_of_reference_delta[working_elem + ielem, inode, :] = [-1, 0, 0]
    # connectivity
    for ielem in range(num_elem_fin):
        conn[working_elem + ielem, :] = ((np.ones((3,))*(working_elem + ielem)*(num_node_elem - 1)) +
                                         [0, 2, 1])
    conn[working_elem, 0] = end_of_fuselage_node
    elem_stiffness[working_elem:working_elem + num_elem_fin] = 3
    elem_mass[working_elem:working_elem + num_elem_fin] = 3
    working_elem += num_elem_fin
    working_node += num_node_fin - 1
    end_of_fin_node = working_node - 1
    # # right tail (beam 4) --------------------------------------------------------------
    beam_number[working_elem:working_elem + num_elem_tail] = 4
    tempy = np.linspace(0.0, tail_span, num_node_tail)
    z[working_node:working_node + num_node_tail - 1] = z[working_node - 1]
    y[working_node:working_node + num_node_tail - 1] = tempy[1:]
    x[working_node:working_node + num_node_tail - 1] = x[working_node - 1]
    for ielem in range(num_elem_tail):
        for inode in range(num_node_elem):
            frame_of_reference_delta[working_elem + ielem, inode, :] = [-1, 0, 0]
    # connectivity
    for ielem in range(num_elem_tail):
        conn[working_elem + ielem, :] = ((np.ones((3,))*(working_elem + ielem)*(num_node_elem - 1)) +
                                         [0, 2, 1])
    conn[working_elem, 0] = conn[working_elem - 1, 1]
    elem_stiffness[working_elem:working_elem + num_elem_tail] = 2
    elem_mass[working_elem:working_elem + num_elem_fuselage] = 2
    boundary_conditions[working_node + num_node_tail - 1 - 1] = -1
    # 70 nodes, 34 elems
    working_elem += num_elem_tail
    working_node += num_node_tail - 1
    #
    # # left tail (beam 5) --------------------------------------------------------------
    beam_number[working_elem:working_elem + num_elem_tail] = 5
    tempy = np.linspace(-tail_span, 0, num_node_tail)
    z[working_node:working_node + num_node_tail - 1] = z[working_node - 1]
    y[working_node:working_node + num_node_tail - 1] = tempy[:-1]
    x[working_node:working_node + num_node_tail - 1] = x[working_node - 1]
    for ielem in range(num_elem_tail):
        for inode in range(num_node_elem):
            frame_of_reference_delta[working_elem + ielem, inode, :] = [-1, 0, 0]
    # connectivity
    for ielem in range(num_elem_tail):
        conn[working_elem + ielem, :] = ((np.ones((3,))*(working_elem + ielem)*(num_node_elem - 1)) +
                                         [0, 2, 1]) + 1
    conn[working_elem + num_elem_tail - 1, 1] = end_of_fin_node
    elem_stiffness[working_elem:working_elem + num_elem_tail] = 2
    elem_mass[working_elem:working_elem + num_elem_fuselage] = 2
    boundary_conditions[working_node] = -1
    # node_app_forces[2] = working_node + num_node_tail - 2
    # app_forces[2, :] = [0, 0, 0*force, 0, 0, 0]
    working_elem += num_elem_tail
    working_node += num_node_tail - 1

    with h5.File(route + '/' + case_name + '.fem.h5', 'a') as h5file:
        coordinates = h5file.create_dataset('coordinates', data=np.column_stack((x, y, z)))
        conectivities = h5file.create_dataset('connectivities', data=conn)
        num_nodes_elem_handle = h5file.create_dataset(
            'num_node_elem', data=num_node_elem)
        num_nodes_handle = h5file.create_dataset(
            'num_node', data=num_node)
        num_elem_handle = h5file.create_dataset(
            'num_elem', data=num_elem)
        stiffness_db_handle = h5file.create_dataset(
            'stiffness_db', data=stiffness)
        stiffness_handle = h5file.create_dataset(
            'elem_stiffness', data=elem_stiffness)
        mass_db_handle = h5file.create_dataset(
            'mass_db', data=mass)
        mass_handle = h5file.create_dataset(
            'elem_mass', data=elem_mass)
        frame_of_reference_delta_handle = h5file.create_dataset(
            'frame_of_reference_delta', data=frame_of_reference_delta)
        structural_twist_handle = h5file.create_dataset(
            'structural_twist', data=structural_twist)
        bocos_handle = h5file.create_dataset(
            'boundary_conditions', data=boundary_conditions)
        beam_handle = h5file.create_dataset(
            'beam_number', data=beam_number)
        app_forces_handle = h5file.create_dataset(
            'app_forces', data=app_forces)
        lumped_mass_nodes_handle = h5file.create_dataset(
            'lumped_mass_nodes', data=lumped_mass_nodes)
        lumped_mass_handle = h5file.create_dataset(
            'lumped_mass', data=lumped_mass)
        lumped_mass_inertia_handle = h5file.create_dataset(
            'lumped_mass_inertia', data=lumped_mass_inertia)
        lumped_mass_position_handle = h5file.create_dataset(
            'lumped_mass_position', data=lumped_mass_position)


def generate_dyn_file():
    global dt
    global num_steps
    global route
    global case_name
    global num_elem
    global num_node_elem
    global num_node
    global amplitude
    global period

    dynamic_forces_time = None
    with_dynamic_forces = False
    with_forced_vel = False
    if with_dynamic_forces:
        angle = np.arctan(8.0/6.0)
        m1 = 80
        f1 = 8
        dynamic_forces = np.zeros((num_node, 6))
        app_node = int(0)
        dynamic_forces[app_node, 0] = -f1*np.cos(angle)
        dynamic_forces[app_node, 1] = -f1*np.sin(angle)
        dynamic_forces[app_node, 5] = m1
        force_time = np.zeros((num_steps, ))
        limit = round(2.5/dt)
        force_time[:limit] = 1

        dynamic_forces_time = np.zeros((num_steps, num_node, 6))
        for it in range(num_steps):
            dynamic_forces_time[it, :, :] = force_time[it]*dynamic_forces

    forced_for_vel = None
    if with_forced_vel:
        forced_for_vel = np.zeros((num_steps, 6))
        forced_for_acc = np.zeros((num_steps, 6))
        for it in range(num_steps):
            forced_for_vel[it, 2] = 2*np.pi/period*amplitude*np.sin(2*np.pi*dt*it/period)
            forced_for_acc[it, 2] = (2*np.pi/period)**2*amplitude*np.cos(2*np.pi*dt*it/period)
            # forced_for_vel[it, 2] = 2*np.pi/period*np.pi/180*amplitude*np.cos(2*np.pi*dt*it/period)

    with h5.File(route + '/' + case_name + '.dyn.h5', 'a') as h5file:
        if with_dynamic_forces:
            h5file.create_dataset(
                'dynamic_forces', data=dynamic_forces_time)
        if with_forced_vel:
            h5file.create_dataset(
                'for_vel', data=forced_for_vel)
            h5file.create_dataset(
                'for_acc', data=forced_for_acc)
        h5file.create_dataset(
            'num_steps', data=num_steps)


def generate_aero_file():
    global x, y, z
    airfoil_distribution = np.zeros((num_elem, num_node_elem), dtype=int)
    surface_distribution = np.zeros((num_elem,), dtype=int) - 1
    surface_m = np.zeros((n_surfaces, ), dtype=int)
    m_distribution = 'uniform'
    aero_node = np.zeros((num_node,), dtype=bool)
    twist = np.zeros((num_node,))
    chord = np.zeros((num_node,))
    elastic_axis = np.zeros((num_node,))

    working_elem = 0
    working_node = 0
    # right wing (surface 0, beam 0)
    i_surf = 0
    airfoil_distribution[working_elem:working_elem + num_elem_main, :] = 0
    surface_distribution[working_elem:working_elem + num_elem_main] = i_surf
    surface_m[i_surf] = m_main
    aero_node[working_node:working_node + num_node_main] = True
    chord[working_node:working_node + num_node_main] = main_chord
    elastic_axis[working_node:working_node + num_node_main] = main_ea
    working_elem += num_elem_main
    working_node += num_node_main

    # left wing (surface 1, beam 1)
    i_surf = 1
    # airfoil_distribution[working_node:working_node + num_node_main - 1] = 0
    airfoil_distribution[working_elem:working_elem + num_elem_main, :] = 0
    surface_distribution[working_elem:working_elem + num_elem_main] = i_surf
    surface_m[i_surf] = m_main
    aero_node[working_node:working_node + num_node_main - 1] = True
    chord[working_node:working_node + num_node_main - 1] = main_chord
    elastic_axis[working_node:working_node + num_node_main - 1] = main_ea
    working_elem += num_elem_main
    working_node += num_node_main - 1

    working_elem += num_elem_fuselage
    working_node += num_node_fuselage - 1 - 1

    # fin (surface 2, beam 3)
    i_surf = 2
    # airfoil_distribution[working_node:working_node + num_node_fin] = 0
    airfoil_distribution[working_elem:working_elem + num_elem_fin, :] = 0
    surface_distribution[working_elem:working_elem + num_elem_fin] = i_surf
    surface_m[i_surf] = m_fin
    aero_node[working_node:working_node + num_node_fin] = True
    chord[working_node:working_node + num_node_fin] = fin_chord
    twist[end_of_fuselage_node] = 0
    twist[working_node:] = 0
    elastic_axis[working_node:working_node + num_node_main] = fin_ea
    working_elem += num_elem_fin
    working_node += num_node_fin

    # # right tail (surface 3, beam 4)
    i_surf = 3
    # airfoil_distribution[working_node:working_node + num_node_tail] = 1
    airfoil_distribution[working_elem:working_elem + num_elem_tail, :] = 0
    surface_distribution[working_elem:working_elem + num_elem_tail] = i_surf
    surface_m[i_surf] = m_tail
    # XXX not very elegant
    aero_node[working_node:] = True
    chord[working_node:working_node + num_node_tail] = tail_chord
    elastic_axis[working_node:working_node + num_node_main] = tail_ea
    twist[working_node:working_node + num_node_tail] = -tail_twist
    working_elem += num_elem_tail
    working_node += num_node_tail

    # left tail (surface 4, beam 5)
    i_surf = 4
    airfoil_distribution[working_elem:working_elem + num_elem_tail, :] = 1
    surface_distribution[working_elem:working_elem + num_elem_tail] = i_surf
    surface_m[i_surf] = m_tail
    aero_node[working_node:working_node + num_node_tail - 1] = True
    chord[working_node:working_node + num_node_tail] = tail_chord
    elastic_axis[working_node:working_node + num_node_main] = tail_ea
    twist[working_node:working_node + num_node_tail-1] = -tail_twist
    working_elem += num_elem_tail
    working_node += num_node_tail


    with h5.File(route + '/' + case_name + '.aero.h5', 'a') as h5file:
        airfoils_group = h5file.create_group('airfoils')
        # add one airfoil
        naca_airfoil_main = airfoils_group.create_dataset('0', data=np.column_stack(
                                generate_naca_camber(P=main_airfoil_P, M=main_airfoil_M)))
        naca_airfoil_tail = airfoils_group.create_dataset('1', data=np.column_stack(
            generate_naca_camber(P=tail_airfoil_P, M=tail_airfoil_M)))
        naca_airfoil_fin = airfoils_group.create_dataset('2', data=np.column_stack(
            generate_naca_camber(P=0, M=0)))

        # chord
        chord_input = h5file.create_dataset('chord', data=chord)
        dim_attr = chord_input .attrs['units'] = 'm'

        # twist
        twist_input = h5file.create_dataset('twist', data=twist)
        dim_attr = twist_input.attrs['units'] = 'rad'

        # airfoil distribution
        airfoil_distribution_input = h5file.create_dataset('airfoil_distribution', data=airfoil_distribution)

        surface_distribution_input = h5file.create_dataset('surface_distribution', data=surface_distribution)
        surface_m_input = h5file.create_dataset('surface_m', data=surface_m)
        m_distribution_input = h5file.create_dataset('m_distribution', data=m_distribution.encode('ascii', 'ignore'))

        aero_node_input = h5file.create_dataset('aero_node', data=aero_node)
        elastic_axis_input = h5file.create_dataset('elastic_axis', data=elastic_axis)


def generate_naca_camber(M=0, P=0):
    m = M*1e-2
    p = P*1e-1
    def naca(x, m, p):
        if x < 1e-6:
            return 0.0
        elif x < p:
            return m/(p*p)*(2*p*x - x*x)
        elif x > p and x < 1+1e-6:
            return m/((1-p)*(1-p))*(1 - 2*p + 2*p*x - x*x)

    x_vec = np.linspace(0, 1, 1000)
    y_vec = np.array([naca(x, m, p) for x in x_vec])
    return x_vec, y_vec


def generate_solver_file(horseshoe=False):
    file_name = route + '/' + case_name + '.solver.txt'
    # config = configparser.ConfigParser()
    import configobj
    config = configobj.ConfigObj()
    config.filename = file_name
    config['SHARPy'] = {'case': case_name,
                        'route': route,
                        'flow': ['BeamLoader',
                                 'AerogridLoader',
                                 'StaticCoupled',
                                 'DynamicCoupled',
                                 # 'DynamicPrescribedCoupled',
                                 'AerogridPlot',
                                 'BeamPlot',
                                 'AeroForcesCalculator',
                                 'BeamCsvOutput'],
                        'write_screen': 'on',
                        'write_log': 'on',
                        'log_folder': os.path.dirname(__file__) + '/output/',
                        'log_file': case_name + '.log'}
    config['BeamLoader'] = {'unsteady': 'on',
                            'orientation': algebra.euler2quat(np.array([0.0,
                                                                        alpha_rad,
                                                                        beta*np.pi/180]))}

    config['StaticCoupled'] = {'print_info': 'on',
                               'structural_solver': 'NonLinearStatic',
                               'structural_solver_settings': {'print_info': 'off',
                                                              'max_iterations': 150,
                                                              'num_load_steps': 10,
                                                              'delta_curved': 1e-5,
                                                              'min_delta': 1e-5,
                                                              'gravity_on': 'on',
                                                              'gravity': 9.81,
                                                              'orientation': algebra.euler2quat(np.array([0.0,
                                                                                                          alpha_rad,
                                                                                                          beta*np.pi/180]))},
                               'aero_solver': 'StaticUvlm',
                               'aero_solver_settings': {'print_info': 'off',
                                                        'horseshoe': 'off',
                                                        'num_cores': 4,
                                                        'n_rollup': 0,
                                                        'rollup_dt': main_chord/m_main/u_inf,
                                                        'rollup_aic_refresh': 1,
                                                        'rollup_tolerance': 1e-4,
                                                        'velocity_field_generator': 'SteadyVelocityField',
                                                        'velocity_field_input': {'u_inf': u_inf,
                                                                                 'u_inf_direction': [1., 0, 0]},
                                                        'rho': rho,
                                                        'alpha': alpha_rad,
                                                        'beta': beta},
                               'max_iter': 80,
                               'n_load_steps': 8,
                               'tolerance': 1e-4,
                               'relaxation_factor': 0.1}
    config['DynamicCoupled'] = {'print_info': 'on',
                                'structural_solver': 'NonLinearDynamicCoupledStep',
                                'structural_solver_settings': {'print_info': 'off',
                                                               'max_iterations': 150,
                                                               'num_load_steps': 20,
                                                               'delta_curved': 1e-5,
                                                               'min_delta': 1e-5,
                                                               'newmark_damp': 5e-4,
                                                               'gravity_on': 'on',
                                                               'gravity': 9.81,
                                                               'num_steps': num_steps,
                                                               'dt': dt},
                                'aero_solver': 'StepUvlm',
                                'aero_solver_settings': {'print_info': 'off',
                                                         'horseshoe': 'off',
                                                         'num_cores': 4,
                                                         'n_rollup': 100,
                                                         'convection_scheme': 3,
                                                         'rollup_dt': main_chord/m_main/u_inf,
                                                         'rollup_aic_refresh': 1,
                                                         'rollup_tolerance': 1e-4,
                                                         'velocity_field_generator': 'GustVelocityField',
                                                         'velocity_field_input': {'u_inf': u_inf,
                                                                                  'u_inf_direction': [1., 0, 0],
                                                                                  'gust_shape': 'DARPA',
                                                                                  'gust_length': 20,
                                                                                  'gust_intensity': 0.3*u_inf,
                                                                                  'offset': 20.0,
                                                                                  'span': main_span},
                                                         'rho': rho,
                                                         'alpha': alpha_rad,
                                                         'beta': beta,
                                                         'n_time_steps': num_steps,
                                                         'dt': dt},
                                'max_iter': 100,
                                'tolerance': 1e-6,
                                'relaxation_factor': 0.,
                                'n_time_steps': num_steps,
                                'dt': dt,
                                'structural_substeps': 1}
    config['DynamicPrescribedCoupled'] = {'print_info': 'on',
                                          'structural_solver': 'NonLinearDynamicPrescribedStep',
                                          'structural_solver_settings': {'print_info': 'off',
                                                                         'max_iterations': 150,
                                                                         'num_load_steps': 15,
                                                                         'delta_curved': 1e-5,
                                                                         'min_delta': 1e-5,
                                                                         'newmark_damp': 5e-4,
                                                                         'gravity_on': 'on',
                                                                         'gravity': 9.754,
                                                                         'num_steps': num_steps,
                                                                         'dt': dt},
                                          'aero_solver': 'StepUvlm',
                                          'aero_solver_settings': {'print_info': 'off',
                                                                   'horseshoe': 'off',
                                                                   'num_cores': 4,
                                                                   'n_rollup': 50,
                                                                   'convection_scheme': 3,
                                                                   'rollup_dt': main_chord/m_main/u_inf,
                                                                   'rollup_aic_refresh': 1,
                                                                   'rollup_tolerance': 1e-4,
                                                                   'velocity_field_generator': 'SteadyVelocityField',
                                                                   'velocity_field_input': {'u_inf': u_inf,
                                                                                            'u_inf_direction': [1., 0, 0]},
                                                                   'rho': rho,
                                                                   'alpha': alpha_rad,
                                                                   'beta': beta,
                                                                   'n_time_steps': num_steps,
                                                                   'dt': dt},
                                          'max_iter': 100,
                                          'tolerance': 1e-6,
                                          'relaxation_factor': 0.,
                                          'n_time_steps': num_steps,
                                          'dt': dt}

    if horseshoe is True:
        config['AerogridLoader'] = {'unsteady': 'on',
                                    'aligned_grid': 'on',
                                    'mstar': 1,
                                    'freestream_dir': ['1', '0', '0']}
    else:
        config['AerogridLoader'] = {'unsteady': 'on',
                                    'aligned_grid': 'on',
                                    'mstar': 60,
                                    'freestream_dir': ['1', '0', '0']}
    config['AerogridPlot'] = {'folder': os.path.dirname(__file__) + '/output/',
                              'include_rbm': 'on',
                              'include_forward_motion': 'on',
                              'include_applied_forces': 'on',
                              'minus_m_star': 0,
                              'u_inf': u_inf,
                              'dt': dt
                              }
    config['AeroForcesCalculator'] = {'folder': os.path.dirname(__file__) + '/output/forces',
                                      'write_text_file': 'on',
                                      'text_file_name': case_name + '_aeroforces.csv',
                                      'screen_output': 'on',
                                      'unsteady': 'off'
                                      }
    config['BeamPlot'] = {'folder': os.path.dirname(__file__) + '/output/',
                          'include_rbm': 'on',
                          'include_applied_forces': 'on',
                          'include_forward_motion': 'on'}
    config['BeamCsvOutput'] = {'folder': os.path.dirname(__file__) + '/output/',
                               'output_pos': 'on',
                               'output_psi': 'on',
                               'screen_output': 'off'}
    config.write()


clean_test_files()
generate_fem_file()
generate_dyn_file()
generate_solver_file(horseshoe=False)
generate_aero_file()
