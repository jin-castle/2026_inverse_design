#!/usr/bin/env python3
"""
Pattern: adjoint_filters_conic
MEEP adjoint built-in filters: conic_filter, tanh_projection, binary_filter with autograd compatibility
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "adjoint_filters_conic"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    """
    General filter functions to be used in other projection and morphological transform routines.
    """

    from scipy import special

    def _centered(arr, newshape):
        '''Helper function that reformats the padded array of the fft filter operation.

        Borrowed from scipy:
        https://github.com/scipy/scipy/blob/v1.4.1/scipy/signal/signaltools.py#L263-L270
        '''
        # Return the center newshape portion of the array.
        newshape = np.asarray(newshape)
        currshape = np.array(arr.shape)
        startind = (currshape - newshape) // 2
        endind = startind + newshape
        myslice = [slice(startind[k], endind[k]) for k in range(len(endind))]
        return arr[tuple(myslice)]

    def _edge_pad(arr, pad):
    
        # fill sides
        left = npa.tile(arr[0,:],(pad[0][0],1)) # left side
        right = npa.tile(arr[-1,:],(pad[0][1],1)) # right side
        top = npa.tile(arr[:,0],(pad[1][0],1)).transpose() # top side
        bottom = npa.tile(arr[:,-1],(pad[1][1],1)).transpose() # bottom side)
    
        # fill corners
        top_left = npa.tile(arr[0,0], (pad[0][0],pad[1][0])) # top left
        top_right = npa.tile(arr[-1,0], (pad[0][1],pad[1][0])) # top right
        bottom_left = npa.tile(arr[0,-1], (pad[0][0],pad[1][1])) # bottom left
        bottom_right = npa.tile(arr[-1,-1], (pad[0][1],pad[1][1])) # bottom right
    
        out = npa.concatenate((
            npa.concatenate((top_left,top,top_right)),
            npa.concatenate((left,arr,right)),
            npa.concatenate((bottom_left,bottom,bottom_right))    
        ),axis=1)
    
        return out

    def _zero_pad(arr, pad):
    
        # fill sides
        left = npa.tile(0,(pad[0][0],arr.shape[1])) # left side
        right = npa.tile(0,(pad[0][1],arr.shape[1])) # right side
        top = npa.tile(0,(arr.shape[0],pad[1][0])) # top side
        bottom = npa.tile(0,(arr.shape[0],pad[1][1])) # bottom side
    
        # fill corners
        top_left = npa.tile(0, (pad[0][0],pad[1][0])) # top left
        top_right = npa.tile(0, (pad[0][1],pad[1][0])) # top right
        bottom_left = npa.tile(0, (pad[0][0],pad[1][1])) # bottom left
        bottom_right = npa.tile(0, (pad[0][1],pad[1][1])) # bottom right
    
        out = npa.concatenate((
            npa.concatenate((top_left,top,top_right)),
            npa.concatenate((left,arr,right)),
            npa.concatenate((bottom_left,bottom,bottom_right))    
        ),axis=1)
    
        return out

    def simple_2d_filter(x,kernel,Lx,Ly,resolution,symmetries=[]):
        """A simple 2d filter algorithm that is differentiable with autograd.
        Uses a 2D fft approach since it is typically faster and preserves the shape
        of the input and output arrays.
    
        The ffts pad the operation to prevent any circular convolution garbage.

        Parameters
        ----------
        x : array_like (2D)
            Input array to be filtered. Must be 2D.
        kernel : array_like (2D)
            Filter kernel (before the DFT). Must be same size as `x`
        Lx : float
            Length of design region in X direction (in "meep units")
        Ly : float
            Length of design region in Y direction (in "meep units")
        resolution : int
            Resolution of the design grid (not the meep simulation resolution)
        symmetries : list
            Symmetries to impose on the parameter field (either mp.X or mp.Y)
    
        Returns
        -------
        array_like (2D)
            The output of the 2d convolution.
        """
        # Get 2d parameter space shape
        Nx = int(Lx*resolution)
        Ny = int(Ly*resolution)
        (kx,ky) = kernel.shape
    
        # Adjust parameter space shape for symmetries
        if mp.X in symmetries:
            Nx = int(Nx/2)
        if mp.Y in symmetries:
            Ny = int(Ny/2)
    
        # Ensure the input is 2D
        x = x.reshape(Nx,Ny)
    
        # Perform the required reflections for symmetries
        if mp.X in symmetries:
            if kx % 2 == 1:
                x = npa.concatenate((x,x[-1,:][None,:],x[::-1,:]), axis=0)
            else:
                x = npa.concatenate((x,x[::-1,:]), axis=0)
        if mp.Y in symmetries:
            if ky % 2 == 1:
                x = npa.concatenate((x[:,::-1],x[:,-1][:,None],x), axis=1)
            else:
                x = npa.concatenate((x[:,::-1],x), axis=1)
    
        # pad the kernel and input to avoid circular convolution and
        # to ensure boundary conditions are met.
        kernel = _zero_pad(kernel,((kx,kx),(ky,ky)))
        x = _edge_pad(x,((kx,kx),(ky,ky)))
    
        # Transform to frequency domain for fast convolution
        H = npa.fft.fft2(kernel)
        X = npa.fft.fft2(x)
    
        # Convolution (multiplication in frequency domain)
        Y = H * X
    
        # We need to fftshift since we padded both sides if each dimension of our input and kernel.
        y = npa.fft.fftshift(npa.real(npa.fft.ifft2(Y)))
    
        # Remove all the extra padding
        y = _centered(y,(kx,ky))
    
        # Remove the added symmetry domains
        if mp.X in symmetries:
            y = y[0:Nx,:]
        if mp.Y in symmetries:
            y = y[:,-Ny:]
    
        return y 

    def cylindrical_filter(x,radius,Lx,Ly,resolution,symmetries=[]):
        '''A uniform cylindrical filter [1]. Typically allows for sharper transitions. 
    
        Parameters
        ----------
        x : array_like (2D)
            Design parameters
        radius : float
            Filter radius (in "meep units")
        Lx : float
            Length of design region in X direction (in "meep units")
        Ly : float
            Length of design region in Y direction (in "meep units")
        resolution : int
            Resolution of the design grid (not the meep simulation resolution)
        symmetries : list
            Symmetries to impose on the parameter field (either mp.X or mp.Y)

        Returns
        -------
        array_like (2D)
            Filtered design parameters.
    
        References
        ----------
        [1] Lazarov, B. S., Wang, F., & Sigmund, O. (2016). Length scale and manufacturability in 
        density-based topology optimization. Archive of Applied Mechanics, 86(1-2), 189-218.
        '''    
        # Get 2d parameter space shape
        Nx = int(Lx*resolution)
        Ny = int(Ly*resolution)
    
        # Formulate grid over en
    # ─────────────────────────────────────────────────────────

    # figure 자동 저장
    _outputs = []
    if plt.get_fignums():
        _out = savefig_safe(_PATTERN)
        if _out:
            _outputs.append("output.png")

    _elapsed = round(_time.time() - _t0, 2)
    save_result(_PATTERN, outputs=_outputs, elapsed=_elapsed)
    if mp.am_master():
        print(f"[OK] {_PATTERN} ({_elapsed}s) outputs={_outputs}")

except Exception as _e:
    _elapsed = round(_time.time() - _t0, 2)
    save_result(_PATTERN, error=_e, elapsed=_elapsed)
    import traceback
    traceback.print_exc()
    sys.exit(1)
