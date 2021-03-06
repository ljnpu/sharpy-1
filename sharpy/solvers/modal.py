"""
@modified   Alfonso del Carre
"""

import ctypes as ct
import numpy as np
import scipy as sc
import os
import itertools
import warnings
from tvtk.api import tvtk, write_data
import scipy.linalg
import matplotlib.pyplot as plt

import sharpy.structure.utils.xbeamlib as xbeamlib
from sharpy.utils.solver_interface import solver, BaseSolver
import sharpy.utils.settings as settings
import sharpy.utils.algebra as algebra



@solver
class Modal(BaseSolver):
    solver_id = 'Modal'

    def __init__(self):
        self.settings_types = dict()
        self.settings_default = dict()

        self.settings_types['print_info'] = 'bool'
        self.settings_default['print_info'] = True

        self.settings_types['folder'] = 'str'
        self.settings_default['folder'] = './output'

        # solution options
        self.settings_types['use_undamped_modes'] = 'bool'  # basis for modal projection
        self.settings_default['use_undamped_modes'] = True

        self.settings_types['NumLambda'] = 'int'  # no. of different modes to retain
        self.settings_default['NumLambda'] = 20  # doubles if use_undamped_modes is False 

        self.settings_types['keep_linear_matrices'] = 'bool'  # attach linear M,C,K matrices to output dictionary
        self.settings_default['keep_linear_matrices'] = True

        # output options
        self.settings_types['write_modes_vtk'] = 'bool'  # write displacements mode shapes in vtk file
        self.settings_default['write_modes_vtk'] = True        

        self.settings_types['print_matrices'] = 'bool'  # print M,C,K matrices to dat file
        self.settings_default['print_matrices'] = False

        self.settings_types['write_dat'] = 'bool'  # write modes shapes/freq./damp. to dat file
        self.settings_default['write_dat'] = True

        self.settings_types['continuous_eigenvalues'] = 'bool'
        self.settings_default['continuous_eigenvalues'] = False

        self.settings_types['dt'] = 'float'
        self.settings_default['dt'] = 0

        self.settings_types['plot_eigenvalues'] = 'bool'
        self.settings_default['plot_eigenvalues'] = False

        self.settings_types['max_rotation_deg'] = 'float'
        self.settings_default['max_rotation_deg'] = 15

        self.settings_types['max_displacement'] = 'float'
        self.settings_default['max_displacement'] = 0.15

        self.data = None
        self.settings = None

        self.folder = None
        self.filename_freq = None
        self.filename_damp = None
        self.filename_shapes = None

    def initialise(self, data, custom_settings=None):
        self.data = data
        if custom_settings is None:
            self.settings = data.settings[self.solver_id]
        else:
            self.settings = custom_settings
        settings.to_custom_types(self.settings,
                                 self.settings_types,
                                 self.settings_default)

        # load info from dyn dictionary
        self.data.structure.add_unsteady_information(
                                            self.data.structure.dyn_dict,
                                            self.data.ts)

        # create folder for containing files if necessary
        if not os.path.exists(self.settings['folder']):
            os.makedirs(self.settings['folder'])
        self.folder = (self.settings['folder'] + '/' +
                       self.data.settings['SHARPy']['case'] +
                       '/beam_modal_analysis/')
        if not os.path.exists(self.folder):
            os.makedirs(self.folder)
        self.filename_freq = (self.folder +
                              'tstep' + ("%06d" % self.data.ts) +
                              '_ModalFrequencies.dat')
        self.filename_damp = (self.folder +
                              'tstep' + ("%06d" % self.data.ts) +
                              '_ModalDamping.dat')
        self.filename_shapes = (self.folder +
                                'tstep' + ("%06d" % self.data.ts) +
                                '_ModalShape')

    def run(self):
        self.data.ts = len(self.data.structure.timestep_info) - 1
        # Initialize matrices
        num_dof = self.data.structure.num_dof.value
        FullMglobal = np.zeros((num_dof, num_dof),
                               dtype=ct.c_double, order='F')
        FullKglobal = np.zeros((num_dof, num_dof),
                               dtype=ct.c_double, order='F')
        FullCglobal = np.zeros((num_dof, num_dof),
                               dtype=ct.c_double, order='F')

        # Obtain the matrices from the fortran library
        xbeamlib.cbeam3_solv_modal(self.data.structure,
                                   self.settings, self.data.ts,
                                   FullMglobal, FullCglobal, FullKglobal)

        # Print matrices
        if self.settings['print_matrices'].value:
            np.savetxt(self.folder + "Mglobal.dat", FullMglobal, fmt='%.12f',
                       delimiter='\t', newline='\n')
            np.savetxt(self.folder + "Cglobal.dat", FullCglobal, fmt='%.12f',
                       delimiter='\t', newline='\n')
            np.savetxt(self.folder + "Kglobal.dat", FullKglobal, fmt='%.12f',
                       delimiter='\t', newline='\n')

        # Check if the damping matrix is zero (issue working)
        if self.settings['use_undamped_modes'].value:
            zero_FullCglobal = True
            for i,j in itertools.product(range(num_dof),range(num_dof)):
                if(np.absolute(FullCglobal[i, j]) > np.finfo(float).eps):
                    zero_FullCglobal = False
                    warnings.warn(
                        'Projecting a system with damping on undamped modal shapes')
                    break
        # Check if the damping matrix is skew-symmetric
        # skewsymmetric_FullCglobal = True
        # for i in range(num_dof):
        #     for j in range(i:num_dof):
        #         if((i==j) and (np.absolute(FullCglobal[i, j]) > np.finfo(float).eps)):
        #             skewsymmetric_FullCglobal = False
        #         elif(np.absolute(FullCglobal[i, j] + FullCglobal[j, i]) > np.finfo(float).eps):
        #             skewsymmetric_FullCglobal = False

        NumLambda = min(self.data.structure.num_dof.value,
                                               self.settings['NumLambda'].value)

        if self.settings['use_undamped_modes'].value:

            # Solve for eigenvalues (with unit eigenvectors)            
            eigenvalues,eigenvectors=np.linalg.eig(
                                       np.linalg.solve(FullMglobal,FullKglobal))
            eigenvectors_left=None
            # Define vibration frequencies and damping
            freq_natural = np.sqrt(eigenvalues)
            order = np.argsort(freq_natural)[:NumLambda]
            freq_natural = freq_natural[order]
            #freq_damped = freq_natural
            eigenvalues = eigenvalues[order]
            eigenvectors = eigenvectors[:,order]
            damping = np.zeros((NumLambda,))

        else:
            # State-space model
            Minv_neg = -np.linalg.inv(FullMglobal)
            A = np.zeros((2*num_dof, 2*num_dof), dtype=ct.c_double, order='F')
            A[range(num_dof), range(num_dof,2*num_dof)] = 1.
            A[num_dof:, :num_dof] = np.dot(Minv_neg, FullKglobal)
            A[num_dof:, num_dof:] = np.dot(Minv_neg, FullCglobal)

            # Solve the eigenvalues problem
            eigenvalues, eigenvectors_left, eigenvectors = \
                sc.linalg.eig(A,left=True,right=True)
            freq_damped = np.abs(eigenvalues)
            damping = np.zeros_like(freq_damped)
            iiflex = freq_damped > 1e-16*np.mean(freq_damped)
            damping[iiflex] = eigenvalues[iiflex].real/freq_damped[iiflex]

            # Order & downselect complex conj:
            # this algorithm assumes that complex conj eigenvalues appear consecutively 
            # in eigenvalues. For symmetrical systems, this relies  on the fact that:
            # - complex conj eigenvalues have the same absolute value (to machine 
            # precision) 
            # - couples of eigenvalues with moltiplicity higher than 1, show larger 
            # numerical difference
            order = np.argsort(freq_damped)[:2*NumLambda]
            freq_damped = freq_damped[order]
            eigenvalues = eigenvalues[order]

            include = np.ones((2*NumLambda,), dtype=np.bool)
            ii = 0
            tol_rel = np.finfo(float).eps * freq_damped[ii]
            while ii < 2*NumLambda:
                # check complex
                if np.abs(eigenvalues[ii].imag) > 0.:
                    if np.abs(eigenvalues[ii+1].real-eigenvalues[ii].real) > tol_rel or\
                       np.abs(eigenvalues[ii+1].imag+eigenvalues[ii].imag) > tol_rel:
                        raise NameError('Complex conjugate expected but not found!')
                    ii += 1
                    try:
                        include[ii] = False
                    except IndexError:
                        pass
                ii += 1
            freq_damped = freq_damped[include]
            eigenvalues = eigenvalues[include]
            if self.settings['continuous_eigenvalues']:
                if self.settings['dt'].value == 0.:
                    raise ValueError('Cannot compute the continuous eigenvalues without a dt value')
                eigenvalues = np.log(eigenvalues)/self.settings['dt'].value

            order = order[include]
            damping = damping[order]
            eigenvectors = eigenvectors[:, order]
            eigenvectors_left = eigenvectors_left[:, order].conj()

        # Scaling
        if self.settings['use_undamped_modes']:
            # mass normalise (diagonalises M and K)
            dfact = np.diag(np.dot(eigenvectors.T, np.dot(FullMglobal, eigenvectors)))
            eigenvectors = (1./np.sqrt(dfact))*eigenvectors
        else:
            # unit normalise (diagonalises A)
            for ii in range(NumLambda):
                fact = 1./np.sqrt(np.dot(eigenvectors_left[:, ii], eigenvectors[:, ii]))
                eigenvectors_left[:, ii] = fact*eigenvectors_left[:, ii]
                eigenvectors[:, ii] = fact*eigenvectors[:, ii]

        # Other terms required for state-space realisation
        # non-zero damping matrix
        if self.settings['use_undamped_modes'] and not(zero_FullCglobal):
            Ccut = np.dot(eigenvectors.T, np.dot(FullCglobal, eigenvectors))
        else:
            Ccut=None

        # forces gain matrix (nodal -> modal)
        if not self.settings['use_undamped_modes']:
            Kin_damp = np.dot(eigenvectors_left[num_dof:, :].T, -Minv_neg)
        else:
            Kin_damp = None

        # # plot eigenvalues
        # fig = plt.figure()
        # plt.scatter(eigenvalues.real, eigenvalues.imag)
        # plt.show()
        # plt.savefig(self.folder + 'eigenvalues.png', transparent=True, bbox_inches='tight')


        # Write dat files
        if self.settings['write_dat'].value:
            np.savetxt(self.folder + "eigenvalues.dat", eigenvalues, fmt='%.12f',
                       delimiter='\t', newline='\n')
            np.savetxt(self.folder + "eigenvectors.dat", eigenvectors[:num_dof].real,
                       fmt='%.12f', delimiter='\t', newline='\n')
            try:
                np.savetxt(self.folder + 'frequencies.dat', freq_damped[:NumLambda],
                           fmt='%e', delimiter='\t', newline='\n')
            except NameError:
                np.savetxt(self.folder + 'frequencies.dat', freq_natural[:NumLambda],
                           fmt='%e', delimiter='\t', newline='\n')
            np.savetxt(self.filename_damp, damping[:NumLambda],
                       fmt='%e', delimiter='\t', newline='\n')

        # Write vtk
        if self.settings['write_modes_vtk'].value:
            write_modes_vtk(
                self.data,
                eigenvectors[:num_dof],
                NumLambda,
                self.filename_shapes,
                self.settings['max_rotation_deg'],
                self.settings['max_displacement'])

        outdict = dict()

        if self.settings['use_undamped_modes']:
            outdict['modes'] = 'undamped'
            outdict['freq_natural'] = freq_natural
            if not zero_FullCglobal:
                outdict['warning'] =\
                    'system with damping: mode shapes and natural frequencies do not account for damping!'
        else: 
            outdict['modes'] = 'damped'
            outdict['freq_damped'] = freq_damped

        outdict['damping'] = damping
        outdict['eigenvalues'] = eigenvalues
        outdict['eigenvectors'] = eigenvectors
        if Ccut is not None:
            outdict['Ccut'] = Ccut
        if Kin_damp is not None:
            outdict['Kin_damp'] = Kin_damp
        if not self.settings['use_undamped_modes']:    
            outdict['eigenvectors_left'] = eigenvectors_left

        if self.settings['keep_linear_matrices'].value:
            outdict['M'] = FullMglobal
            outdict['C'] = FullCglobal
            outdict['K'] = FullKglobal
        self.data.structure.timestep_info[self.data.ts].modal = outdict
        return self.data



def scale_mode(data,eigenvector,rot_max_deg=15,perc_max=0.15):
    '''
    Scales the eigenvector such that:
    -  the maximum change in component of the beam cartesian rotation vector 
    is equal to rot_max_deg degrees.
    - the maximum translational displacement does not exceed perc_max the
    maximum nodal position.

    Warning: if the eigenvector is in state-space form, only the first
    half of the eigenvector is scanned for determining the scaling.
    '''

    ### initialise
    struct=data.structure
    tsstr=data.structure.timestep_info[data.ts]

    jj=0 # structural dofs index
    RotMax=0.0
    RaMax=0.0
    dRaMax=0.0

    for node_glob in range(struct.num_node):
        ### detect bc at node (and no. of dofs)
        bc_here=struct.boundary_conditions[node_glob]
        if bc_here==1: # clamp
            dofs_here=0
            continue
        elif bc_here==-1 or bc_here==0: 
            dofs_here=6
            jj_tra=[jj  ,jj+1,jj+2]
            jj_rot=[jj+3,jj+4,jj+5]
        jj+=dofs_here

        # check for max rotation
        RotMaxHere=np.max(np.abs(eigenvector[jj_rot].real))
        if RotMaxHere>RotMax:
            RotMax=RotMaxHere

        # check for maximum position
        RaNorm=np.linalg.norm(tsstr.pos[node_glob,:] )
        if RaNorm>RaMax:
            RaMax=RaNorm

        # check for maximum displacement
        dRaNorm=np.linalg.norm( eigenvector[jj_tra].real)  
        if dRaNorm>dRaMax:
            dRaMax=dRaNorm

    RotMaxDeg=RotMax*180/np.pi

    if RotMaxDeg>1e-4:
        fact=rot_max_deg/RotMaxDeg
        if dRaMax*fact>perc_max*RaMax:
            fact=perc_max*RaMax/dRaMax
    else:
        fact=perc_max*RaMax/dRaMax
    # correct factor to ensure max disp is perc
    return eigenvector*fact



def get_mode_zeta(data, eigvect):
    ''' 
    Retrieves the UVLM grid nodal displacements associated to the eigenvector 
    eigvect
    '''

    ### initialise
    aero=data.aero
    struct=data.structure
    tsaero=data.aero.timestep_info[data.ts]
    tsstr=data.structure.timestep_info[data.ts]

    num_dof=struct.num_dof.value
    eigvect=eigvect[:num_dof]

    zeta_mode=[]
    for ss in range(aero.n_surf):
        zeta_mode.append(tsaero.zeta[ss].copy())


    jj=0 # structural dofs index
    Cag0=algebra.quat2rot(tsstr.quat)
    Cga0=Cag0.T
    for node_glob in range(struct.num_node):

        ### detect bc at node (and no. of dofs)
        bc_here=struct.boundary_conditions[node_glob]
        if bc_here==1: # clamp
            dofs_here=0
            continue
        elif bc_here==-1 or bc_here==0: 
            dofs_here=6
            jj_tra=[jj  ,jj+1,jj+2]
            jj_rot=[jj+3,jj+4,jj+5]
        jj+=dofs_here

        # retrieve element and local index
        ee,node_loc=struct.node_master_elem[node_glob,:]

        # get original position and crv 
        Ra0=tsstr.pos[node_glob,:]
        psi0=tsstr.psi[ee,node_loc,:]
        Rg0=np.dot(Cga0,Ra0) 
        Cab0=algebra.crv2rot(psi0)
        Cbg0=np.dot(Cab0.T,Cag0)

        # update position and crv of mode
        Ra=tsstr.pos[node_glob,:]+eigvect[jj_tra]
        psi=tsstr.psi[ee,node_loc,:]+eigvect[jj_rot]
        Rg=np.dot(Cga0,Ra)
        Cab=algebra.crv2rot(psi)
        Cbg=np.dot(Cab.T,Cag0)
    

        ### str -> aero mapping
        # some nodes may be linked to multiple surfaces...
        for str2aero_here in aero.struct2aero_mapping[node_glob]:

            # detect surface/span-wise coordinate (ss,nn)
            nn,ss=str2aero_here['i_n'],str2aero_here['i_surf']
            #print('%.2d,%.2d'%(nn,ss))

            # surface panelling
            M=aero.aero_dimensions[ss][0]
            N=aero.aero_dimensions[ss][1]

            for mm in range(M+1):

                # get position of vertex in B FoR
                zetag0=tsaero.zeta[ss][:,mm,nn]   # in G FoR, w.r.t. origin A-G
                Xb=np.dot(Cbg0,zetag0-Rg0)        # in B FoR, w.r.t. origin B

                # update vertex position
                zeta_mode[ss][:,mm,nn]=Rg+np.dot( np.dot(Cga0,Cab),Xb)

    return zeta_mode



def write_modes_vtk(data, eigenvectors, NumLambda, filename_root, 
                                                rot_max_deg=15.,perc_max=0.15):
    '''
    Writes a vtk file for each of the first NumLambda eigenvectors. When these
    are associated to the state-space form of the structural equations, only
    the displacement field is saved.
    '''

    ### initialise
    aero=data.aero
    struct=data.structure
    tsaero=data.aero.timestep_info[data.ts]
    tsstr=data.structure.timestep_info[data.ts]

    num_dof=struct.num_dof.value
    eigenvectors=eigenvectors[:num_dof,:]

    for mode in range(NumLambda):

        # scale eigenvector
        eigvec=eigenvectors[:num_dof,mode]
        eigvec=scale_mode(data,eigvec,rot_max_deg,perc_max)
        zeta_mode=get_mode_zeta(data,eigvec)

        for i_surf in range(tsaero.n_surf):

            # filename=filename_root+"_%06u_%02u.vtu" %(mode,i_surf)
            filename = filename_root + "_%02u_%06u.vtu" % (i_surf, mode)

            dims = tsaero.dimensions[i_surf, :]
            point_data_dim = (dims[0]+1)*(dims[1]+1)  # + (dims_star[0]+1)*(dims_star[1]+1)
            panel_data_dim = (dims[0])*(dims[1])  # + (dims_star[0])*(dims_star[1])

            coords = np.zeros((point_data_dim, 3))
            conn = []
            panel_id = np.zeros((panel_data_dim,), dtype=int)
            panel_surf_id = np.zeros((panel_data_dim,), dtype=int)
            point_struct_id = np.zeros((point_data_dim,), dtype=int)
            point_struct_mag = np.zeros((point_data_dim,), dtype=float)

            counter = -1
            # coordinates of corners
            for i_n in range(dims[1]+1):
                for i_m in range(dims[0]+1):
                    counter += 1
                    coords[counter, :] = zeta_mode[i_surf][:, i_m, i_n]

            counter = -1
            node_counter = -1
            for i_n in range(dims[1] + 1):
                global_counter = aero.aero2struct_mapping[i_surf][i_n]
                for i_m in range(dims[0] + 1):
                    node_counter += 1
                    # point data
                    point_struct_id[node_counter]=global_counter
                    point_struct_mag[node_counter]=\
                        np.linalg.norm(zeta_mode[i_surf][:, i_m, i_n]\
                                            -tsaero.zeta[i_surf][:,i_m,i_n])

                    if i_n < dims[1] and i_m < dims[0]:
                        counter += 1
                    else:
                        continue

                    conn.append([node_counter + 0,
                                 node_counter + 1,
                                 node_counter + dims[0]+2,
                                 node_counter + dims[0]+1])
                    # cell data
                    panel_id[counter] = counter
                    panel_surf_id[counter] = i_surf

            ug = tvtk.UnstructuredGrid(points=coords)
            ug.set_cells(tvtk.Quad().cell_type, conn)
            ug.cell_data.scalars = panel_id
            ug.cell_data.scalars.name = 'panel_n_id'
            ug.cell_data.add_array(panel_surf_id)
            ug.cell_data.get_array(1).name = 'panel_surface_id'

            ug.point_data.scalars = np.arange(0, coords.shape[0])
            ug.point_data.scalars.name = 'n_id'
            ug.point_data.add_array(point_struct_id)
            ug.point_data.get_array(1).name = 'point_struct_id'

            ug.point_data.add_array(point_struct_mag)
            ug.point_data.get_array(2).name = 'point_displacement_magnitude'

            write_data(ug, filename)