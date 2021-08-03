import dask
import numpy as np
import scipy
import unittest
import rioxarray as rxr
import xarray as xr

from raster_tools import Raster
from raster_tools.raster import (
    _BINARY_ARITHMETIC_OPS,
    _BINARY_LOGICAL_OPS,
    _get_focal_window,
)
from raster_tools._types import (
    DTYPE_INPUT_TO_DTYPE,
    U8,
    U16,
    U32,
    U64,
    I8,
    I16,
    I32,
    I64,
    F16,
    F32,
    F64,
    F128,
    BOOL,
)


def rs_eq_array(rs, ar):
    return (rs._rs.values == ar).all()


def array_eq_all(ar1, ar2):
    return (ar1 == ar2).all()


class TestRasterCtor(unittest.TestCase):
    def test_raster_ctor(self):
        for nprs in [np.ones((6, 6)), np.ones((1, 6, 6)), np.ones((4, 5, 5))]:
            rs = Raster(nprs)
            shape = nprs.shape if len(nprs.shape) == 3 else (1, *nprs.shape)
            self.assertEqual(rs.shape, shape)
            self.assertTrue(rs_eq_array(rs, nprs))

        with self.assertRaises(ValueError):
            rs = Raster(np.ones(4))
        with self.assertRaises(ValueError):
            rs = Raster(np.ones((1, 3, 4, 4)))


class TestRasterMath(unittest.TestCase):
    def setUp(self):
        self.rs1 = Raster("test/data/elevation_small.tif")
        self.rs1_np = self.rs1._rs.values
        self.rs2 = Raster("test/data/elevation2_small.tif")
        self.rs2_np = self.rs2._rs.values

    def tearDown(self):
        self.rs1.close()
        self.rs2.close()

    def test_add(self):
        # Raster + raster
        truth = self.rs1_np + self.rs2_np
        rst = self.rs1.add(self.rs2)
        self.assertTrue(rs_eq_array(rst, truth))
        rst = self.rs2.add(self.rs1)
        self.assertTrue(rs_eq_array(rst, truth))
        rst = self.rs1 + self.rs2
        self.assertTrue(rs_eq_array(rst, truth))
        rst = self.rs2 + self.rs1
        self.assertTrue(rs_eq_array(rst, truth))
        # Raster + scalar
        for v in [-23, 0, 1, 2, 321]:
            truth = self.rs1_np + v
            rst = self.rs1.add(v)
            self.assertTrue(rs_eq_array(rst, truth))
            rst = self.rs1 + v
            self.assertTrue(rs_eq_array(rst, truth))
            rst = v + self.rs1
            self.assertTrue(rs_eq_array(rst, truth))
        for v in [-23.3, 0.0, 1.0, 2.0, 321.4]:
            truth = self.rs1_np + v
            rst = self.rs1.add(v)
            self.assertTrue(rs_eq_array(rst, truth))
            rst = self.rs1 + v
            self.assertTrue(rs_eq_array(rst, truth))
            rst = v + self.rs1
            self.assertTrue(rs_eq_array(rst, truth))

    def test_subtract(self):
        # Raster - raster
        truth = self.rs1_np - self.rs2_np
        rst = self.rs1.subtract(self.rs2)
        self.assertTrue(rs_eq_array(rst, truth))
        rst = self.rs2.subtract(self.rs1)
        self.assertTrue(rs_eq_array(rst, -truth))
        rst = self.rs1 - self.rs2
        self.assertTrue(rs_eq_array(rst, truth))
        rst = self.rs2 - self.rs1
        self.assertTrue(rs_eq_array(rst, -truth))
        # Raster - scalar
        for v in [-1359, 0, 1, 2, 42]:
            truth = self.rs1_np - v
            rst = self.rs1.subtract(v)
            self.assertTrue(rs_eq_array(rst, truth))
            rst = self.rs1 - v
            self.assertTrue(rs_eq_array(rst, truth))
            rst = v - self.rs1
            self.assertTrue(rs_eq_array(rst, -truth))
        for v in [-1359.2, 0.0, 1.0, 2.0, 42.5]:
            truth = self.rs1_np - v
            rst = self.rs1.subtract(v)
            self.assertTrue(rs_eq_array(rst, truth))
            rst = self.rs1 - v
            self.assertTrue(rs_eq_array(rst, truth))
            rst = v - self.rs1
            self.assertTrue(rs_eq_array(rst, -truth))

    def test_mult(self):
        # Raster * raster
        truth = self.rs1_np * self.rs2_np
        rst = self.rs1.multiply(self.rs2)
        self.assertTrue(rs_eq_array(rst, truth))
        rst = self.rs2.multiply(self.rs1)
        self.assertTrue(rs_eq_array(rst, truth))
        rst = self.rs1 * self.rs2
        self.assertTrue(rs_eq_array(rst, truth))
        rst = self.rs2 * self.rs1
        self.assertTrue(rs_eq_array(rst, truth))
        # Raster * scalar
        for v in [-123, 0, 1, 2, 345]:
            truth = self.rs1_np * v
            rst = self.rs1.multiply(v)
            self.assertTrue(rs_eq_array(rst, truth))
            rst = self.rs1 * v
            self.assertTrue(rs_eq_array(rst, truth))
            rst = v * self.rs1
            self.assertTrue(rs_eq_array(rst, truth))
        for v in [-123.9, 0.0, 1.0, 2.0, 345.3]:
            truth = self.rs1_np * v
            rst = self.rs1.multiply(v)
            self.assertTrue(rs_eq_array(rst, truth))
            rst = self.rs1 * v
            self.assertTrue(rs_eq_array(rst, truth))
            rst = v * self.rs1
            self.assertTrue(rs_eq_array(rst, truth))

    def test_div(self):
        # Raster / raster
        truth = self.rs1_np / self.rs2_np
        rst = self.rs1.divide(self.rs2)
        self.assertTrue(rs_eq_array(rst, truth))
        rst = self.rs2.divide(self.rs1)
        self.assertTrue(rs_eq_array(rst, 1 / truth))
        rst = self.rs1 / self.rs2
        self.assertTrue(rs_eq_array(rst, truth))
        rst = self.rs2 / self.rs1
        self.assertTrue(rs_eq_array(rst, 1 / truth))
        # Raster / scalar, scalar / raster
        for v in [-123, -1, 1, 2, 345]:
            truth = self.rs1_np / v
            rst = self.rs1.divide(v)
            self.assertTrue(rs_eq_array(rst, truth))
            rst = self.rs1 / v
            self.assertTrue(rs_eq_array(rst, truth))
            rst = v / self.rs1
            np.testing.assert_array_almost_equal(rst._rs.values, 1 / truth)
        for v in [-123.8, -1.0, 1.0, 2.0, 345.6]:
            truth = self.rs1_np / v
            rst = self.rs1.divide(v)
            self.assertTrue(rs_eq_array(rst, truth))
            rst = self.rs1 / v
            self.assertTrue(rs_eq_array(rst, truth))
            rst = v / self.rs1
            np.testing.assert_array_almost_equal(rst._rs.values, 1 / truth)

    def test_mod(self):
        # Raster % raster
        truth = self.rs1_np % self.rs2_np
        rst = self.rs1.mod(self.rs2)
        self.assertTrue(rs_eq_array(rst, truth))
        rst = self.rs1 % self.rs2
        self.assertTrue(rs_eq_array(rst, truth))
        truth = self.rs2_np % self.rs1_np
        rst = self.rs2.mod(self.rs1)
        self.assertTrue(rs_eq_array(rst, truth))
        rst = self.rs2 % self.rs1
        self.assertTrue(rs_eq_array(rst, truth))
        # Raster % scalar, scalar % raster
        for v in [-123, -1, 1, 2, 345]:
            truth = self.rs1_np % v
            rst = self.rs1.mod(v)
            self.assertTrue(rs_eq_array(rst, truth))
            rst = self.rs1 % v
            self.assertTrue(rs_eq_array(rst, truth))
            truth = v % self.rs1_np
            rst = v % self.rs1
            self.assertTrue(rs_eq_array(rst, truth))
        for v in [-123.8, -1.0, 1.0, 2.0, 345.6]:
            truth = self.rs1_np % v
            rst = self.rs1.mod(v)
            self.assertTrue(rs_eq_array(rst, truth))
            rst = self.rs1 % v
            self.assertTrue(rs_eq_array(rst, truth))
            truth = v % self.rs1_np
            rst = v % self.rs1
            self.assertTrue(rs_eq_array(rst, truth))

    def test_power(self):
        # Raster ** raster
        rs1 = self.rs1 / self.rs1._rs.max().values.item() * 2
        rs2 = self.rs2 / self.rs2._rs.max().values.item() * 2
        rs1_np = self.rs1_np / self.rs1_np.max() * 2
        rs2_np = self.rs2_np / self.rs2_np.max() * 2
        truth = rs1_np ** rs2_np
        rst = rs1.pow(rs2)
        self.assertTrue(rs_eq_array(rst, truth))
        rst = rs2.pow(rs1)
        self.assertTrue(rs_eq_array(rst, truth))
        rst = rs1 ** rs2
        self.assertTrue(rs_eq_array(rst, truth))
        truth = rs2_np ** rs1_np
        rst = rs2 ** rs1
        self.assertTrue(rs_eq_array(rst, truth))
        # Raster ** scalar, scalar ** raster
        for v in [-10, -1, 1, 2, 11]:
            truth = rs1_np ** v
            rst = rs1.pow(v)
            self.assertTrue(rs_eq_array(rst, truth))
            rst = rs1 ** v
            self.assertTrue(rs_eq_array(rst, truth))
            # Avoid complex numbers issues
            if v >= 0:
                truth = v ** rs1_np
                rst = v ** rs1
                self.assertTrue(rs_eq_array(rst, truth))
        for v in [-10.5, -1.0, 1.0, 2.0, 11.3]:
            truth = rs1_np ** v
            rst = rs1.pow(v)
            self.assertTrue(rs_eq_array(rst, truth))
            rst = rs1 ** v
            self.assertTrue(rs_eq_array(rst, truth))
            # Avoid complex numbers issues
            if v >= 0:
                truth = v ** rs1_np
                rst = v ** rs1
                self.assertTrue(rs_eq_array(rst, truth))

    def test_sqrt(self):
        rs = self.rs1 + np.abs(self.rs1_np.min())
        rsnp = rs._rs.values
        truth = np.sqrt(rsnp)
        self.assertTrue(rs_eq_array(rs.sqrt(), truth))


class TestLogicalOps(unittest.TestCase):
    def setUp(self):
        self.rs1 = Raster("test/data/elevation_small.tif")
        self.rs1_np = self.rs1._rs.values
        self.rs2 = Raster("test/data/elevation2_small.tif")
        self.rs2_np = self.rs2._rs.values

    def tearDown(self):
        self.rs1.close()
        self.rs2.close()

    def test_eq(self):
        for v, vnp in [
            (self.rs2, self.rs2_np),
            (0, 0),
            (self.rs1_np[0, 10, 10], self.rs1_np[0, 10, 10]),
        ]:
            truth = self.rs1_np == vnp
            rst = self.rs1.eq(v)
            self.assertTrue(rs_eq_array(rst, truth))
            rst = self.rs1 == v
            self.assertTrue(rs_eq_array(rst, truth))

    def test_ne(self):
        for v, vnp in [
            (self.rs2, self.rs2_np),
            (0, 0),
            (self.rs1_np[0, 10, 10], self.rs1_np[0, 10, 10]),
        ]:
            truth = self.rs1_np != vnp
            rst = self.rs1.ne(v)
            self.assertTrue(rs_eq_array(rst, truth))
            rst = self.rs1 != v
            self.assertTrue(rs_eq_array(rst, truth))

    def test_le(self):
        for v, vnp in [
            (self.rs2, self.rs2_np),
            (0, 0),
            (self.rs1_np[0, 10, 10], self.rs1_np[0, 10, 10]),
        ]:
            truth = self.rs1_np <= vnp
            rst = self.rs1.le(v)
            self.assertTrue(rs_eq_array(rst, truth))
            rst = self.rs1 <= v
            self.assertTrue(rs_eq_array(rst, truth))

    def test_ge(self):
        for v, vnp in [
            (self.rs2, self.rs2_np),
            (0, 0),
            (self.rs1_np[0, 10, 10], self.rs1_np[0, 10, 10]),
        ]:
            truth = self.rs1_np >= vnp
            rst = self.rs1.ge(v)
            self.assertTrue(rs_eq_array(rst, truth))
            rst = self.rs1 >= v
            self.assertTrue(rs_eq_array(rst, truth))

    def test_lt(self):
        for v, vnp in [
            (self.rs2, self.rs2_np),
            (0, 0),
            (self.rs1_np[0, 10, 10], self.rs1_np[0, 10, 10]),
        ]:
            truth = self.rs1_np < vnp
            rst = self.rs1.lt(v)
            self.assertTrue(rs_eq_array(rst, truth))
            rst = self.rs1 < v
            self.assertTrue(rs_eq_array(rst, truth))

    def test_gt(self):
        for v, vnp in [
            (self.rs2, self.rs2_np),
            (0, 0),
            (self.rs1_np[0, 10, 10], self.rs1_np[0, 10, 10]),
        ]:
            truth = self.rs1_np > vnp
            rst = self.rs1.gt(v)
            self.assertTrue(rs_eq_array(rst, truth))
            rst = self.rs1 > v
            self.assertTrue(rs_eq_array(rst, truth))


class TestAstype(unittest.TestCase):
    def test_astype(self):
        rs = Raster("test/data/elevation_small.tif")
        for type_code, dtype in DTYPE_INPUT_TO_DTYPE.items():
            self.assertEqual(rs.astype(type_code).dtype, dtype)
            self.assertEqual(rs.astype(type_code).eval().dtype, dtype)

    def test_wrong_type_codes(self):
        rs = Raster("test/data/elevation_small.tif")
        self.assertRaises(ValueError, lambda: rs.astype("not float32"))
        self.assertRaises(ValueError, lambda: rs.astype("other"))

    def test_dtype_property(self):
        rs = Raster("test/data/elevation_small.tif")
        self.assertEqual(rs.dtype, rs._rs.dtype)

    def test_astype_str_uppercase(self):
        rs = Raster("test/data/elevation_small.tif")
        for type_code, dtype in DTYPE_INPUT_TO_DTYPE.items():
            if isinstance(type_code, str):
                type_code = type_code.upper()
                self.assertEqual(rs.astype(type_code).eval().dtype, dtype)


class TestRasterAttrsPropagation(unittest.TestCase):
    def test_arithmetic_attrs(self):
        r1 = Raster("test/data/elevation_small.tif")
        true_attrs = r1._attrs
        v = 2.1
        for op in _BINARY_ARITHMETIC_OPS.keys():
            r2 = r1._binary_arithmetic(v, op).eval()
            self.assertEqual(r2._rs.attrs, true_attrs)
            self.assertEqual(r2._attrs, true_attrs)
        for r in [+r1, -r1]:
            self.assertEqual(r._rs.attrs, true_attrs)
            self.assertEqual(r._attrs, true_attrs)

    def test_logical_attrs(self):
        r1 = Raster("test/data/elevation_small.tif")
        true_attrs = r1._attrs
        v = 1.0
        for op in _BINARY_LOGICAL_OPS.keys():
            r2 = r1._binary_logical(v, op).eval()
            self.assertEqual(r2._rs.attrs, true_attrs)
            self.assertEqual(r2._attrs, true_attrs)

    def test_ctor_attrs(self):
        r1 = Raster("test/data/elevation_small.tif")
        true_attrs = r1._attrs.copy()
        r2 = Raster(Raster("test/data/elevation_small.tif"))
        test_attrs = {"test": 0}
        r3 = Raster("test/data/elevation_small.tif")
        r3._attrs = test_attrs
        self.assertEqual(r2._attrs, true_attrs)
        self.assertEqual(r3._attrs, test_attrs)

    def test_astype_attrs(self):
        rs = Raster("test/data/elevation_small.tif")
        attrs = rs._attrs
        self.assertEqual(rs.astype(int)._attrs, attrs)

    def test_sqrt_attrs(self):
        rs = Raster("test/data/elevation_small.tif")
        rs += np.abs(rs._rs.values.min())
        attrs = rs._attrs
        self.assertEqual(rs.sqrt()._attrs, attrs)

    def test_log_attrs(self):
        rs = Raster("test/data/elevation_small.tif")
        attrs = rs._attrs
        self.assertEqual(rs.log()._attrs, attrs)
        self.assertEqual(rs.log10()._attrs, attrs)

    def test_convolve_attrs(self):
        rs = Raster("test/data/elevation_small.tif")
        attrs = rs._attrs
        self.assertEqual(rs.convolve(np.ones((3, 3)))._attrs, attrs)

    def test_focal_attrs(self):
        rs = Raster("test/data/elevation_small.tif")
        attrs = rs._attrs
        self.assertEqual(rs.focal("max", 3)._attrs, attrs)

    def test_band_concat_attrs(self):
        rs = Raster("test/data/elevation_small.tif")
        attrs = rs._attrs
        rs2 = Raster("test/data/elevation2_small.tif")
        self.assertEqual(rs.band_concat([rs2])._attrs, attrs)


class TestCopy(unittest.TestCase):
    def test_copy(self):
        rs = Raster("test/data/elevation_small.tif")
        copy = rs.copy()
        self.assertIsNot(rs, copy)
        self.assertIsNot(rs._rs, copy._rs)
        self.assertIsNot(rs._attrs, copy._attrs)
        self.assertTrue((rs._rs == copy._rs).all())
        self.assertEqual(rs._attrs, copy._attrs)


class TestSetNullValue(unittest.TestCase):
    def test_set_null_value(self):
        rs = Raster("test/data/null_values.tiff")
        ndv = rs._rs.rio.encoded_nodata
        rs2 = rs.set_null_value(0)
        self.assertEqual(rs._rs.rio.encoded_nodata, ndv)
        self.assertEqual(rs2._rs.rio.encoded_nodata, 0)


class TestReplaceNull(unittest.TestCase):
    def test_replace_null(self):
        fill_value = 0
        rs = Raster("test/data/null_values.tiff")
        rsnp = rxr.open_rasterio("test/data/null_values.tiff").values
        rsnp_replaced = rsnp.copy()
        rsnp_replaced[np.isnan(rsnp)] = fill_value
        rsnp_replaced[rsnp == rs._rs.rio.encoded_nodata] = fill_value
        rs = rs.replace_null(fill_value)
        self.assertTrue(rs_eq_array(rs, rsnp_replaced))


class TestRemapRange(unittest.TestCase):
    def test_remap_range(self):
        rs = Raster("test/data/elevation_small.tif")
        rsnp = rs._rs.values
        min, max, new_value = rs._rs.values.min(), rs._rs.values.max(), 0
        rng = (min, min + (0.2 * (max - min)))
        match = rsnp >= rng[0]
        match &= rsnp < rng[1]
        rsnp[match] = new_value
        rs = rs.remap_range(rng[0], rng[1], new_value)
        self.assertTrue(rs_eq_array(rs, rsnp))

    def test_remap_range_multi(self):
        rs = Raster("test/data/elevation_small.tif")
        min, max = rs._rs.values.min(), rs._rs.values.max()
        rsnp = rs._rs.values
        span = max - min
        rng1 = (min, min + (0.2 * span))
        match = rsnp >= rng1[0]
        match &= rsnp < rng1[1]
        nv1 = 0
        rsnp[match] = nv1
        rng2 = (min + (0.2 * span), min + (0.3 * span))
        match = rsnp >= rng2[0]
        match &= rsnp < rng2[1]
        nv2 = 1
        rsnp[match] = nv2
        rs = rs.remap_range(rng1[0], rng1[1], nv1, rng2[0], rng2[1], nv2)
        self.assertTrue(rs_eq_array(rs, rsnp))
        rsnp = rs._rs.values
        span = max - min
        rng1 = (min, min + (0.2 * span))
        match = rsnp >= rng1[0]
        match &= rsnp < rng1[1]
        nv1 = 0
        rsnp[match] = nv1
        rng2 = (min + (0.2 * span), min + (0.3 * span))
        match = rsnp >= rng2[0]
        match &= rsnp < rng2[1]
        nv2 = 1
        rsnp[match] = nv2
        rs = rs.remap_range(rng1[0], rng1[1], nv1, rng2[0], rng2[1], nv2)
        rng3 = (min + (0.3 * span), min + (0.4 * span))
        match = rsnp >= rng3[0]
        match &= rsnp < rng3[1]
        nv3 = 2
        rsnp[match] = nv3
        rs = rs.remap_range(*rng1, nv1, *rng2, nv2, *rng3, nv3)
        self.assertTrue(rs_eq_array(rs, rsnp))

    def test_remap_range_errors(self):
        rs = Raster("test/data/elevation_small.tif")
        # TypeError if not scalars
        with self.assertRaises(TypeError):
            rs.remap_range(None, 2, 4)
        with self.assertRaises(TypeError):
            rs.remap_range(0, "2", 4)
        with self.assertRaises(TypeError):
            rs.remap_range(0, 2, None)
        with self.assertRaises(TypeError):
            rs.remap_range(0, 2, 1, 2, 3, None)
        # ValueError if nan
        with self.assertRaises(ValueError):
            rs.remap_range(np.nan, 2, 4)
        with self.assertRaises(ValueError):
            rs.remap_range(0, np.nan, 4)
        # ValueError if range reversed
        with self.assertRaises(ValueError):
            rs.remap_range(0, -1, 6)
        # RuntimeError if not enough values to form group
        with self.assertRaises(RuntimeError):
            rs.remap_range(0, 1, 2, 0, 3)
        with self.assertRaises(RuntimeError):
            rs.remap_range(0, 1, 2, 2, 3, 4, 9)


class TestEval(unittest.TestCase):
    def test_eval(self):
        rs = Raster("test/data/elevation_small.tif")
        rsnp = rs._rs.values
        rs += 2
        rsnp += 2
        rs -= rs
        rsnp -= rsnp
        rs *= -1
        rsnp *= -1
        result = rs.eval()
        # Make sure new raster returned
        self.assertIsNot(rs, result)
        self.assertIsNot(rs._rs, result._rs)
        # Make sure that original raster is still lazy
        self.assertTrue(dask.is_dask_collection(rs._rs))
        self.assertTrue(rs_eq_array(result, rsnp))
        self.assertFalse(dask.is_dask_collection(result._rs))


class TestToXarray(unittest.TestCase):
    def test_to_xarray(self):
        rs = Raster("test/data/elevation2_small.tif")
        self.assertTrue(isinstance(rs.to_xarray(), xr.DataArray))
        self.assertIs(rs.to_xarray(), rs._rs)


class TestToDask(unittest.TestCase):
    def test_to_dask(self):
        rs = Raster("test/data/elevation2_small.tif")
        self.assertTrue(isinstance(rs.to_dask(), dask.array.Array))
        self.assertIs(rs.to_dask(), rs._rs.data)
        self.assertTrue(isinstance(rs.eval().to_dask(), dask.array.Array))


class TestToLazy(unittest.TestCase):
    def test_to_lazy(self):
        rs = Raster("test/data/elevation2_small.tif")
        rs += rs
        rs_nonlazy = rs.eval()
        rs_lazy = rs_nonlazy.to_lazy()
        self.assertFalse(dask.is_dask_collection(rs_nonlazy._rs))
        self.assertTrue(dask.is_dask_collection(rs_lazy._rs))


class TestAndOr(unittest.TestCase):
    def test_and(self):
        rs1 = Raster("test/data/elevation_small.tif")
        rsnp1 = rs1._rs.values
        rs2 = Raster("test/data/elevation2_small.tif")
        rsnp2 = rs2._rs.values
        rsnp2 -= rsnp2.max() / 2
        truth = (rsnp1 > 0) & (rsnp2 > 0)
        self.assertTrue(rs_eq_array(rs1 & rs2, truth))
        self.assertTrue(rs_eq_array(rs1.and_(rs2), truth))
        truth = rsnp1.astype(bool) & rsnp2.astype(bool)
        self.assertTrue(rs_eq_array(rs1.and_(rs2, "cast"), truth))
        for v in [-22.0, -20, 0, 1, 1.0, 23.1, 30]:
            truth = (rsnp1 > 0) & (v > 0)
            self.assertTrue(rs_eq_array(rs1 & v, truth))
            self.assertTrue(rs_eq_array(rs1.and_(v), truth))
            truth = rsnp1.astype(bool) & bool(v)
            self.assertTrue(rs_eq_array(rs1.and_(v, "cast"), truth))
        for v in [False, True]:
            truth = (rsnp1 > 0) & v
            self.assertTrue(rs_eq_array(rs1 & v, truth))
            self.assertTrue(rs_eq_array(rs1.and_(v), truth))
            truth = rsnp1.astype(bool) & v
            self.assertTrue(rs_eq_array(rs1.and_(v, "cast"), truth))

    def test_or(self):
        rs1 = Raster("test/data/elevation_small.tif")
        rsnp1 = rs1._rs.values
        rs2 = Raster("test/data/elevation2_small.tif")
        rsnp2 = rs2._rs.values
        rsnp2 -= rsnp2.max() / 2
        truth = (rsnp1 > 0) | (rsnp2 > 0)
        self.assertTrue(rs_eq_array(rs1 | rs2, truth))
        self.assertTrue(rs_eq_array(rs1.or_(rs2), truth))
        truth = rsnp1.astype(bool) | rsnp2.astype(bool)
        self.assertTrue(rs_eq_array(rs1.or_(rs2, "cast"), truth))
        for v in [-22.0, -20, 0, 1, 1.0, 23.1, 30]:
            truth = (rsnp1 > 0) | (v > 0)
            self.assertTrue(rs_eq_array(rs1 | v, truth))
            self.assertTrue(rs_eq_array(rs1.or_(v), truth))
            truth = rsnp1.astype(bool) | bool(v)
            self.assertTrue(rs_eq_array(rs1.or_(v, "cast"), truth))
        for v in [False, True]:
            truth = (rsnp1 > 0) | v
            self.assertTrue(rs_eq_array(rs1 | v, truth))
            self.assertTrue(rs_eq_array(rs1.or_(v), truth))
            truth = rsnp1.astype(bool) | v
            self.assertTrue(rs_eq_array(rs1.or_(v, "cast"), truth))

    def test_and_or_output_type(self):
        rs1 = Raster("test/data/elevation_small.tif")
        rs2 = Raster("test/data/elevation2_small.tif")
        bools = [BOOL]
        uints = [U8, U16, U32, U64]
        ints = [I8, I16, I32, I64]
        floats = [F16, F32, F64, F128]
        types = [*bools, *uints, *ints, *floats]
        out_kind_priorities = {
            "bb": "b",
            "bu": "u",
            "bi": "i",
            "bf": "f",
            "uu": "u",
            "ui": "i",
            "uf": "f",
            "ii": "i",
            "if": "f",
            "ff": "f",
        }
        # Standardize key strings
        out_kind_priorities = {
            "".join(sorted(k)): v for k, v in out_kind_priorities.items()
        }
        for t1 in types:
            for t2 in types:
                res = rs1.astype(t1) & rs2.astype(t2)
                kstr = "".join(sorted((t1.kind, t2.kind)))
                target_kind = out_kind_priorities[kstr]
                self.assertEqual(target_kind, res.dtype.kind)
                if t1.kind == t2.kind:
                    widths = [t1.itemsize, t2.itemsize]
                    self.assertEqual(res.dtype.itemsize, max(widths))
                else:
                    target_type = t1 if t1.kind == target_kind else t2
                    self.assertEqual(res.dtype, target_type)


class TestConvolve(unittest.TestCase):
    def test_convolve(self):
        rs = Raster("test/data/elevation2_small.tif")
        kern = np.ones((3, 3))
        rsnp = rs._rs.values
        modes = ["reflect", "constant", "nearest", "mirror", "wrap"]
        for m in modes:
            truth = rsnp.copy()
            for b in range(truth.shape[0]):
                truth[b] = scipy.ndimage.convolve(truth[b], kern, mode=m)
            self.assertTrue(rs_eq_array(rs.convolve(kern, mode=m), truth))
        rs = Raster("test/data/multiband_small.tif")
        kern = np.ones((5, 5))
        rsnp = rs._rs.values
        modes = ["reflect", "constant", "nearest", "mirror", "wrap"]
        for m in modes:
            truth = rsnp.copy()
            for b in range(truth.shape[0]):
                truth[b] = scipy.ndimage.convolve(truth[b], kern, mode=m)
            self.assertTrue(rs_eq_array(rs.convolve(kern, mode=m), truth))

    def test_convolve_cval(self):
        rs = Raster("test/data/elevation2_small.tif")
        kern = np.ones((3, 3))
        rsnp = rs._rs.values
        cvals = [-22.9, -1.0, 0, 1, 123.0]
        for cv in cvals:
            truth = rsnp.copy()
            for b in range(truth.shape[0]):
                truth[b] = scipy.ndimage.convolve(
                    truth[b], kern, mode="constant", cval=cv
                )
            self.assertTrue(
                rs_eq_array(rs.convolve(kern, mode="constant", cval=cv), truth)
            )

    def test_convolve_kernel_shape_error(self):
        rs = Raster("test/data/elevation2_small.tif")
        kern = np.ones((1, 3, 3))
        with self.assertRaises(ValueError):
            rs.convolve(kern)
        kern = np.ones((3))
        with self.assertRaises(ValueError):
            rs.convolve(kern)
        kern = np.ones((2, 3, 3))
        with self.assertRaises(ValueError):
            rs.convolve(kern)


class TestFocal(unittest.TestCase):
    def test_focal_window(self):
        truths = [
            np.array([[1.0]]),
            np.array([[0.0, 1.0, 0.0], [1.0, 1.0, 1.0], [0.0, 1.0, 0.0]]),
            np.array(
                [
                    [0.0, 0.0, 1.0, 0.0, 0.0],
                    [0.0, 1.0, 1.0, 1.0, 0.0],
                    [1.0, 1.0, 1.0, 1.0, 1.0],
                    [0.0, 1.0, 1.0, 1.0, 0.0],
                    [0.0, 0.0, 1.0, 0.0, 0.0],
                ],
            ),
            np.array(
                [
                    [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
                    [0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0],
                    [0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0],
                    [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
                    [0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0],
                    [0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0],
                    [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
                ],
            ),
            np.array(
                [
                    [0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0],
                    [0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0],
                    [0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0],
                    [0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0],
                    [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
                    [0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0],
                    [0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0],
                    [0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0],
                    [0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0],
                ],
            ),
            np.array(
                [
                    [0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                    [0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0],
                    [0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0],
                    [0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0],
                    [0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0],
                    [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
                    [0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0],
                    [0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0],
                    [0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0],
                    [0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0],
                    [0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                ],
            ),
        ]
        for r, truth in zip(range(1, len(truths) + 1), truths):
            window = _get_focal_window(r)
            self.assertTrue(array_eq_all(window, truth))
            self.assertEqual(window.dtype, I32)
        for w in range(1, 6):
            for h in range(1, 6):
                window = _get_focal_window(w, h)
                self.assertTrue(array_eq_all(window, np.ones((w, h))))
                self.assertEqual(window.dtype, I32)

    modes = ["reflect", "constant", "nearest", "mirror", "wrap"]

    def test_focal_basic_filters(self):
        rs = Raster("test/data/elevation2_small.tif")
        rsnp = rs._rs.values
        ops = [
            (scipy.ndimage.maximum_filter, "max"),
            (scipy.ndimage.minimum_filter, "min"),
            (scipy.ndimage.median_filter, "median"),
            (
                lambda x, footprint, mode: scipy.ndimage.convolve(
                    x, footprint, mode=mode
                ),
                "sum",
            ),
            (
                lambda x, footprint, mode: scipy.ndimage.convolve(
                    x, footprint, mode=mode
                )
                / footprint.sum(),
                "mean",
            ),
        ]
        for scipy_func, op_str in ops:
            for mode in self.modes:
                for r in range(1, 5):
                    window = _get_focal_window(r)
                    truth = rsnp.copy()
                    for bnd in range(truth.shape[0]):
                        truth[bnd] = scipy_func(
                            truth[bnd], footprint=window, mode=mode
                        )
                    test = rs.focal(op_str, r, mode=mode)
                    self.assertTrue(rs_eq_array(test, truth))
                for w in range(1, 5):
                    for h in range(1, 5):
                        window = _get_focal_window(w, h)
                        truth = rsnp.copy()
                        for bnd in range(truth.shape[0]):
                            truth[bnd] = scipy_func(
                                truth[bnd], footprint=window, mode=mode
                            )
                        test = rs.focal(op_str, w, h, mode=mode)
                        self.assertTrue(rs_eq_array(test, truth))

    def test_focal_var_std(self):
        rs = Raster("test/data/elevation_small.tif").astype(F64)
        rsnp = rs._rs.values
        for r in range(1, 5):
            window = _get_focal_window(r)
            data = rsnp.copy()
            sq = rsnp ** 2
            n = window.sum()
            for bnd in range(rsnp.shape[0]):
                data[bnd] = scipy.ndimage.convolve(
                    data[bnd], window, mode="constant"
                )
                sq[bnd] = scipy.ndimage.convolve(
                    sq[bnd], window, mode="constant"
                )
            truth = (sq - ((data ** 2) / n)) / n
            test = rs.focal("variance", r)
            self.assertTrue(rs_eq_array(test, truth))
            truth = np.sqrt(truth)
            test = rs.focal("std", r)
            self.assertTrue(rs_eq_array(test, truth))
        for w in range(1, 5):
            for h in range(1, 5):
                window = _get_focal_window(w, h)
                data = rsnp.copy()
                sq = rsnp ** 2
                n = window.sum()
                for bnd in range(rsnp.shape[0]):
                    data[bnd] = scipy.ndimage.convolve(
                        data[bnd], window, mode="constant"
                    )
                    sq[bnd] = scipy.ndimage.convolve(
                        sq[bnd], window, mode="constant"
                    )
                truth = (sq - ((data ** 2) / n)) / n
                test = rs.focal("variance", w, h)
                self.assertTrue(rs_eq_array(test, truth))
                truth = np.sqrt(truth)
                test = rs.focal("std", w, h)
                self.assertTrue(rs_eq_array(test, truth))

    def test_focal_errors(self):
        rs = Raster("test/data/elevation_small.tif")
        with self.assertRaises(ValueError):
            rs.focal("other", 1, 2)
        with self.assertRaises(TypeError):
            rs.focal("max", 1.2, 2)
        with self.assertRaises(ValueError):
            rs.focal("max", 0)
        with self.assertRaises(ValueError):
            rs.focal("max", -2)
        with self.assertRaises(TypeError):
            rs.focal("max", 3, 3.2)
        with self.assertRaises(ValueError):
            rs.focal("max", 3, 0)
        with self.assertRaises(ValueError):
            rs.focal("max", 3, -2)


class TestGetBands(unittest.TestCase):
    def test_get_bands(self):
        rs = Raster("test/data/multiband_small.tif")
        rsnp = rs._rs.values
        self.assertTrue(rs_eq_array(rs.get_bands(1), rsnp[:1]))
        self.assertTrue(rs_eq_array(rs.get_bands(2), rsnp[1:2]))
        self.assertTrue(rs_eq_array(rs.get_bands(3), rsnp[2:3]))
        self.assertTrue(rs_eq_array(rs.get_bands(4), rsnp[3:4]))
        for bands in [[1], [1, 2], [1, 1], [3, 1, 2], [4, 3, 2, 1]]:
            np_bands = [i - 1 for i in bands]
            self.assertTrue(rs_eq_array(rs.get_bands(bands), rsnp[np_bands]))

        self.assertTrue(len(rs.get_bands(1).shape) == 3)

        for bands in [0, 5, [1, 5], [0]]:
            with self.assertRaises(IndexError):
                rs.get_bands(bands)
        with self.assertRaises(ValueError):
            rs.get_bands([])


class TestBandConcat(unittest.TestCase):
    def test_band_concat(self):
        rs1 = Raster("test/data/elevation_small.tif")
        rs2 = Raster("test/data/elevation2_small.tif")
        rsnp1 = rs1._rs.values
        rsnp2 = rs2._rs.values
        truth = np.concatenate((rsnp1, rsnp2))
        test = rs1.band_concat([rs2])
        self.assertEqual(test.shape, truth.shape)
        self.assertTrue(rs_eq_array(test, truth))
        truth = np.concatenate((rsnp1, rsnp1, rsnp2, truth))
        test = rs1.band_concat([rs1, rs2, test])
        self.assertEqual(test.shape, truth.shape)
        self.assertTrue(rs_eq_array(test, truth))

    def test_band_concat_band_dim_values(self):
        rs1 = Raster("test/data/elevation_small.tif")
        rs2 = Raster("test/data/elevation2_small.tif")
        test = rs1.band_concat([rs2])
        # Make sure that band is now an increaseing list starting at 1 and
        # incrementing by 1
        self.assertTrue(all(test._rs.band == [1, 2]))
        test = rs1.band_concat([test, rs2])
        self.assertTrue(all(test._rs.band == [1, 2, 3, 4]))

    def test_band_concat_path_inputs(self):
        rs1 = Raster("test/data/elevation_small.tif")
        rs2 = Raster("test/data/elevation2_small.tif")
        rsnp1 = rs1._rs.values
        rsnp2 = rs2._rs.values
        truth = np.concatenate((rsnp1, rsnp2, rsnp1, rsnp2))
        test = rs1.band_concat(
            [
                rs2,
                "test/data/elevation_small.tif",
                "test/data/elevation2_small.tif",
            ]
        )
        self.assertEqual(test.shape, truth.shape)
        self.assertTrue(rs_eq_array(test, truth))

    def test_band_concat_errors(self):
        rs1 = Raster("test/data/elevation_small.tif")
        rs2 = Raster("test/data/elevation2_small.tif")
        rs3 = Raster("test/data/elevation.tif")
        with self.assertRaises(ValueError):
            rs1.band_concat([])
        with self.assertRaises(ValueError):
            rs1.band_concat([rs2, rs3])
        with self.assertRaises(ValueError):
            rs3.band_concat([rs2])


if __name__ == "__main__":
    unittest.main()
