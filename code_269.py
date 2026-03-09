# -*- coding: utf-8 -*-
from collections import namedtuple
import warnings

import numpy as np

import meep as mp
from meep.geom import Vector3, init_do_averaging
from meep.source import EigenModeSource, check_positive


# ------------------------------------------------------- #
# Visualization
# ------------------------------------------------------- #
# Contains all necesarry visualation routines for use with
# pymeep and pympb.

# ------------------------------------------------------- #
# Functions used to define the default plotting parameters
# for the different plotting routines.

default_source_parameters = {
        'color':'r',
        'edgecolor':'r',
        'facecolor':'none',
        'hatch':'/',
        'linewidth':2
    }

default_monitor_parameters = {
        'color':'b',
        'edgecolor':'b',
        'facecolor':'none',
        'hatch':'/',
        'linewidth':2
    }

default_field_parameters = {
        'interpolation':'spline36',
        'cmap':'RdBu',
        'alpha':0.6,
        'post_process':np.real
        }

default_eps_parameters = {
        'interpolation':'spline36',
        'cmap':'binary',
        'alpha':1.0,
        'contour':False,
        'contour_linewidth':1
    }

default_boundary_parameters = {
        'color':'g',
        'edgecolor':'g',
        'facecolor':'none',
        'hatch':'/'
    }

default_volume_parameters = {
        'alpha':1.0,
        'color':'k',
        'linestyle':'-',
        'linewidth':1,
        'marker':'.',
        'edgecolor':'k',
        'facecolor':'none',
        'hatch':'/'
    }

default_label_parameters = {
    'label_color':'r',
    'offset':20,
    'label_alpha':0.3
}

# Used to remove the elements of a dictionary (dict_to_filter) that
# don't correspond to the keyword arguments of a particular
# function (func_with_kwargs.)
# Adapted from https://stackoverflow.com/questions/26515595/how-does-one-ignore-unexpected-keyword-arguments-passed-to-a-function/44052550
def filter_dict(dict_to_filter, func_with_kwargs):
    import inspect
    filter_keys = []
    try:
        # Python3 ...
        sig = inspect.signature(func_with_kwargs)
        filter_keys = [param.name for param in sig.parameters.values() if param.kind == param.POSITIONAL_OR_KEYWORD]
    except:
        # Python2 ...
        filter_keys = inspect.getargspec(func_with_kwargs)[0]

    filtered_dict = {filter_key:dict_to_filter[filter_key] for filter_key in filter_keys if filter_key in dict_to_filter}
    return filtered_dict

# ------------------------------------------------------- #
# Routines to add legends to plot

def place_label(ax,label_text,x,y,centerx,centery,label_parameters=None):

    label_parameters = default_label_parameters if label_parameters is None else dict(default_label_parameters, **label_parameters)

    offset = label_parameters['offset']
    alpha = label_parameters['label_alpha']
    color = label_parameters['label_color']

    if x > centerx:
        xtext = -offset
    else:
        xtext = offset
    if y > centery:
        ytext = -offset
    else:
        ytext = offset

    ax.annotate(label_text, xy=(x, y), xytext=(xtext,ytext),
            textcoords='offset points', ha='center', va='bottom',
            bbox=dict(boxstyle='round,pad=0.2', fc=color, alpha=alpha),
            arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0.5',
                            color=color))
    return ax

# ------------------------------------------------------- #
# Helper functions used to plot volumes on a 2D plane

# Returns the intersection points of 2 Volumes.
# Volumes must be a line, plane, or rectangular prism
# (since they are volume objects)
def intersect_volume_volume(volume1,volume2):
    # volume1 ............... [volume]
    # volume2 ............... [volume]

    # Represent the volumes by an "upper" and "lower" coordinate
    U1 = [volume1.center.x+volume1.size.x/2,volume1.center.y+volume1.size.y/2,volume1.center.z+volume1.size.z/2]
    L1 = [volume1.center.x-volume1.size.x/2,volume1.center.y-volume1.size.y/2,volume1.center.z-volume1.size.z/2]

    U2 = [volume2.center.x+volume2.size.x/2,volume2.center.y+volume2.size.y/2,volume2.center.z+volume2.size.z/2]
    L2 = [volume2.center.x-volume2.size.x/2,volume2.center.y-volume2.size.y/2,volume2.center.z-volume2.size.z/2]

    # Evaluate intersection
    U = np.min([U1,U2],axis=0)
    L = np.max([L1,L2],axis=0)

    # For single points we have to check manually
    if np.all(U-L == 0):
        if (not volume1.pt_in_volume(Vector3(*U))) or (not volume2.pt_in_volume(Vector3(*U))):
            return []

    # Check for two volumes that don't intersect
    if np.any(U-L < 0):
        return []

    # Pull all possible vertices
    vertices = []
    for x_vals in [L[0],U[0]]:
        for y_vals in [L[1],U[1]]:
            for z_vals in [L[2],U[2]]:
                vertices.append(Vector3(x_vals,y_vals,z_vals))

    # Remove any duplicate points caused by coplanar lines
    vertices = [vertices[i] for i, x in enumerate(vertices) if x not in vertices[i+1:]]

    return vertices

# All of the 2D plotting routines need an output plane over which to plot.
# The user has many options to specify this output plane. They can pass
# the output_plane parameter, which is a 2D volume object. They can specify
# a volume using in_volume, which stores the volume as a C volume, not a python
# volume. They can also do nothing and plot the XY plane through Z=0.
#
# Not only do we need to check for all of these possibilities, but we also need
# to check if the user accidentally specifies a plane that stretches beyond the
# simulation domain.
def get_2D_dimensions(sim,output_plane):
    from meep.simulation import Volume

    # Pull correct plane from user
    if output_plane:
        plane_center, plane_size = (output_plane.center, output_plane.size)
    elif sim.output_volume:
        plane_center, plane_size = mp.get_center_and_size(sim.output_volume)
    else:
        plane_center, plane_size = (sim.geometry_center, sim.cell_size)
    plane_volume = Volume(center=plane_center,size=plane_size)

    if plane_size.x!=0 and plane_size.y!=0 and plane_size.z!=0:
        raise ValueError("Plane volume must be 2D (a plane).")

    check_volume = Volume(center=sim.geometry_center,size=sim.cell_size)

    vertices = intersect_volume_volume(check_volume,plane_volume)

    if len(vertices) == 0:
        raise ValueError("The specified user volume is completely outside of the simulation domain.")

    intersection_vol = Volume(vertices=vertices)

    if (intersection_vol.size != plane_volume.size) or (intersection_vol.center != plane_volume.center):
        warnings.warn('The specified user volume is larger than the simulation domain and has been truncated.')

    sim_center, sim_size = (intersection_vol.center, intersection_vol.size)
    return sim_center, sim_size

# ------------------------------------------------------- #
# actual plotting routines

def plot_volume(sim,ax,volume,output_plane=None,plotting_parameters=None,label=None):
    if not sim._is_initialized:
        sim.init_sim()

    import matplotlib.patches as patches
    from matplotlib import pyplot as plt
    from meep.simulation import Volume

    # Set up the plotting parameters
    plotting_parameters = default_volume_parameters if plotting_parameters is None else dict(default_volume_parameters, **plotting_parameters)

    # Get domain measurements
    sim_center, sim_size = get_2D_dimensions(sim,output_plane)

    plane = Volume(center=sim_center,size=sim_size)

    # Pull volume parameters
    size = volume.size
    center = volume.center

    xmax = center.x+size.x/2
    xmin = center.x-size.x/2
    ymax = center.y+size.y/2
    ymin = center.y-size.y/2
    zmax = center.z+size.z/2
    zmin = center.z-size.z/2

    # Add labels if requested
    if label is not None and mp.am_master():
        if sim_size.x == 0:
            ax = place_label(ax,label,center.y,center.z,sim_center.y,sim_cente