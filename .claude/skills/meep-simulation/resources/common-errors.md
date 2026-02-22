# Common MEEP/MPB Errors & Solutions

_자동 생성 (meep-kb DB)_

## ADJOINT

### `Unable to display the figure of the adjoint example-CrossRouter.py`
**Solution:** I'm trying to familiar with how to use adjoint solver on Meep and have met some problems when running the example script of CrossRouter.py.

After several tries, I still couldn't work out how to remove the below warning and thought this might be the reason why the figure of this example couldn't be displayed. 

Visualization.py:347: FutureWarning: elementwise comparison failed; returning scalar instead, but in the future will perform elementwise comparison
  if options['fill_color'] != 'none': # first copy: faces, no edges

Any help would be very appreciated. 

**Ref:** https://github.com/NanoComp/meep/issues/1124

### ``test_adjoint_solver.py` failing due to autograd-related error`
**Solution:**                     self.design_region_resolution,
**Ref:** https://github.com/NanoComp/meep/issues/2539

## CONVERGENCE

### `Guile deprecated features`
**Solution:** SCM_VECTORP is deprecated.  Use scm_is_vector instead.
SCM_VECTOR_LENGTH is deprecated.  Use scm_c_vector_length instead.
```

```$ guile
GNU Guile 2.0.11
Copyright (C) 1995-2014 Free Software Foundation, Inc.

Guile comes with ABSOLUTELY NO WARRANTY; for details type `,show w'.
**Ref:** https://github.com/NanoComp/meep/issues/16

### `documentation regarding implementation of symmetries`
**Solution:**   // loop over symmetry transformations of the chunks:
  for (int sn = 0; sn < (use_symmetry ? S.multiplicity() : 1); ++sn) {
    component cS = S.transform(cgrid, -sn);
    ivec iyee_cS(S.transform_unshifted(iyee_c, -sn));

    volume gvS = S.transform(gv.surroundings(), sn);
    vec L(gv.dim);
    ivec iL(gv.dim);

**Ref:** https://github.com/NanoComp/meep/issues/405

### `accessing members of object returned by get-eigenmode-coefficients in Scheme`
**Solution:** The Scheme function [`get-eigenmode-coefficients`](https://github.com/NanoComp/meep/blob/master/scheme/meep.scm.in#L1125-L1139), which is currently missing from the [documentation](https://meep.readthedocs.io/en/latest/Scheme_User_Interface), returns a list of typed arrays containing the mode coefficients, group velocities, and wavevectors similar to [`get_eigenmode_coefficients`](https://meep.readthedocs.io/en/latest/Python_User_Interface/#mode-decomposition) of Python. However, unlike the Python version, accessing members of the Scheme object requires knowledge of the internal data structure. To streamline the functionality of `get-eigenmode-coefficients` in order to make it consistent with Python, the returned object should be a simple list of lists such that the individual elements can be accessed using e.g. `list-ref`. As a demonstration, the following script is the Scheme version of the straight waveguide normalization run from the [waveguide mode converter tutorial example](http
**Ref:** https://github.com/NanoComp/meep/issues/709

### `improve performance of writing HDF5 files in parallel simulations `
**Solution:** I believe the correct code in h5file::write(const char *dataname, const char *data) should be:

  if (IF_EXCLUSIVE(am_master(), 1)) {
    hid_t file_id = HID(get_id()), type_id, data_id, space_id;

    CHECK(file_id >= 0, "error opening HDF5 output file");

    remove_data(dataname); // HDF5 gives error if we H5Dcreate existing dataset

**Ref:** https://github.com/NanoComp/meep/issues/738

### `On cygwin, make meep got error when make scheme : #error need --with-maintainer-mode to generate this file`
**Solution:** (echo "// AUTOMATICALLY GENERATED -- DO NOT EDIT"; grep -h friend ../src/meep.hpp ../src/meep/vec.hpp ../src/meep/mympi.hpp | perl -pe 's/^ *friend +[A-Za-z_0-9:<>]+[* ]+([A-Za-z_0-9:]*) *\(.*$/%ignore \1;/' | grep "%ignore" | sort -u;) > meep_swig_bug_workaround.i
(perl -pe 's/%rename\(([A-Za-z0-9_]*)\) *([A-Za-z0-9:_]*);$/(define \2 (\1))/' meep_enum_renames.i | perl -pe 's/[A-Za-z0-9:_]*:://g' | perl -pe 's/_/-/g' | perl -pe 's,//,;,'; echo "(define Centered Dielectric)") > meep-enums.scm
echo "#error need --with-maintainer-mode to generate this file" 1>&2
#error need --with-maintainer-mode to generate this file
exit 1
make[2]: *** [Makefile:915: meep_wrap.cxx] Error 1
make[2]: Leaving directory '/home/Genlin/meep-1.8.0/scheme'
make[1]: *** [Makefile:506: all-recursive] Error 1
make[1]: Leaving directory '/home/Genlin/meep-1.8.0'
**Ref:** https://github.com/NanoComp/meep/issues/767

### `python2 compatibility of MPB tests?`
**Solution:** In Python 2, however, isn't this wrong because it does truncated integer division?  It seems like all of these tests and examples should use `mp.Vector3(-1./3, 1./3)` and similar.

(It surprises me that the MPB tests pass in Python 2.)
**Ref:** https://github.com/NanoComp/meep/issues/772

### `Problem with load_minus_flux_data in parallel simulations`
**Solution:** I am finding that parallel simulations with Python interface give wrong results when I use the function 'load_minus_flux_data'. I have found a [closed issue about this problem](https://github.com/NanoComp/meep/issues/463) but the bug persists for release [v1.11.0](https://github.com/NanoComp/meep/releases/tag/v1.11.0).

If necessary, I can provide my simulation code but the bug can be reproduced with the original code reported on issue 463. Only a small change is required, on lines 60, from:
```python
coeffs, vgrp, kpoints = sim.get_eigenmode_coefficients(refl_flux,[1],eig_parity=mp.ODD_Z+mp.EVEN_Y)
```
to:
```python
coeffs, vgrp, kpoints, kdom = sim.get_eigenmode_coefficients(refl_flux,[1],eig_parity=mp.ODD_Z+mp.EVEN_Y)
**Ref:** https://github.com/NanoComp/meep/issues/1044

### `Calculating eigenmode coefficient scaling`
**Solution:** In theory, if I wanted to calculate this (i.e. for adjoint sims), I should be able to use the group velocity returned by `get_eigenmode_coefficients` and a brute force calculation of the mode volume. I can't seem to reconcile results, however, with what the internals of `get_eigenmode_coefficients`:

https://github.com/NanoComp/meep/blob/93be1abd83e507d4f8becba8bef0da002526b947/src/mpb.cpp#L811

I'm assuming my calculation of the mode volume is different from meep's. Is there a routine (maybe through swig) that can calculate this given a volume object? It's also possible that meep does some additional normalization on the group velocity that I'm not aware of...

Currently, I'm doing the brute force mode-mode overlap integral and am getting matching results. It would be nice to skip this step, however, and just use quantities from the API.
**Ref:** https://github.com/NanoComp/meep/issues/1107

### `Incomplete simulation results!`
**Solution:** around only 13 to 20 time steps are calculated. Ideally 333 time steps should have been calculated.
errors shownin _a.out_ are:
`ERROR: In procedure %run-finalizers:`
`ERROR: In procedure delete-meep-volume: Wrong type argument in position 1: #<finalized smob 561534af3d00>`

In both the cases I ran the control files without any changes to the scripts. 
I have attached screenshot containing some system informations. If more information is needed, I will be happy to provide. Thank you in advance.
![Screenshot from 2020-02-09 01-25-20](https://user-images.githubusercontent.com/36835879/74091239-573b0380-4adb-11ea-8a14-aa7a1e1a58f4.png)

**Ref:** https://github.com/NanoComp/meep/issues/1119

### `Python: progress tracking error with `bend-flux.py` tutorial`
**Solution:** Computational cell is 16 x 32 x 0 with resolution 10
     block, center = (0,-11.5,0)
          size (1e+20,1,1e+20)
          axes (1,0,0), (0,1,0), (0,0,1)
          dielectric constant epsilon diagonal = (12,12,12)
time for set_epsilon = 0.21156 s
-----------
field decay(t = 50.050000000000004): 4.825189380557793e-09 / 4.825189380557793e-09 = 1.0
on time step 1773 (time=88.65), 0.00225686 s/step
**Ref:** https://github.com/NanoComp/meep/issues/1160

## GENERAL

### `Request for updating Meep on Ubuntu`
**Solution:** I am using Meep on Ubuntu. I was trying to use the step function "dft-ldos", but I got an error saying "Unbound variable: dft-ldos". Later, I found out that MEEP on Ubuntu is outdated (current version is 1.1.1, http://packages.ubuntu.com/trusty/meep). This update would appeal to many people currently using Ubuntu. 

Thank you.

**Ref:** https://github.com/NanoComp/meep/issues/10

### `Simulating Very Large Strucutres`
**Solution:** My simulation runs for lower resolutions but when I increase the resolution I get this error
meep: Cannot split -287473792 grid points into 3 parts

I would like to simulate structures as large as 150 * lambda but I get similar errors.

Thank you, 
Mahdad.
**Ref:** https://github.com/NanoComp/meep/issues/186

### `PML documentation incorrect for Python`
**Solution:** I left `strength` out of python because the scheme interface had this comment:
```scheme
  (define-property strength 1.0 'number) ; obsolete: R -> R^strength
```
The Python docs probably want a more detailed description of this.
**Ref:** https://github.com/NanoComp/meep/issues/338

### `ZeroDivisionError in _disp function`
**Solution:** I suggest to use python's 'try' and 'expect' syntax to make sure that meep continues.
**Ref:** https://github.com/NanoComp/meep/issues/343

### `get_array clarification`
**Solution:** While I use the `get_array` function in the Python API quite frequently, I can't seem to predict its behavior 100% of the time.

For example, if I pass a (1D) volume that is 4 units long with a predefined simulation resolution of 10, I would expect `get_array` to return an array of length 40. Instead, it returns an array of length 42.

Now, If I pass that same volume on a simulation domain with a resolution of 15, it returns an array of length 63.

I'm assuming this has something to do with Meep's averaging (grid interpolation), but I feel like the results should be much more predictable. The documentation is a little vague in this regard.

Am I missing something obvious here?
**Ref:** https://github.com/NanoComp/meep/issues/502

### `module 'meep' has no attribute 'EnergyRegion'`
**Solution:** I encountered the below error when I tried to use EnergyRegion to define where to calculate the energy density. 

AttributeError: module 'meep' has no attribute 'EnergyRegion'

Besides, not only the above command, it seems like add_energy, get_electric_energy, load_minus_energy, and get_energy_freqs also having the same issue. (These commands are highlighted in my editor)

Does anyone meet this issue and successfully solve it?

Thank you very much.
**Ref:** https://github.com/NanoComp/meep/issues/816

### `module 'meep' has no attribute 'output_dft'`
**Solution:** can be called as mp.output_* except for output_dft, which returns the error "module 'meep' has no attribute 'output_dft'" when you try to call mp.output_dft(...).
**Ref:** https://github.com/NanoComp/meep/issues/852

### `Numpy deprecation warning in tests/geom.py`
**Solution:**   $SRC_DIR/python/tests/geom.py:604: PendingDeprecationWarning: the matrix subclass is not the recommended way to represent matrices or deal with linear algebra (see https://docs.scipy.org/doc/numpy/user/numpy-for-matlab-users.html). Please adjust your code to use regular ndarray.
    m_arr = np.matrix(m)
```
**Ref:** https://github.com/NanoComp/meep/issues/1376

### `configure script problem`
**Solution:** configure: error: could not find libctl files; use --with-libctl=<dir>
```

which I can fix as follows:

```
if test x != x"$LIBCTL_DIR" -a -r "$LIBCTL_DIR/share/libctl/base/ctl.scm"; then
##￼     LIBCTL_DIR="$LIBCTL_DIR/share/libctl"
    LIBCTL_DIR="${LIBCTL_DIR}/share/libctl"
**Ref:** https://github.com/NanoComp/meep/issues/1819

### `Mailing list issues`
**Solution:** The Mailman CGI wrapper encountered a fatal error. This entry is being stored in your syslog:

No such file or directory
```

These two things lead me to wonder if there may not perhaps be issues with the mailing list currently. 

Regards,
Durham
**Ref:** https://github.com/NanoComp/meep/issues/1875

## GEOMETRY

### `field-energy-in-box returns 0.0 always`
**Solution:** (set! geometry (list
                (make sphere (center 0 0 (- 10)) (radius sphereSize)
                      (material (make dielectric (epsilon realeps) (D-conductivity (/ (\* 2 pi
                                freq imageps) realeps)))))))

(set! pml-layers (list (make pml (thickness pmlSize))))

(set! sources (list (make source (src (make continuous-src (frequency freq))) (component Ex) (center 0 0 15)
(size xSize ySize 0) (amplitude
**Ref:** https://github.com/NanoComp/meep/issues/6

### `Eigenmode source calculated at wrong position in 3D`
**Solution:** when I have a 3d geometry of a straight waveguide, parallel to the z-direction and I use the eigenmode-source on one side, I get the correct eigenmode there and thus the correct propagation through the waveguide.
Anyway, when I taper the waveguide for example and again use the eigenmode source at one end of the waveguide, I do not get the correct eigenmode! After testing I found out, that the eigenmode is always calculated in the z-center. Means: Even if I place the eigenmode source at one end of the waveguide, let's say (center 0 0 14) (size sx sy 0), the eigenmode is calculated at (center 0 0 0) (size sx sy 0).
Not even the (eig-lattice-center 0 0 14) (eig-lattice-size sx sy 0) commands can change this.

Can somebody confirm this bug?

Best regards
Marc

**Ref:** https://github.com/NanoComp/meep/issues/20

### `Cylindrical coordinates python example doesn't work (AttributeError: swigobj)`
**Solution:** Computational cell is 8 x 0 x 0.1 with resolution 10
     block, center = (1,0,0)
          size (1,1e+20,1e+20)
          axes (1,0,0), (0,1,0), (0,0,1)
          dielectric constant epsilon diagonal = (11.56,11.56,11.56)
time for set_epsilon = 0.000378132 s
-----------
Meep: using complex fields.
harminv0:, frequency, imag., freq., Q, |amp|, amplitude, error
**Ref:** https://github.com/NanoComp/meep/issues/174

### `Drude metal material with material function-defined geometry fails  `
**Solution:** Defining the geometry by a material function that uses materials with DrudeSusceptibiltiy/LorentzianSusceptibility fails with error  "meep: susceptibilities in user-defined-materials not yet supported". 

Am I doing something wrong, or is this correct behavior? According to the manual, materials with susceptibilities are supported by material functions.

Minimal Python script to reproduce error -
[MaterialFunctionMinimal.zip](https://github.com/stevengj/meep/files/1697723/MaterialFunctionMinimal.zip)

**Ref:** https://github.com/NanoComp/meep/issues/197

### `typechecking error in meep/simulation.py`
**Solution:** Python meep seems to return a type-error when you set `epsilon_input_file` with a string (`epsilon_input_file="somefile.h5"`).  The type-error happens at the `set_materials_from_geometry()` call in meep/simulation.py (line 396).  However, casting it to a string fixes this:

`epsilon_input_file=str("somefile.h5")`.

I think this might be fixed, if line [394](https://github.com/stevengj/meep/blob/7998e6dc96eac709211f923128021bddbb9b7ee1/python/simulation.py) of `simulation.py` is changed from:

`self.default_material = self.epsilon_input_file`

to:
**Ref:** https://github.com/NanoComp/meep/issues/278

### `Cannot implement 3 or more prisms, get "bug 1 in find_best_partition" error`
**Solution:** I'm getting an interesting error: `bug 1 in find_best_partition` or `bug 2 in find_best_partition` when implementing 3 or more prism objects in meep.  Interestingly, it works totally fine with 1 or 2 prisms, but adding any more will cause this error to be thrown.

I attached a simple [MWE](https://github.com/stevengj/meep/files/2100058/multiple_prisms.zip) if you'd like to try reproducing the issue (I'm working off the latest meep,mpb,&libctl built from source).

The file should throw the error as is, but if you comment out the 3rd prism object in the geometry list (line 48), it will run.

Thanks,
Derek

**Ref:** https://github.com/NanoComp/meep/issues/384

### `zero current amplitudes in solve_cw`
**Solution:** For a given geometry, the solver works for some resolutions and fails with others. I can't seem to understand why. The codebase itself is a little vague:
https://github.com/stevengj/meep/blob/05b9778823beed36672f3054eea6b264c51f6973/src/cw_fields.cpp#L151-L171

Any thoughts as to why the solver fails with only some resolutions?
**Ref:** https://github.com/NanoComp/meep/issues/501

### `bug in vertices property of prism objects in Scheme interface`
**Solution:** (set-param! resolution 50)

(define-param pz 0)   ; prism bottom z coordinate                                                                                                                    
(define-param ph 1.0) ; prism height                                                                                                                                 

(set! geometry
      (list
       (make prism
         (vertices
**Ref:** https://github.com/NanoComp/meep/issues/608

### `pw-source.ctl`
**Solution:** Hello, I find the example of pw-source propagating at a 45-degree angle in vacuum. But how to change it to propagate in materials with n != 1. Because when I change n in the example, it can't propagate at 45-degree angle.
Thanks a lot!
**Ref:** https://github.com/NanoComp/meep/issues/762

### `failing get_farfield test due to multithreading`
**Solution:** Computational cell is 12.4 x 6 x 0 with resolution 10
     block, center = (0,0,0)
          size (1e+20,1.2,1e+20)
          axes (1,0,0), (0,1,0), (0,0,1)
          dielectric constant epsilon diagonal = (13,13,13)
     cylinder, center = (0.7,0,0)
          radius 0.36, height 1e+20, axis (0, 0, 1)
          dielectric constant epsilon diagonal = (1,1,1)
     cylinder, center = (-0.7,0,0)
**Ref:** https://github.com/NanoComp/meep/issues/878

## INSTALL

### `field-energy-in-box and MPI`
**Solution:** Meep throws out the error randomly (or I cannot spot any systematic behaviour). 5-6 out to 10 attempts to run this code end with the error (the rest of attempts end with a success). The error occurs only when I use multiple nodes.

Compiler: icc 14.0.0 (gcc version 4.4.7 compatibility)

Any help is appreciated.

Let me know if you need more information.

best wishes
**Ref:** https://github.com/NanoComp/meep/issues/19

### `meep not linking with fftw3_mpi`
**Solution:** It works fine if I use -lfftw3 linker instead.
I am not sure why meep looks for fftw3, instead of fftw3_mpi. 

**Ref:** https://github.com/NanoComp/meep/issues/22

### `Any working build for MacOS X 10.11 or 12 (El Cap. or Sierra)?`
**Solution:** I was using the `./autogen.sh --with-mpi --enable-maintainer-mode --enable-shared --prefix=/usr/local` command to build.
**Ref:** https://github.com/NanoComp/meep/issues/39

### `Bug: Guile 2.0.13 not compatible with meep 1.3`
**Solution:** Computational cell is 16 x 8 x 0 with resolution 10
     block, center = (0,0,0)
          size (1e+20,1,1e+20)
          axes (1,0,0), (0,1,0), (0,0,1)
          dielectric constant epsilon diagonal = (12,12,12)
time for set_epsilon = 0.163085 s
-----------
creating output file "./tutorial1-eps-000000.00.h5"...
Backtrace:
**Ref:** https://github.com/NanoComp/meep/issues/57

### `configure can't find ctl.h`
**Solution:** I am trying to install meep and company on an iMac running 10.12.5 (Sierra). Harminv and libctl install without error.  When I try to install meep itself, however, the configure script complains that it cannot find the ctl.h header.

configure:25526: error: Couldn't find the ctl.h header file for libctl.
ac_cv_header_ctl_h=no

However ctl.h is where it is supposed to be.  A "find -name ctl.h", results in
/usr/local/include/ctl.h
/usr/local/share/libctl/ctl.h

**Ref:** https://github.com/NanoComp/meep/issues/61

### `cannot compile meep from master branch due to libmeepgeom`
**Solution:** Meep is configured with mpi support, it should depend on ../src/libmeep_mpi.la
**Ref:** https://github.com/NanoComp/meep/issues/62

### `Cannot make meep on macOS Sierra`
**Solution:** meep_wrap.cxx:1394:10: error: use of undeclared identifier 'SCM_VECTORP'
  return SCM_VECTORP(o) && SCM_VECTOR_LENGTH(o) == 3;
         ^
meep_wrap.cxx:1394:28: error: use of undeclared identifier 'SCM_VECTOR_LENGTH'
  return SCM_VECTORP(o) && SCM_VECTOR_LENGTH(o) == 3;
                           ^
meep_wrap.cxx:53286:63: error: address of overloaded function '_wrap_do_harminv' does not match required type 'void'
  scm_c_define_gsubr("do-harminv", 0, 0, 1, (swig_guile_proc) _wrap_do_harminv);

**Ref:** https://github.com/NanoComp/meep/issues/64

### `h5topng seg faults in macOS Sierra`
**Solution:** Does anybody know how to diagnose the error allocation problem and fix it?
**Ref:** https://github.com/NanoComp/meep/issues/70

### `Make errors building from source in Debian Testing(Buster)`
**Solution:** Since the officially packaged meep for Debian doesn't work either, I find the use or compilation of meep virtually impossible, since the issue #57 is present on my system too.
**Ref:** https://github.com/NanoComp/meep/issues/94

### `Python import error simulation.py`
**Solution:** After running make install, 'import meep' failed with a message about missing 'simulation.py'.  I found that simulation.py had simply not been copied to .../site-packages/meep/, and manually doing so seemed to fix the problem.  I couldn't find anything relevant in the Makefiles except

`PY_PKG_FILES = \
    __init__.py              \
    $(srcdir)/geom.py        \
    $(srcdir)/simulation.py  \
    $(srcdir)/source.py      \
    .libs/_meep.so
`
**Ref:** https://github.com/NanoComp/meep/issues/107

