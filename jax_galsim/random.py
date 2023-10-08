import secrets

import galsim as _galsim
import jax
import jax.numpy as jnp
import jax.random as jrandom
from jax._src.numpy.util import _wraps
from jax.tree_util import register_pytree_node_class

try:
    from jax.extend.random import wrap_key_data
except ImportError:
    from jax.random import wrap_key_data

from jax_galsim.core.utils import ensure_hashable

LAX_FUNCTIONAL_RNG = (
    "The JAX version of the this class is purely function and thus cannot "
    "share state with any other version of this class. Also no type checking is done on the inputs."
)


@_wraps(
    _galsim.BaseDeviate,
    lax_description=LAX_FUNCTIONAL_RNG,
)
@register_pytree_node_class
class BaseDeviate:
    # always the case for JAX
    has_reliable_discard = True
    generates_in_pairs = False

    def __init__(self, seed=None):
        self.reset(seed=seed)

    @_wraps(
        _galsim.BaseDeviate.seed,
        lax_description="The JAX version of this method does no type checking.",
    )
    def seed(self, seed=0):
        self._seed(seed=seed)

    @_wraps(_galsim.BaseDeviate._seed)
    def _seed(self, seed=0):
        _initial_seed = seed or secrets.randbelow(2**31)
        self._key = jrandom.PRNGKey(_initial_seed)

    @_wraps(
        _galsim.BaseDeviate.reset,
        lax_description=(
            "The JAX version of this method does no type checking. Also, the JAX version of this "
            "class cannot be linked to another JAX version of this class so ``reset`` is equivalent "
            "to ``seed``. If another ``BaseDeviate`` is supplied, that deviates current state is used."
        ),
    )
    def reset(self, seed=None):
        if isinstance(seed, BaseDeviate):
            self._reset(seed)
        elif isinstance(seed, jax.Array):
            self._key = wrap_key_data(seed)
        elif isinstance(seed, str):
            self._key = wrap_key_data(jnp.array(eval(seed), dtype=jnp.uint32))
        elif isinstance(seed, tuple):
            self._key = wrap_key_data(jnp.array(seed, dtype=jnp.uint32))
        else:
            self._seed(seed=seed)

    @_wraps(_galsim.BaseDeviate._reset)
    def _reset(self, rng):
        self._key = rng._key

    @property
    @_wraps(_galsim.BaseDeviate.np)
    def np(self):
        raise NotImplementedError(
            "The JAX galsim.BaseDeviate does not support being used as a numpy PRNG."
        )

    @_wraps(_galsim.BaseDeviate.as_numpy_generator)
    def as_numpy_generator(self):
        raise NotImplementedError(
            "The JAX galsim.BaseDeviate does not support being used as a numpy PRNG."
        )

    @_wraps(_galsim.BaseDeviate.duplicate)
    def duplicate(self):
        ret = BaseDeviate.__new__(self.__class__)
        ret._key = self._key
        return ret

    def __copy__(self):
        return self.duplicate()

    @_wraps(
        _galsim.BaseDeviate.clearCache,
        lax_description="This method is a no-op for the JAX version of this class.",
    )
    def clearCache(self):
        pass

    @_wraps(
        _galsim.BaseDeviate.discard,
        lax_description=(
            "The JAX version of this class has reliable discarding and uses one key per value "
            "so it never generates in pairs. Thus this method will never raise an error."
        ),
    )
    def discard(self, n, suppress_warnings=False):
        def _discard(i, key):
            key, subkey = jrandom.split(key)
            return key

        self._key = jax.lax.fori_loop(0, n, _discard, self._key)

    @_wraps(
        _galsim.BaseDeviate.raw,
        lax_description=(
            "The JAX version of this class does not use the raw value to "
            "generate the next value of a specific kind."
        ),
    )
    def raw(self):
        self._key, subkey = jrandom.split(self._key)
        return jrandom.bits(subkey, dtype=jnp.uint32)

    @_wraps(
        _galsim.BaseDeviate.generate,
        lax_description=(
            "JAX arrays cannot be changed in-place, so the JAX version of "
            "this method returns a new array."
        ),
    )
    def generate(self, array):
        self._key, array = self.__class__._generate(self._key, array)
        return array

    @_wraps(
        _galsim.BaseDeviate.generate,
        lax_description=(
            "JAX arrays cannot be changed in-place, so the JAX version of "
            "this method returns a new array."
        ),
    )
    def add_generate(self, array):
        return self.generate(array) + array

    def __call__(self):
        self._key, val = self.__class__._generate_one(self._key, None)
        return val

    def __eq__(self, other):
        return self is other or (
            isinstance(other, self.__class__)
            and jnp.array_equal(
                jrandom.key_data(self._key), jrandom.key_data(other._key)
            )
        )

    def __ne__(self, other):
        return not self.__eq__(other)

    __hash__ = None

    def serialize(self):
        return repr(ensure_hashable(jrandom.key_data(self._key)))

    def __repr__(self):
        return "galsim.%s(%r) " % (
            self.__class__.__name__,
            ensure_hashable(jrandom.key_data(self._key)),
        )

    def __str__(self):
        return self.__repr__()

    def tree_flatten(self):
        """This function flattens the PRNG into a list of children
        nodes that will be traced by JAX and auxiliary static data."""
        # Define the children nodes of the PyTree that need tracing
        children = (jrandom.key_data(self._key),)
        # Define auxiliary static data that doesn’t need to be traced
        aux_data = {}
        return (children, aux_data)

    @classmethod
    def tree_unflatten(cls, aux_data, children):
        """Recreates an instance of the class from flatten representation"""
        return cls(children[0])


@_wraps(
    _galsim.UniformDeviate,
    lax_description=LAX_FUNCTIONAL_RNG,
)
@register_pytree_node_class
class UniformDeviate(BaseDeviate):
    def _generate(key, array):
        # we do it this way so that the RNG appears to have a fixed state that is advanced per value drawn
        key, res = jax.lax.scan(
            UniformDeviate._generate_one, key, None, length=array.ravel().shape[0]
        )
        return key, res.reshape(array.shape)

    @jax.jit
    def _generate_one(key, x):
        _key, subkey = jrandom.split(key)
        return _key, jrandom.uniform(subkey, dtype=float)


# class GaussianDeviate(BaseDeviate):
#     """Pseudo-random number generator with Gaussian distribution.

#     See http://en.wikipedia.org/wiki/Gaussian_distribution for further details.

#     Successive calls to ``g()`` generate pseudo-random values distributed according to a Gaussian
#     distribution with the provided ``mean``, ``sigma``::

#         >>> g = galsim.GaussianDeviate(31415926)
#         >>> g()
#         0.5533754000847082
#         >>> g()
#         1.0218588970190354

#     Parameters:
#         seed:       Something that can seed a `BaseDeviate`: an integer seed or another
#                     `BaseDeviate`.  Using 0 means to generate a seed from the system.
#                     [default: None]
#         mean:       Mean of Gaussian distribution. [default: 0.]
#         sigma:      Sigma of Gaussian distribution. [default: 1.; Must be > 0]
#     """
#     def __init__(self, seed=None, mean=0., sigma=1.):
#         if sigma < 0.:
#             raise GalSimRangeError("GaussianDeviate sigma must be > 0.", sigma, 0.)
#         self._rng_type = _galsim.GaussianDeviateImpl
#         self._rng_args = (float(mean), float(sigma))
#         self.reset(seed)

#     @property
#     def mean(self):
#         """The mean of the Gaussian distribution.
#         """
#         return self._rng_args[0]

#     @property
#     def sigma(self):
#         """The sigma of the Gaussian distribution.
#         """
#         return self._rng_args[1]

#     @property
#     def generates_in_pairs(self):
#         return True

#     def __call__(self):
#         """Draw a new random number from the distribution.

#         Returns a Gaussian deviate with the given mean and sigma.
#         """
#         return self._rng.generate1()

#     def generate_from_variance(self, array):
#         """Generate many Gaussian deviate values using the existing array values as the
#         variance for each.
#         """
#         array_1d = np.ascontiguousarray(array.ravel(), dtype=float)
#         #assert(array_1d.strides[0] == array_1d.itemsize)
#         _a = array_1d.__array_interface__['data'][0]
#         self._rng.generate_from_variance(len(array_1d), _a)
#         if array_1d.data != array.data:
#             # array_1d is not a view into the original array.  Need to copy back.
#             np.copyto(array, array_1d.reshape(array.shape), casting='unsafe')

#     def __repr__(self):
#         return 'galsim.GaussianDeviate(seed=%r, mean=%r, sigma=%r)'%(
#                 self._seed_repr(), self.mean, self.sigma)
#     def __str__(self):
#         return 'galsim.GaussianDeviate(mean=%r, sigma=%r)'%(self.mean, self.sigma)


# class BinomialDeviate(BaseDeviate):
#     """Pseudo-random Binomial deviate for ``N`` trials each of probability ``p``.

#     ``N`` is number of 'coin flips,' ``p`` is probability of 'heads,' and each call returns an
#     integer value where 0 <= value <= N gives the number of heads.  See
#     http://en.wikipedia.org/wiki/Binomial_distribution for more information.

#     Successive calls to ``b()`` generate pseudo-random integer values distributed according to a
#     binomial distribution with the provided ``N``, ``p``::

#         >>> b = galsim.BinomialDeviate(31415926, N=10, p=0.3)
#         >>> b()
#         2
#         >>> b()
#         3

#     Parameters:
#         seed:       Something that can seed a `BaseDeviate`: an integer seed or another
#                     `BaseDeviate`.  Using 0 means to generate a seed from the system.
#                     [default: None]
#         N:          The number of 'coin flips' per trial. [default: 1; Must be > 0]
#         p:          The probability of success per coin flip. [default: 0.5; Must be > 0]
#     """
#     def __init__(self, seed=None, N=1, p=0.5):
#         self._rng_type = _galsim.BinomialDeviateImpl
#         self._rng_args = (int(N), float(p))
#         self.reset(seed)

#     @property
#     def n(self):
#         """The number of 'coin flips'.
#         """
#         return self._rng_args[0]

#     @property
#     def p(self):
#         """The probability of success per 'coin flip'.
#         """
#         return self._rng_args[1]

#     def __call__(self):
#         """Draw a new random number from the distribution.

#         Returns a Binomial deviate with the given n and p.
#         """
#         return self._rng.generate1()

#     def __repr__(self):
#         return 'galsim.BinomialDeviate(seed=%r, N=%r, p=%r)'%(self._seed_repr(), self.n, self.p)
#     def __str__(self):
#         return 'galsim.BinomialDeviate(N=%r, p=%r)'%(self.n, self.p)


# class PoissonDeviate(BaseDeviate):
#     """Pseudo-random Poisson deviate with specified ``mean``.

#     The input ``mean`` sets the mean and variance of the Poisson deviate.  An integer deviate with
#     this distribution is returned after each call.
#     See http://en.wikipedia.org/wiki/Poisson_distribution for more details.

#     Successive calls to ``p()`` generate pseudo-random integer values distributed according to a
#     Poisson distribution with the specified ``mean``::

#         >>> p = galsim.PoissonDeviate(31415926, mean=100)
#         >>> p()
#         94
#         >>> p()
#         106

#     Parameters:
#         seed:       Something that can seed a `BaseDeviate`: an integer seed or another
#                     `BaseDeviate`.  Using 0 means to generate a seed from the system.
#                     [default: None]
#         mean:       Mean of the distribution. [default: 1; Must be > 0]
#     """
#     def __init__(self, seed=None, mean=1.):
#         if mean < 0:
#             raise GalSimValueError("PoissonDeviate is only defined for mean >= 0.", mean)
#         self._rng_type = _galsim.PoissonDeviateImpl
#         self._rng_args = (float(mean),)
#         self.reset(seed)

#     @property
#     def mean(self):
#         """The mean of the distribution.
#         """
#         return self._rng_args[0]

#     @property
#     def has_reliable_discard(self):
#         return False

#     def __call__(self):
#         """Draw a new random number from the distribution.

#         Returns a Poisson deviate with the given mean.
#         """
#         return self._rng.generate1()

#     def generate_from_expectation(self, array):
#         """Generate many Poisson deviate values using the existing array values as the
#         expectation value (aka mean) for each.
#         """
#         if np.any(array < 0):
#             raise GalSimValueError("Expectation array may not have values < 0.", array)
#         array_1d = np.ascontiguousarray(array.ravel(), dtype=float)
#         #assert(array_1d.strides[0] == array_1d.itemsize)
#         _a = array_1d.__array_interface__['data'][0]
#         self._rng.generate_from_expectation(len(array_1d), _a)
#         if array_1d.data != array.data:
#             # array_1d is not a view into the original array.  Need to copy back.
#             np.copyto(array, array_1d.reshape(array.shape), casting='unsafe')

#     def __repr__(self):
#         return 'galsim.PoissonDeviate(seed=%r, mean=%r)'%(self._seed_repr(), self.mean)
#     def __str__(self):
#         return 'galsim.PoissonDeviate(mean=%r)'%(self.mean)


# class WeibullDeviate(BaseDeviate):
#     """Pseudo-random Weibull-distributed deviate for shape parameter ``a`` and scale parameter ``b``.

#     The Weibull distribution is related to a number of other probability distributions; in
#     particular, it interpolates between the exponential distribution (a=1) and the Rayleigh
#     distribution (a=2).
#     See http://en.wikipedia.org/wiki/Weibull_distribution (a=k and b=lambda in the notation adopted
#     in the Wikipedia article) for more details.  The Weibull distribution is real valued and
#     produces deviates >= 0.

#     Successive calls to ``w()`` generate pseudo-random values distributed according to a Weibull
#     distribution with the specified shape and scale parameters ``a`` and ``b``::

#         >>> w = galsim.WeibullDeviate(31415926, a=1.3, b=4)
#         >>> w()
#         1.1038481241018219
#         >>> w()
#         2.957052966368049

#     Parameters:
#         seed:       Something that can seed a `BaseDeviate`: an integer seed or another
#                     `BaseDeviate`.  Using 0 means to generate a seed from the system.
#                     [default: None]
#         a:          Shape parameter of the distribution. [default: 1; Must be > 0]
#         b:          Scale parameter of the distribution. [default: 1; Must be > 0]
#     """
#     def __init__(self, seed=None, a=1., b=1.):
#         self._rng_type = _galsim.WeibullDeviateImpl
#         self._rng_args = (float(a), float(b))
#         self.reset(seed)

#     @property
#     def a(self):
#         """The shape parameter, a.
#         """
#         return self._rng_args[0]

#     @property
#     def b(self):
#         """The scale parameter, b.
#         """
#         return self._rng_args[1]

#     def __call__(self):
#         """Draw a new random number from the distribution.

#         Returns a Weibull-distributed deviate with the given shape parameters a and b.
#         """
#         return self._rng.generate1()

#     def __repr__(self):
#         return 'galsim.WeibullDeviate(seed=%r, a=%r, b=%r)'%(self._seed_repr(), self.a, self.b)
#     def __str__(self):
#         return 'galsim.WeibullDeviate(a=%r, b=%r)'%(self.a, self.b)


# class GammaDeviate(BaseDeviate):
#     """A Gamma-distributed deviate with shape parameter ``k`` and scale parameter ``theta``.
#     See http://en.wikipedia.org/wiki/Gamma_distribution.
#     (Note: we use the k, theta notation. If you prefer alpha, beta, use k=alpha, theta=1/beta.)
#     The Gamma distribution is a real valued distribution producing deviates >= 0.

#     Successive calls to ``g()`` generate pseudo-random values distributed according to a gamma
#     distribution with the specified shape and scale parameters ``k`` and ``theta``::

#         >>> gam = galsim.GammaDeviate(31415926, k=1, theta=2)
#         >>> gam()
#         0.37508882726316
#         >>> gam()
#         1.3504199388358704

#     Parameters:
#         seed:       Something that can seed a `BaseDeviate`: an integer seed or another
#                     `BaseDeviate`.  Using 0 means to generate a seed from the system.
#                     [default: None]
#         k:          Shape parameter of the distribution. [default: 1; Must be > 0]
#         theta:      Scale parameter of the distribution. [default: 1; Must be > 0]
#     """
#     def __init__(self, seed=None, k=1., theta=1.):
#         self._rng_type = _galsim.GammaDeviateImpl
#         self._rng_args = (float(k), float(theta))
#         self.reset(seed)

#     @property
#     def k(self):
#         """The shape parameter, k.
#         """
#         return self._rng_args[0]

#     @property
#     def theta(self):
#         """The scale parameter, theta.
#         """
#         return self._rng_args[1]

#     @property
#     def has_reliable_discard(self):
#         return False

#     def __call__(self):
#         """Draw a new random number from the distribution.

#         Returns a Gamma-distributed deviate with the given k and theta.
#         """
#         return self._rng.generate1()

#     def __repr__(self):
#         return 'galsim.GammaDeviate(seed=%r, k=%r, theta=%r)'%(
#                 self._seed_repr(), self.k, self.theta)
#     def __str__(self):
#         return 'galsim.GammaDeviate(k=%r, theta=%r)'%(self.k, self.theta)


# class Chi2Deviate(BaseDeviate):
#     """Pseudo-random Chi^2-distributed deviate for degrees-of-freedom parameter ``n``.

#     See http://en.wikipedia.org/wiki/Chi-squared_distribution (note that k=n in the notation
#     adopted in the Boost.Random routine called by this class).  The Chi^2 distribution is a
#     real-valued distribution producing deviates >= 0.

#     Successive calls to ``chi2()`` generate pseudo-random values distributed according to a
#     chi-square distribution with the specified degrees of freedom, ``n``::

#         >>> chi2 = galsim.Chi2Deviate(31415926, n=7)
#         >>> chi2()
#         7.9182211987712385
#         >>> chi2()
#         6.644121724269535

#     Parameters:
#         seed:       Something that can seed a `BaseDeviate`: an integer seed or another
#                     `BaseDeviate`.  Using 0 means to generate a seed from the system.
#                     [default: None]
#         n:          Number of degrees of freedom for the output distribution. [default: 1;
#                     Must be > 0]
#     """
#     def __init__(self, seed=None, n=1.):
#         self._rng_type = _galsim.Chi2DeviateImpl
#         self._rng_args = (float(n),)
#         self.reset(seed)

#     @property
#     def n(self):
#         """The number of degrees of freedom.
#         """
#         return self._rng_args[0]

#     @property
#     def has_reliable_discard(self):
#         return False

#     def __call__(self):
#         """Draw a new random number from the distribution.

#         Returns a Chi2-distributed deviate with the given number of degrees of freedom.
#         """
#         return self._rng.generate1()

#     def __repr__(self):
#         return 'galsim.Chi2Deviate(seed=%r, n=%r)'%(self._seed_repr(), self.n)
#     def __str__(self):
#         return 'galsim.Chi2Deviate(n=%r)'%(self.n)


# class DistDeviate(BaseDeviate):
#     """A class to draw random numbers from a user-defined probability distribution.

#     DistDeviate is a `BaseDeviate` class that can be used to draw from an arbitrary probability
#     distribution.  The probability distribution passed to DistDeviate can be given one of three
#     ways: as the name of a file containing a 2d ASCII array of x and P(x), as a `LookupTable`
#     mapping x to P(x), or as a callable function.

#     Once given a probability, DistDeviate creates a table of the cumulative probability and draws
#     from it using a `UniformDeviate`.  The precision of its outputs can be controlled with the
#     keyword ``npoints``, which sets the number of points DistDeviate creates for its internal table
#     of CDF(x).  To prevent errors due to non-monotonicity, the interpolant for this internal table
#     is always linear.

#     Two keywords, ``x_min`` and ``x_max``, define the support of the function.  They must be passed
#     if a callable function is given to DistDeviate, unless the function is a `LookupTable`, which
#     has its own defined endpoints.  If a filename or `LookupTable` is passed to DistDeviate, the
#     use of ``x_min`` or ``x_max`` will result in an error.

#     If given a table in a file, DistDeviate will construct an interpolated `LookupTable` to obtain
#     more finely gridded probabilities for generating the cumulative probability table.  The default
#     ``interpolant`` is linear, but any interpolant understood by `LookupTable` may be used.  We
#     caution against the use of splines because they can cause non-monotonic behavior.  Passing the
#     ``interpolant`` keyword next to anything but a table in a file will result in an error.

#     **Examples**:

#     Some sample initialization calls::

#         >>> d = galsim.DistDeviate(function=f, x_min=x_min, x_max=x_max)

#     Initializes d to be a DistDeviate instance with a distribution given by the callable function
#     ``f(x)`` from ``x=x_min`` to ``x=x_max`` and seeds the PRNG using current time::

#         >>> d = galsim.DistDeviate(1062533, function=file_name, interpolant='floor')

#     Initializes d to be a DistDeviate instance with a distribution given by the data in file
#     ``file_name``, which must be a 2-column ASCII table, and seeds the PRNG using the integer
#     seed 1062533. It generates probabilities from ``file_name`` using the interpolant 'floor'::

#         >>> d = galsim.DistDeviate(rng, function=galsim.LookupTable(x,p))

#     Initializes d to be a DistDeviate instance with a distribution given by P(x), defined as two
#     arrays ``x`` and ``p`` which are used to make a callable `LookupTable`, and links the
#     DistDeviate PRNG to the already-existing random number generator ``rng``.

#     Successive calls to ``d()`` generate pseudo-random values with the given probability
#     distribution::

#         >>> d = galsim.DistDeviate(31415926, function=lambda x: 1-abs(x), x_min=-1, x_max=1)
#         >>> d()
#         -0.4151921102709466
#         >>> d()
#         -0.00909781188974034

#     Parameters:
#         seed:           Something that can seed a `BaseDeviate`: an integer seed or another
#                         `BaseDeviate`.  Using 0 means to generate a seed from the system.
#                         [default: None]
#         function:       A callable function giving a probability distribution or the name of a
#                         file containing a probability distribution as a 2-column ASCII table.
#                         [required]
#         x_min:          The minimum desired return value (required for non-`LookupTable`
#                         callable functions; will raise an error if not passed in that case, or if
#                         passed in any other case) [default: None]
#         x_max:          The maximum desired return value (required for non-`LookupTable`
#                         callable functions; will raise an error if not passed in that case, or if
#                         passed in any other case) [default: None]
#         interpolant:    Type of interpolation used for interpolating a file (causes an error if
#                         passed alongside a callable function).  Options are given in the
#                         documentation for `LookupTable`. [default: 'linear']
#         npoints:        Number of points DistDeviate should create for its internal interpolation
#                         tables. [default: 256, unless the function is a non-log `LookupTable`, in
#                         which case it uses the table's x values]
#     """
#     def __init__(self, seed=None, function=None, x_min=None,
#                  x_max=None, interpolant=None, npoints=None):
#         from .table import LookupTable
#         from . import utilities
#         from . import integ

#         # Set up the PRNG
#         self._rng_type = _galsim.UniformDeviateImpl
#         self._rng_args = ()
#         self.reset(seed)

#         # Basic input checking and setups
#         if function is None:
#             raise TypeError('You must pass a function to DistDeviate!')

#         self._interpolant = interpolant
#         self._npoints = npoints
#         self._xmin = x_min
#         self._xmax = x_max

#         # Figure out if a string is a filename or something we should be using in an eval call
#         if isinstance(function, str):
#             self._function = function # Save the inputs to be used in repr
#             import os.path
#             if os.path.isfile(function):
#                 if interpolant is None:
#                     interpolant='linear'
#                 if x_min or x_max:
#                     raise GalSimIncompatibleValuesError(
#                         "Cannot pass x_min or x_max with a filename argument",
#                         function=function, x_min=x_min, x_max=x_max)
#                 function = LookupTable.from_file(function, interpolant=interpolant)
#                 x_min = function.x_min
#                 x_max = function.x_max
#             else:
#                 try:
#                     function = utilities.math_eval('lambda x : ' + function)
#                     if x_min is not None: # is not None in case x_min=0.
#                         function(x_min)
#                     else:
#                         # Somebody would be silly to pass a string for evaluation without x_min,
#                         # but we'd like to throw reasonable errors in that case anyway
#                         function(0.6) # A value unlikely to be a singular point of a function
#                 except Exception as e:
#                     raise GalSimValueError(
#                         "String function must either be a valid filename or something that "
#                         "can eval to a function of x.\n"
#                         "Caught error: {0}".format(e), self._function)
#         else:
#             # Check that the function is actually a function
#             if not hasattr(function, '__call__'):
#                 raise TypeError('function must be a callable function or a string')
#             if interpolant:
#                 raise GalSimIncompatibleValuesError(
#                     "Cannot provide an interpolant with a callable function argument",
#                     interpolant=interpolant, function=function)
#             if isinstance(function, LookupTable):
#                 if x_min or x_max:
#                     raise GalSimIncompatibleValuesError(
#                         "Cannot provide x_min or x_max with a LookupTable function",
#                         function=function, x_min=x_min, x_max=x_max)
#                 x_min = function.x_min
#                 x_max = function.x_max
#             else:
#                 if x_min is None or x_max is None:
#                     raise GalSimIncompatibleValuesError(
#                         "Must provide x_min and x_max when function argument is a regular "
#                         "python callable function",
#                         function=function, x_min=x_min, x_max=x_max)

#             self._function = function # Save the inputs to be used in repr

#         # Compute the probability distribution function, pdf(x)
#         if (npoints is None and isinstance(function, LookupTable) and
#             not function.x_log and not function.f_log):
#             xarray = np.array(function.x, dtype=float)
#             pdf = np.array(function.f, dtype=float)
#             # Set up pdf, so cumsum basically does a cumulative trapz integral
#             # On Python 3.4, doing pdf[1:] += pdf[:-1] the last value gets messed up.
#             # Writing it this way works.  (Maybe slightly slower though, so if we stop
#             # supporting python 3.4, consider switching to the += version.)
#             pdf[1:] = pdf[1:] + pdf[:-1]
#             pdf[1:] *= np.diff(xarray)
#             pdf[0] = 0.
#         else:
#             if npoints is None: npoints = 256
#             xarray = x_min+(1.*x_max-x_min)/(npoints-1)*np.array(range(npoints),float)
#             # Integrate over the range of x in case the function is doing something weird here.
#             pdf = [0.] + [integ.int1d(function, xarray[i], xarray[i+1])
#                           for i in range(npoints - 1)]
#             pdf = np.array(pdf)

#         # Check that the probability is nonnegative
#         if not np.all(pdf >= 0.):
#             raise GalSimValueError('Negative probability found in DistDeviate.',function)

#         # Compute the cumulative distribution function = int(pdf(x),x)
#         cdf = np.cumsum(pdf)

#         # Quietly renormalize the probability if it wasn't already normalized
#         totalprobability = cdf[-1]
#         cdf /= totalprobability

#         self._inverse_cdf = LookupTable(cdf, xarray, interpolant='linear')
#         self.x_min = x_min
#         self.x_max = x_max

#     def val(self, p):
#         r"""
#         Return the value :math:`x` of the input function to `DistDeviate` such that ``p`` =
#         :math:`F(x)`, where :math:`F` is the cumulattive probability distribution function:

#         .. math::

#             F(x) = \int_{-\infty}^x \mathrm{pdf}(t) dt

#         This function is typically called by `__call__`, which generates a random p
#         between 0 and 1 and calls ``self.val(p)``.

#         Parameters:
#             p:      The desired cumulative probabilty p.

#         Returns:
#             the corresponding x such that :math:`p = F(x)`.
#         """
#         if p<0 or p>1:
#             raise GalSimRangeError('Invalid cumulative probability for DistDeviate', p, 0., 1.)
#         return self._inverse_cdf(p)

#     def __call__(self):
#         """Draw a new random number from the distribution.
#         """
#         return self._inverse_cdf(self._rng.generate1())

#     def generate(self, array):
#         """Generate many pseudo-random values, filling in the values of a numpy array.
#         """
#         p = np.empty_like(array)
#         BaseDeviate.generate(self, p)  # Fill with unform deviate values
#         np.copyto(array, self._inverse_cdf(p)) # Convert from p -> x

#     def add_generate(self, array):
#         """Generate many pseudo-random values, adding them to the values of a numpy array.
#         """
#         p = np.empty_like(array)
#         BaseDeviate.generate(self, p)
#         array += self._inverse_cdf(p)

#     def __repr__(self):
#         return ('galsim.DistDeviate(seed=%r, function=%r, x_min=%r, x_max=%r, interpolant=%r, '
#                 'npoints=%r)')%(self._seed_repr(), self._function, self._xmin, self._xmax,
#                                 self._interpolant, self._npoints)
#     def __str__(self):
#         return 'galsim.DistDeviate(function="%s", x_min=%s, x_max=%s, interpolant=%s, npoints=%s)'%(
#                 self._function, self._xmin, self._xmax, self._interpolant, self._npoints)

#     def __eq__(self, other):
#         return (self is other or
#                 (isinstance(other, DistDeviate) and
#                  self.serialize() == other.serialize() and
#                  self._function == other._function and
#                  self._xmin == other._xmin and
#                  self._xmax == other._xmax and
#                  self._interpolant == other._interpolant and
#                  self._npoints == other._npoints))


# class GalSimBitGenerator(np.random.BitGenerator):
#     """A numpy.random.BitGenerator that uses the GalSim C++-layer random number generator
#     for the random bit generation.

#     Parameters:
#         rng:    The galsim.BaseDeviate object to use for the underlying bit generation.
#     """
#     def __init__(self, rng):
#         super().__init__(0)
#         self.rng = rng
#         self.rng._rng.setup_bitgen(self.capsule)

# def permute(rng, *args):
#     """Randomly permute one or more lists.

#     If more than one list is given, then all lists will have the same random permutation
#     applied to it.

#     Parameters:
#         rng:    The random number generator to use. (This will be converted to a `UniformDeviate`.)
#         args:   Any number of lists to be permuted.
#     """
#     from .random import UniformDeviate
#     ud = UniformDeviate(rng)
#     if len(args) == 0:
#         raise TypeError("permute called with no lists to permute")

#     # We use an algorithm called the Knuth shuffle, which is based on the Fisher-Yates shuffle.
#     # See http://en.wikipedia.org/wiki/Fisher-Yates_shuffle for more information.
#     n = len(args[0])
#     for i in range(n-1,1,-1):
#         j = int((i+1) * ud())
#         if j == i+1: j = i  # I'm not sure if this is possible, but just in case...
#         for lst in args:
#             lst[i], lst[j] = lst[j], lst[i]
