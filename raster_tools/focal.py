import dask.array as da
import numba as nb
import numpy as np
from dask_image import ndfilters
from functools import partial

from raster_tools import Raster
from raster_tools.raster import is_raster_class
from ._types import F64, promote_dtype_to_float, promote_data_dtype
from ._utils import is_bool, is_float, is_int, is_str


__all__ = [
    "check_kernel",
    "convolve",
    "correlate",
    "focal",
    "get_focal_window",
]


ngjit = nb.jit(nopython=True, nogil=True)


@ngjit
def _agg_nan_min(x):
    return np.nanmin(x)


@ngjit
def _agg_nan_max(x):
    return np.nanmax(x)


@ngjit
def _agg_nan_mean(x):
    return np.nanmean(x)


@ngjit
def _agg_nan_median(x):
    return np.nanmedian(x)


@ngjit
def _agg_nan_sum(x):
    return np.nansum(x)


@ngjit
def _agg_nan_var(x):
    return np.nanvar(x)


@ngjit
def _agg_nan_std(x):
    return np.nanstd(x)


@ngjit
def _agg_nan_unique(x):
    # Create set of floats. {1.0} is a hack to tell numba.jit what type the set
    # contains
    s = {1.0}
    s.clear()
    for v in x.ravel():
        if not np.isnan(v):
            s.add(v)
    if len(s):
        return len(s)
    return np.nan


@ngjit
def _agg_nan_mode(x):
    one: nb.types.uint16 = 1
    c = {}
    x = x.ravel()
    j: nb.types.uint16 = 0
    for i in range(x.size):
        v = x[i]
        if not np.isnan(v):
            if v in c:
                c[v] += one
            else:
                c[v] = one
            x[j] = v
            j += one
    vals = x[:j]
    if len(vals) == 0:
        return np.nan
    vals.sort()
    cnts = np.empty(len(vals), dtype=nb.types.uint16)
    for i in range(len(vals)):
        cnts[i] = c[vals[i]]
    return vals[np.argmax(cnts)]


@ngjit
def _agg_nan_entropy(x):
    c = {}
    one: nb.types.uint16 = 1
    n: nb.types.uint16 = 0
    for v in x.ravel():
        if not np.isnan(v):
            if v in c:
                c[v] += one
            else:
                c[v] = one
            n += one
    if len(c) == 0:
        return np.nan
    entr = 0.0
    frac = one / n
    for cnt in c.values():
        p = cnt * frac
        entr -= p * np.log(p)
    return entr


@ngjit
def _agg_nan_asm(x):
    c = {}
    one: nb.types.uint16 = 1
    n: nb.types.uint16 = 0
    for v in x.ravel():
        if not np.isnan(v):
            if v in c:
                c[v] += one
            else:
                c[v] = one
            n += one
    if len(c) == 0:
        return np.nan
    asm = 0.0
    frac = one / n
    for cnt in c.values():
        p = cnt * frac
        asm += p * p
    return asm


@ngjit
def _focal_chunk(chunk, kernel, func):
    out = np.empty_like(chunk)
    rows, cols = chunk.shape
    krows, kcols = kernel.shape
    kr_top = (krows - 1) // 2
    kr_bot = krows // 2
    kc_left = (kcols - 1) // 2
    kc_right = kcols // 2
    r_ovlp = max(kr_top, kr_bot)
    c_ovlp = max(kc_left, kc_right)
    kernel_values = np.empty(kernel.size, dtype=chunk.dtype)
    kernel = kernel.ravel()

    # iterate over rows, skipping outer overlap rows
    for r in range(r_ovlp, rows - r_ovlp):
        # iterate over cols, skipping outer overlap cols
        for c in range(c_ovlp, cols - c_ovlp):
            kernel_values.fill(np.nan)
            # Kernel flat index
            ki = 0
            # iterate over kernel footprint, this extends into overlap regions
            # at edges
            for kr in range(r - kr_top, r + kr_bot + 1):
                for kc in range(c - kc_left, c + kc_right + 1):
                    if kernel[ki]:
                        kernel_values[ki] = chunk[kr, kc]
                    ki += 1
            out[r, c] = func(kernel_values)
    return out


@nb.jit(nopython=True, nogil=True, parallel=True)
def _correlate2d_chunk(chunk, kernel):
    out = np.empty_like(chunk)
    rows, cols = chunk.shape
    krows, kcols = kernel.shape
    kr_top = (krows - 1) // 2
    kr_bot = krows // 2
    kc_left = (kcols - 1) // 2
    kc_right = kcols // 2
    r_ovlp = max(kr_top, kr_bot)
    c_ovlp = max(kc_left, kc_right)
    kernel = kernel.ravel()

    # iterate over rows, skipping outer overlap rows
    for r in nb.prange(r_ovlp, rows - r_ovlp):
        # iterate over cols, skipping outer overlap cols
        for c in nb.prange(c_ovlp, cols - c_ovlp):
            # Kernel flat index
            ki = 0
            # iterate over kernel footprint, this extends into overlap regions
            # at edges
            v = 0.0
            for kr in range(r - kr_top, r + kr_bot + 1):
                for kc in range(c - kc_left, c + kc_right + 1):
                    val = chunk[kr, kc]
                    if not np.isnan(val):
                        v += kernel[ki] * chunk[kr, kc]
                    ki += 1
            out[r, c] = v
    return out


@ngjit
def _get_offsets(kernel_shape):
    """
    Returns the number of cells on either side of kernel center in both
    directions.
    """
    krows, kcols = kernel_shape
    kr_top = (krows - 1) // 2
    kr_bot = krows // 2
    kc_left = (kcols - 1) // 2
    kc_right = kcols // 2
    return ((kr_top, kr_bot), (kc_left, kc_right))


def _focal_dask_map(data, chunk_func, kernel, boundary=np.nan):
    offsets = _get_offsets(kernel.shape)
    # map_overlap does not support asymmetrical padding so take max. This adds
    # at most one extra pixel to each dim.
    rpad = max(offsets[0])
    cpad = max(offsets[1])
    return data.map_overlap(
        chunk_func,
        depth={0: rpad, 1: cpad},
        boundary=boundary,
        dtype=data.dtype,
        meta=np.array((), dtype=data.dtype),
    )


def _focal_dispatch(
    operation, data, kernel, kernel_func=None, boundary=np.nan
):
    # TODO: check for cupy eventually
    if operation == "correlate":
        chunk_func = partial(_correlate2d_chunk, kernel=kernel)
    else:
        chunk_func = partial(_focal_chunk, kernel=kernel, func=kernel_func)
    return _focal_dask_map(data, chunk_func, kernel, boundary=boundary)


def check_kernel(kernel):
    if not isinstance(kernel, np.ndarray):
        raise TypeError("Kernel must be numpy.ndarray")
    if len(kernel.shape) != 2:
        raise ValueError("Kernel must be 2D")
    if np.isnan(kernel).any():
        raise ValueError("Kernel can't contain NaN values")


def _check_data(data):
    if not isinstance(data, (np.ndarray, da.Array)):
        raise TypeError("Kernel must be numpy.ndarray or dask.array.Array")
    if len(data.shape) != 2:
        raise ValueError("Data must be 2D")


_MODE_TO_DASK_BOUNDARY = {
    "reflect": "reflect",
    "nearest": "nearest",
    "wrap": "periodic",
    "constant": "constant",
}
_VALID_CORRELATE_MODES = frozenset(_MODE_TO_DASK_BOUNDARY.keys())


def _correlate(data, kernel, mode="constant", cval=0.0, nan_aware=False):
    """Cross-correlates a `kernel` with `data`.

    This function can be used for convolution as well; just rotate the kernel
    180 degress (e.g. ``kernel = kernel[::-1, ::-1])`` before calling this
    function.

    Parameters
    ----------
    data : 2D ndarray or dask array
        Data to cross-correlate the kernel with.
    kernel : 2D ndarray
        Kernel to apply to the data through cross-correlation.
    mode : {'reflect', 'nearest', 'wrap', 'constant'}, optional
        The mode to use for the edges of the data. Default is 'constant'.
    cval : scalar, optional
        The value to use when `mode` is 'constant'. Default is ``0.0``.
    nan_aware : bool, optional
        If ``True``, NaN values are ignored during correlation. If ``False``,
        a faster correlation algorithm can be used. Default is ``False``.

    Returns
    -------
    correlated : 2D dask array
        The cross-correlation result as a lazy dask array.

    """
    _check_data(data)
    check_kernel(kernel)
    if mode not in _VALID_CORRELATE_MODES:
        raise ValueError(f"Invalid mode: '{mode}'")
    if isinstance(data, np.ndarray):
        data = da.from_array(data)
    if nan_aware:
        data = promote_data_dtype(data)
    if is_bool(kernel.dtype):
        kernel = kernel.astype(int)
    if is_float(data.dtype) and is_int(kernel.dtype):
        kernel = kernel.astype(data.dtype)
    if is_int(data.dtype) and is_float(kernel.dtype):
        data = promote_data_dtype(data)

    if nan_aware:
        boundary = _MODE_TO_DASK_BOUNDARY[mode]
        if boundary == "constant":
            boundary = cval
        return _focal_dispatch("correlate", data, kernel, boundary=boundary)
    # Shift pixel origins to match ESRI behavior for even shaped kernels
    shift_origin = [d % 2 == 0 for d in kernel.shape]
    origin = [-1 if shift else 0 for shift in shift_origin]
    return ndfilters.correlate(
        data, kernel, mode=mode, cval=cval, origin=origin
    )


# Focal ops that promote dtype to float
FOCAL_PROMOTING_OPS = frozenset(
    (
        "asm",
        "entropy",
        "mean",
        "median",
        "std",
        "var",
    )
)


FOCAL_STATS = frozenset(
    (
        "asm",
        "entropy",
        "max",
        "mean",
        "median",
        "mode",
        "min",
        "std",
        "sum",
        "var",
        "unique",
    )
)


def _focal(data, kernel, stat, nan_aware=False):
    """Apply a focal stat function.

    Applies the `stat` function to the `data` using `kernel` to determine the
    neighborhood for each pixel. `nan_aware` indicates whether the filter
    should handle NaN values. If `nan_aware` is False, optimizations may be
    made.

    """
    if stat not in FOCAL_STATS:
        raise ValueError(f"Unknown focal stat: '{stat}'")
    _check_data(data)
    check_kernel(kernel)

    if isinstance(data, np.ndarray):
        data = da.from_array(data)
    if nan_aware or stat in FOCAL_PROMOTING_OPS:
        data = promote_data_dtype(data)

    kernel = kernel.astype(bool)
    if stat == "asm":
        return _focal_dispatch("focal", data, kernel, _agg_nan_asm)
    elif stat == "entropy":
        return _focal_dispatch("focal", data, kernel, _agg_nan_entropy)
    elif stat == "min":
        if not nan_aware:
            return ndfilters.minimum_filter(
                data, footprint=kernel, mode="nearest"
            )
        else:
            return _focal_dispatch("focal", data, kernel, _agg_nan_min)
    elif stat == "max":
        if not nan_aware:
            return ndfilters.maximum_filter(
                data, footprint=kernel, mode="nearest"
            )
        else:
            return _focal_dispatch("focal", data, kernel, _agg_nan_max)
    elif stat == "mode":
        return _focal_dispatch("focal", data, kernel, _agg_nan_mode)
    elif stat == "mean":
        return _focal_dispatch("focal", data, kernel, _agg_nan_mean)
    elif stat == "median":
        return _focal_dispatch("focal", data, kernel, _agg_nan_median)
    elif stat == "std":
        return _focal_dispatch("focal", data, kernel, _agg_nan_std)
    elif stat == "var":
        return _focal_dispatch("focal", data, kernel, _agg_nan_var)
    elif stat == "sum":
        if not nan_aware:
            return ndfilters.correlate(data, kernel, mode="constant")
        else:
            return _focal_dispatch("focal", data, kernel, _agg_nan_sum)
    elif stat == "unique":
        return _focal_dispatch("focal", data, kernel, _agg_nan_unique)


def focal(raster, focal_type, width_or_radius, height=None):
    """Applies a focal filter to raster bands individually.

    The filter uses a window/footprint that is created using the
    `width_or_radius` and `height` parameters. The window can be a
    rectangle, circle or annulus.

    Parameters
    ----------
    raster : Raster or path str
        The raster to perform the focal operation on.
    focal_type : str
        Specifies the aggregation function to apply to the focal
        neighborhood at each pixel. Can be one of the following string
        values:

        'min'
            Finds the minimum value in the neighborhood.
        'max'
            Finds the maximum value in the neighborhood.
        'mean'
            Finds the mean of the neighborhood.
        'median'
            Finds the median of the neighborhood.
        'mode'
            Finds the mode of the neighborhood.
        'sum'
            Finds the sum of the neighborhood.
        'std'
            Finds the standard deviation of the neighborhood.
        'var'
            Finds the variance of the neighborhood.
        'asm'
            Angular second moment. Applies -sum(P(g)**2) where P(g) gives
            the probability of g within the neighborhood.
        'entropy'
            Calculates the entropy. Applies -sum(P(g) * log(P(g))). See
            'asm' above.
        'unique'
            Calculates the number of unique values in the neighborhood.
    width_or_radius : int or 2-tuple of ints
        If an int and `height` is `None`, specifies the radius of a circle
        window. If an int and `height` is also an int, specifies the width
        of a rectangle window. If a 2-tuple of ints, the values specify the
        inner and outer radii of an annulus window.
    height : int or None
        If `None` (default), `width_or_radius` will be used to construct a
        circle or annulus window. If an int, specifies the height of a
        rectangle window.

    Returns
    -------
    Raster
        The resulting raster with focal filter applied to each band. The
        bands will have the same shape as the original Raster.

    """
    if not is_raster_class(raster) and not is_str(raster):
        raise TypeError(
            "First argument must be a Raster or path string to a raster"
        )
    elif is_str(raster):
        raster = Raster(raster)
    if focal_type not in FOCAL_STATS:
        raise ValueError(f"Unknown focal operation: '{focal_type}'")

    window = get_focal_window(width_or_radius, height)
    rs = raster.copy()
    data = rs._rs.data
    final_dtype = data.dtype

    # Convert to float and fill nulls with nan, if needed
    upcast = False
    if raster._masked:
        new_dtype = promote_dtype_to_float(raster.dtype)
        upcast = new_dtype != data.dtype
        if upcast:
            data = data.astype(new_dtype)
        data = da.where(~raster._mask, data, np.nan)

    for bnd in range(data.shape[0]):
        data[bnd] = _focal(data[bnd], window, focal_type, raster._masked)

    # Cast back to int, if needed
    if upcast and focal_type not in FOCAL_PROMOTING_OPS:
        data = data.astype(final_dtype)

    rs._rs.data = data
    return rs


def get_focal_window(width_or_radius, height=None):
    """Get a rectangle, circle, or annulus focal window.

    A rectangle window is simply a NxM grid of ``True`` values. A circle window
    is a grid with a centered circle of ``True`` values surrounded by `False`
    values. The circle extends to the edge of the grid. An annulus window is
    the same as a circle window but  has a nested circle of `False` values
    inside the main circle.

    Parameters
    ----------
    width_or_radius : int or 2-tuple of ints
        If an int and `height` is `None`, specifies the radius of a circle
        window. If an int and `height` is also an int, specifies the width of
        a rectangle window. If a 2-tuple of ints, the values specify the inner
        and outer radii of an annulus window.
    height : int or None
        If `None` (default), `width_or_radius` will be used to construct a
        circle or annulus window. If an int, specifies the height of a
        rectangle window.

    Returns
    -------
    window : ndarray
        A focal window containing bools with the specified pattern.

    """
    if isinstance(width_or_radius, (list, tuple)):
        if len(width_or_radius) != 2:
            raise ValueError(
                "If width_or_radius is a sequence, it must be size 2"
            )
        if width_or_radius[0] >= width_or_radius[1]:
            raise ValueError(
                "First radius value must be less than or equal to the second."
            )
    else:
        width_or_radius = [width_or_radius]
    for value in width_or_radius:
        if not is_int(value):
            raise TypeError(
                f"width_or_radius values must be integers: {value}"
            )
        elif value <= 0:
            raise ValueError(
                "Window width or radius values must be greater than 0."
                f" Got {value}"
            )
    if height is not None:
        if len(width_or_radius) == 2:
            raise ValueError(
                "height must be None if width_or_radius indicates annulus"
            )
        if not is_int(height):
            raise TypeError(f"height must be an integer or None: {height}")
        elif height <= 0:
            raise ValueError(
                f"Window height must be greater than 0. Got {height}"
            )

    window_out = None
    windows = []
    if height is None:
        for rvalue in width_or_radius:
            width = ((rvalue - 1) * 2) + 1
            height = width
            r = (width - 1) // 2
            window = np.zeros((height, width), dtype=bool)
            for x in range(width):
                for y in range(height):
                    rxy = np.sqrt((x - r) ** 2 + (y - r) ** 2)
                    if rxy <= r:
                        window[x, y] = True
            windows.append(window)
        if len(windows) != 2:
            window_out = windows[0]
        else:
            w1, w2 = windows
            padding = (np.array(w2.shape) - np.array(w1.shape)) // 2
            w1 = np.pad(w1, padding, mode="constant", constant_values=False)
            w2[w1] = False
            window_out = w2
    else:
        width = width_or_radius[0]
        window_out = np.ones((width, height), dtype=bool)
    return window_out


def correlate(raster, kernel, mode="constant", cval=0.0):
    """Cross-correlate `kernel` with each band individually. Returns a new
    Raster.

    The kernel is applied to each band in isolation so returned raster has
    the same shape as the original.

    Parameters
    ----------
    raster : Raster or path str
        The raster to cross-correlate `kernel` with. Can be multibanded.
    kernel : array_like
        2D array of kernel weights
    mode : {'reflect', 'constant', 'nearest', 'wrap'}, optional
        Determines how the data is extended beyond its boundaries. The
        default is 'constant'.

        'reflect' (d c b a | a b c d | d c b a)
            The data pixels are reflected at the boundaries.
        'constant' (k k k k | a b c d | k k k k)
            A constant value determined by `cval` is used to extend the
            data pixels.
        'nearest' (a a a a | a b c d | d d d d)
            The data is extended using the boundary pixels.
        'wrap' (a b c d | a b c d | a b c d)
            The data is extended by wrapping to the opposite side of the
            grid.
    cval : scalar, optional
        Value used to fill when `mode` is 'constant'. Default is 0.0.

    Returns
    -------
    Raster
        The resulting new Raster.
    """
    if not is_raster_class(raster) and not is_str(raster):
        raise TypeError(
            "First argument must be a Raster or path string to a raster"
        )
    elif is_str(raster):
        raster = Raster(raster)
    kernel = np.asarray(kernel)
    check_kernel(kernel)
    rs = raster.copy()
    if is_float(kernel.dtype) and is_int(rs.dtype):
        rs._rs.data = rs._rs.data.astype(F64)
    data = rs._rs.data
    final_dtype = data.dtype

    # Convert to float and fill nulls with nan, if needed
    upcast = False
    if raster._masked:
        new_dtype = promote_dtype_to_float(data.dtype)
        upcast = new_dtype != data.dtype
        if upcast:
            data = data.astype(new_dtype)
        data = da.where(raster._mask, np.nan, data)

    for bnd in range(data.shape[0]):
        data[bnd] = _correlate(
            data[bnd], kernel, mode=mode, cval=cval, nan_aware=rs._masked
        )

    # Cast back to int, if needed
    if upcast:
        data = data.astype(final_dtype)

    rs._rs.data = data
    return rs


def convolve(raster, kernel, mode="constant", cval=0.0):
    """Convolve `kernel` with each band individually. Returns a new Raster.

    This is the same as correlation but the kernel is rotated 180 degrees,
    e.g. ``kernel = kernel[::-1, ::-1]``.  The kernel is applied to each
    band in isolation so the returned raster has the same shape as the
    original.

    Parameters
    ----------
    raster : Raster
        The raster to convolve `kernel` with. Can be multibanded.
    kernel : array_like
        2D array of kernel weights
    mode : {'reflect', 'constant', 'nearest', 'wrap'}, optional
        Determines how the data is extended beyond its boundaries. The
        default is 'constant'.

        'reflect' (d c b a | a b c d | d c b a)
            The data pixels are reflected at the boundaries.
        'constant' (k k k k | a b c d | k k k k)
            A constant value determined by `cval` is used to extend the
            data pixels.
        'nearest' (a a a a | a b c d | d d d d)
            The data is extended using the boundary pixels.
        'wrap' (a b c d | a b c d | a b c d)
            The data is extended by wrapping to the opposite side of the
            grid.
    cval : scalar, optional
        Value used to fill when `mode` is 'constant'. Default is 0.0.

    Returns
    -------
    Raster
        The resulting new Raster.
    """
    kernel = np.asarray(kernel)
    check_kernel(kernel)
    kernel = kernel[::-1, ::-1].copy()
    return correlate(raster, kernel, mode=mode, cval=cval)
