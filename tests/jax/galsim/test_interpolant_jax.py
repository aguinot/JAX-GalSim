"""These are pure tests of the interpolants to use while
InterpolatedImage is not yet implemented.

Much of the code is copied out of the galsim test suite.
"""
import galsim as ref_galsim
import numpy as np
import jax_galsim as galsim
from galsim_test_helpers import do_pickle, assert_raises, timer


@timer
def test_interpolant_smoke():
    """Test the interpolants directly."""
    x = np.linspace(-10, 10, 141)

    g = galsim.Gaussian(sigma=1.0)
    do_pickle(g)

    # Delta
    d = galsim.Delta()
    print(repr(d.gsparams))
    print(repr(galsim.GSParams()))
    assert d.gsparams == galsim.GSParams()
    assert d.xrange == 0
    assert d.ixrange == 0
    assert np.isclose(d.krange, 2. * np.pi / d.gsparams.kvalue_accuracy)
    assert np.isclose(d.krange, 2. * np.pi * d._i.urange())
    assert d.positive_flux == 1
    assert d.negative_flux == 0
    print(repr(d))
    do_pickle(galsim.Delta())
    do_pickle(galsim.Interpolant.from_name('delta'))

    true_xval = np.zeros_like(x)
    true_xval[np.abs(x) < d.gsparams.kvalue_accuracy / 2] = 1. / d.gsparams.kvalue_accuracy
    np.testing.assert_allclose(d.xval(x), true_xval)
    np.testing.assert_allclose(d.kval(x), 1.)
    assert np.isclose(d.xval(x[12]), true_xval[12])
    assert np.isclose(d.kval(x[12]), 1.)

    # Nearest
    n = galsim.Nearest()
    assert n.gsparams == galsim.GSParams()
    assert n.xrange == 0.5
    assert n.ixrange == 1
    assert np.isclose(n.krange, 2. / n.gsparams.kvalue_accuracy)
    assert n.positive_flux == 1
    assert n.negative_flux == 0
    do_pickle(galsim.Nearest())
    do_pickle(galsim.Interpolant.from_name('nearest'))

    true_xval = np.zeros_like(x)
    true_xval[np.abs(x) < 0.5] = 1
    np.testing.assert_allclose(n.xval(x), true_xval)
    true_kval = np.sinc(x / 2 / np.pi)
    np.testing.assert_allclose(n.kval(x), true_kval)
    assert np.isclose(n.xval(x[12]), true_xval[12])
    assert np.isclose(n.kval(x[12]), true_kval[12])

    # Conserves dc flux:
    # Most interpolants (not Delta above) conserve a constant (DC) flux.
    # This means input points separated by 1 pixel with any subpixel phase
    # will sum to 1.  The input x array has 7 phases, so the total sum is 7.
    print('Nearest sum = ', np.sum(n.xval(x)))
    assert np.isclose(np.sum(n.xval(x)), 7.0)

    # SincInterpolant
    s = galsim.SincInterpolant()
    assert s.gsparams == galsim.GSParams()
    assert np.isclose(s.xrange, 1. / (np.pi * s.gsparams.kvalue_accuracy))
    assert s.ixrange == 2 * np.ceil(s.xrange)
    assert np.isclose(s.krange, np.pi)
    assert np.isclose(s.krange, 2. * np.pi * s._i.urange())
    assert np.isclose(s.positive_flux, 3.18726437)  # Empirical -- this is a regression test
    assert np.isclose(s.negative_flux, s.positive_flux - 1., rtol=1.e-4)
    do_pickle(galsim.SincInterpolant())
    do_pickle(galsim.Interpolant.from_name('sinc'))

    true_xval = np.sinc(x)
    np.testing.assert_allclose(s.xval(x), true_xval)
    true_kval = np.zeros_like(x)
    true_kval[np.abs(x) < np.pi] = 1.
    np.testing.assert_allclose(s.kval(x), true_kval)
    assert np.isclose(s.xval(x[12]), true_xval[12])
    assert np.isclose(s.kval(x[12]), true_kval[12])

    # Conserves dc flux:
    # This one would conserve dc flux, but we don't go out far enough.
    # At +- 10 pixels, it's only about 6.86
    print('Sinc sum = ', np.sum(s.xval(x)))
    assert np.isclose(np.sum(s.xval(x)), 7.0, rtol=0.02)

    # Linear
    ln = galsim.Linear()
    assert ln.gsparams == galsim.GSParams()
    assert ln.xrange == 1.
    assert ln.ixrange == 2
    assert np.isclose(ln.krange, 2. / ln.gsparams.kvalue_accuracy**0.5)
    assert np.isclose(ln.krange, 2. * np.pi * ln._i.urange())
    assert ln.positive_flux == 1
    assert ln.negative_flux == 0
    do_pickle(galsim.Linear())
    do_pickle(galsim.Interpolant.from_name('linear'))

    true_xval = np.zeros_like(x)
    true_xval[np.abs(x) < 1] = 1. - np.abs(x[np.abs(x) < 1])
    np.testing.assert_allclose(ln.xval(x), true_xval)
    true_kval = np.sinc(x / 2 / np.pi)**2
    np.testing.assert_allclose(ln.kval(x), true_kval)
    assert np.isclose(ln.xval(x[12]), true_xval[12])
    assert np.isclose(ln.kval(x[12]), true_kval[12])

    # Conserves dc flux:
    print('Linear sum = ', np.sum(ln.xval(x)))
    assert np.isclose(np.sum(ln.xval(x)), 7.0)

    # Cubic
    c = galsim.Cubic()
    assert c.gsparams == galsim.GSParams()
    assert c.xrange == 2.
    assert c.ixrange == 4
    assert np.isclose(c.krange, 2. * (3**1.5 / 8 / c.gsparams.kvalue_accuracy)**(1. / 3.))
    assert np.isclose(c.krange, 2. * np.pi * c._i.urange())
    assert np.isclose(c.positive_flux, 13. / 12.)
    assert np.isclose(c.negative_flux, 1. / 12.)
    do_pickle(galsim.Cubic())
    do_pickle(galsim.Interpolant.from_name('cubic'))

    true_xval = np.zeros_like(x)
    ax = np.abs(x)
    m = ax < 1
    true_xval[m] = 1. + ax[m]**2 * (1.5 * ax[m] - 2.5)
    m = (1 <= ax) & (ax < 2)
    true_xval[m] = -0.5 * (ax[m] - 1) * (2. - ax[m])**2
    np.testing.assert_allclose(c.xval(x), true_xval)
    sx = np.sinc(x / 2 / np.pi)
    cx = np.cos(x / 2)
    true_kval = sx**3 * (3 * sx - 2 * cx)
    np.testing.assert_allclose(c.kval(x), true_kval)
    assert np.isclose(c.xval(x[12]), true_xval[12])
    assert np.isclose(c.kval(x[12]), true_kval[12])

    # Conserves dc flux:
    print('Cubic sum = ', np.sum(c.xval(x)))
    assert np.isclose(np.sum(c.xval(x)), 7.0)

#     # Quintic
#     q = galsim.Quintic()
#     assert q.gsparams == galsim.GSParams()
#     assert q.xrange == 3.
#     assert q.ixrange == 6
#     assert np.isclose(q.krange, 2. * (5**2.5 / 108 / q.gsparams.kvalue_accuracy)**(1./3.))
#     assert np.isclose(q.krange, 2.*np.pi * q._i.urange())
#     assert np.isclose(q.positive_flux, (13018561. / 11595672.) + (17267. / 14494590.) * 31**0.5)
#     assert np.isclose(q.negative_flux, q.positive_flux-1.)
#     do_pickle(q, test_func)
#     do_pickle(galsim.Quintic())
#     do_pickle(galsim.Interpolant.from_name('quintic'))

#     true_xval = np.zeros_like(x)
#     ax = np.abs(x)
#     m = ax < 1.
#     true_xval[m] = 1. + ax[m]**3 * (-95./12. + 23./2.*ax[m] - 55./12.*ax[m]**2)
#     m = (1 <= ax) & (ax < 2)
#     true_xval[m] = (ax[m]-1) * (2.-ax[m]) * (23./4. - 29./2.*ax[m] + 83./8.*ax[m]**2
#                                              - 55./24.*ax[m]**3)
#     m = (2 <= ax) & (ax < 3)
#     true_xval[m] = (ax[m]-2) * (3.-ax[m])**2 * (-9./4. + 25./12.*ax[m] - 11./24.*ax[m]**2)
#     np.testing.assert_allclose(q.xval(x), true_xval)
#     sx = np.sinc(x/2/np.pi)
#     cx = np.cos(x/2)
#     true_kval = sx**5 * (sx*(55.-19./4. * x**2) + cx*(x**2/2. - 54.))
#     np.testing.assert_allclose(q.kval(x), true_kval)
#     assert np.isclose(q.xval(x[12]), true_xval[12])
#     assert np.isclose(q.kval(x[12]), true_kval[12])

#     # Conserves dc flux:
#     print('Quintic sum = ',np.sum(q.xval(x)))
#     assert np.isclose(np.sum(q.xval(x)), 7.0)

#     # Lanczos
#     l3 = galsim.Lanczos(3)
#     assert l3.gsparams == galsim.GSParams()
#     assert l3.conserve_dc == True
#     assert l3.n == 3
#     assert l3.xrange == l3.n
#     assert l3.ixrange == 2*l3.n
#     assert np.isclose(l3.krange, 2.*np.pi * l3._i.urange())  # No analytic version for this one.
#     print(l3.positive_flux, l3.negative_flux)
#     assert np.isclose(l3.positive_flux, 1.1793639)  # Empirical -- this is a regression test
#     assert np.isclose(l3.negative_flux, l3.positive_flux-1., rtol=1.e-4)
#     do_pickle(l3, test_func)
#     do_pickle(galsim.Lanczos(n=7, conserve_dc=False))
#     do_pickle(galsim.Lanczos(3))
#     do_pickle(galsim.Interpolant.from_name('lanczos7'))
#     do_pickle(galsim.Interpolant.from_name('lanczos9F'))
#     do_pickle(galsim.Interpolant.from_name('lanczos8T'))
#     assert_raises(ValueError, galsim.Interpolant.from_name, 'lanczos3A')
#     assert_raises(ValueError, galsim.Interpolant.from_name, 'lanczosF')
#     assert_raises(ValueError, galsim.Interpolant.from_name, 'lanzos')

#     # Note: 1-7 all have special case code, so check them. 8 uses the generic code.
#     for n in [1, 2, 3, 4, 5, 6, 7, 8]:
#         ln = galsim.Lanczos(n, conserve_dc=False)
#         assert ln.conserve_dc == False
#         assert ln.n == n
#         true_xval = np.zeros_like(x)
#         true_xval[np.abs(x) < n] = np.sinc(x[np.abs(x)<n]) * np.sinc(x[np.abs(x)<n]/n)
#         np.testing.assert_allclose(ln.xval(x), true_xval, rtol=1.e-5, atol=1.e-10)
#         assert np.isclose(ln.xval(x[12]), true_xval[12])

#         # Lanczos notably does not conserve dc flux
#         print('Lanczos(%s,conserve_dc=False) sum = '%n,np.sum(ln.xval(x)))

#         # With conserve_dc=True, it does a bit better, but still only to 1.e-4 accuracy.
#         lndc = galsim.Lanczos(n, conserve_dc=True)
#         np.testing.assert_allclose(lndc.xval(x), true_xval, rtol=0.3, atol=1.e-10)
#         print('Lanczos(%s,conserve_dc=True) sum = '%n,np.sum(lndc.xval(x)))
#         assert np.isclose(np.sum(lndc.xval(x)), 7.0, rtol=1.e-4)

#         # The math for kval (at least when conserve_dc=False) is complicated, but tractable.
#         # It ends up using the Si function, which is in scipy as scipy.special.sici
#         vp = n * (x/np.pi + 1)
#         vm = n * (x/np.pi - 1)
#         true_kval = ( (vm-1) * sici(np.pi*(vm-1))[0]
#                      -(vm+1) * sici(np.pi*(vm+1))[0]
#                      -(vp-1) * sici(np.pi*(vp-1))[0]
#                      +(vp+1) * sici(np.pi*(vp+1))[0] ) / (2*np.pi)
#         np.testing.assert_allclose(ln.kval(x), true_kval, rtol=1.e-4, atol=1.e-8)
#         assert np.isclose(ln.kval(x[12]), true_kval[12])

    # Base class is invalid.
    assert_raises(NotImplementedError, galsim.Interpolant)

    # 2d arrays are invalid.
    x2d = np.ones((5, 5))
    with assert_raises(galsim.GalSimValueError):
        s.xval(x2d)
    with assert_raises(galsim.GalSimValueError):
        s.kval(x2d)


@timer
def test_interpolant_unit_integrals():
    # Test Interpolant.unit_integrals

    interps = [
        galsim.Delta(),
        galsim.Nearest(),
        galsim.SincInterpolant(),
        galsim.Linear(),
        galsim.Cubic(),
        #    galsim.Quintic(),
        #    galsim.Lanczos(3),
        #    galsim.Lanczos(3, conserve_dc=False),
        #    galsim.Lanczos(17),
    ]
    for interp in interps:
        print(str(interp))
        # Compute directly with int1d
        n = interp.ixrange // 2 + 1
        direct_integrals = np.zeros(n)
        if isinstance(interp, galsim.Delta):
            # int1d doesn't handle this well.
            direct_integrals[0] = 1
        else:
            for k in range(n):
                direct_integrals[k] = ref_galsim.integ.int1d(interp.xval, k - 0.5, k + 0.5)
        print('direct: ', direct_integrals)

        # Get from unit_integrals method (sometimes using analytic formulas)
        integrals = interp.unit_integrals()
        print('integrals: ', len(integrals), integrals)

        assert len(integrals) == n
        np.testing.assert_allclose(integrals, direct_integrals, atol=1.e-12)

        if n > 10:
            print('n>10 for ', repr(interp))
            integrals2 = interp.unit_integrals(max_len=10)
            assert len(integrals2) == 10
            np.testing.assert_allclose(integrals2, integrals[:10], atol=0, rtol=0)

    # # Test making shorter versions before longer ones
    # interp = galsim.Lanczos(11)
    # short = interp.unit_integrals(max_len=5)
    # long = interp.unit_integrals(max_len=10)
    # med = interp.unit_integrals(max_len=8)
    # full = interp.unit_integrals()

    # assert len(full) > 10
    # np.testing.assert_equal(short, full[:5])
    # np.testing.assert_equal(med, full[:8])
    # np.testing.assert_equal(long, full[:10])
